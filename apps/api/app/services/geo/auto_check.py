import logging

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.plan_limits import check_and_increment_geo_usage
from app.models.geo import GeoCheck, TrackedQuery
from app.models.project import Project
from app.models.user import User
from app.schemas import AiVisibilityOut, AiVisibilityProviderOut
from app.services.geo.runner import run_geo_check

logger = logging.getLogger(__name__)

PROVIDER_NAMES = ("perplexity", "openai")


async def get_or_create_default_tracked_query(db: AsyncSession, project: Project) -> TrackedQuery:
    """Every project gets one auto-managed tracked query so AI Visibility can
    run without the user having to set one up by hand -- reuses the oldest
    one if it already exists (e.g. from a previous audit, or hand-created
    via the /geo page) rather than creating a new one every time."""
    existing = await db.scalar(
        select(TrackedQuery).where(TrackedQuery.project_id == project.id).order_by(TrackedQuery.created_at).limit(1)
    )
    if existing is not None:
        return existing

    tracked_query = TrackedQuery(
        project_id=project.id,
        query_text=f"Tell me about {project.brand_name or project.domain}.",
        competitor_domains=[],
    )
    db.add(tracked_query)
    await db.commit()
    await db.refresh(tracked_query)
    return tracked_query


async def run_default_geo_check(db: AsyncSession, project: Project) -> None:
    """Best-effort AI Visibility check run automatically as part of every
    audit. Must never raise -- a billing/quota/provider problem here is a
    degraded AI Visibility section, not a failed audit."""
    settings = get_settings()
    if not (settings.perplexity_api_key or settings.openai_api_key):
        return  # nothing configured -- no quota spent, no row written

    try:
        user = await db.get(User, project.user_id)
        if user is None:
            return

        try:
            await check_and_increment_geo_usage(db, user)
        except HTTPException:
            return  # monthly GEO-check quota reached -- keep showing the last result

        tracked_query = await get_or_create_default_tracked_query(db, project)
        outcomes = await run_geo_check(
            tracked_query.query_text, project.domain, project.brand_name, tracked_query.competitor_domains
        )
        db.add_all(
            [
                GeoCheck(
                    tracked_query_id=tracked_query.id,
                    provider=outcome.provider,
                    status=outcome.status,
                    cited=outcome.cited,
                    position=outcome.position,
                    competitor_mentions=outcome.competitor_mentions,
                    citation_urls=outcome.citation_urls,
                    response_text=outcome.response_text,
                    error_message=outcome.error_message,
                )
                for outcome in outcomes
            ]
        )
        await db.commit()
    except Exception:  # noqa: BLE001 -- AI Visibility must never sink the audit
        logger.exception("Auto GEO check failed for project %s", project.id)


async def build_ai_visibility_summary(db: AsyncSession, project: Project) -> AiVisibilityOut:
    """Pure read: current provider configuration plus the latest check per
    provider, if any tracked query and checks exist yet for this project."""
    settings = get_settings()
    configured = {"perplexity": bool(settings.perplexity_api_key), "openai": bool(settings.openai_api_key)}

    tracked_query = await db.scalar(
        select(TrackedQuery).where(TrackedQuery.project_id == project.id).order_by(TrackedQuery.created_at).limit(1)
    )

    latest_by_provider: dict[str, GeoCheck] = {}
    if tracked_query is not None:
        checks = await db.scalars(
            select(GeoCheck)
            .where(GeoCheck.tracked_query_id == tracked_query.id)
            .order_by(GeoCheck.created_at.desc())
        )
        for check in checks:
            latest_by_provider.setdefault(check.provider, check)

    providers = [
        AiVisibilityProviderOut(
            provider=name,
            configured=configured[name],
            status=latest_by_provider[name].status if name in latest_by_provider else None,
            cited=latest_by_provider[name].cited if name in latest_by_provider else None,
            position=latest_by_provider[name].position if name in latest_by_provider else None,
            error_message=latest_by_provider[name].error_message if name in latest_by_provider else None,
            checked_at=latest_by_provider[name].created_at if name in latest_by_provider else None,
        )
        for name in PROVIDER_NAMES
    ]

    return AiVisibilityOut(query_text=tracked_query.query_text if tracked_query else None, providers=providers)
