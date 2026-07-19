import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_or_api_key
from app.core.db import get_db
from app.core.plan_limits import check_and_increment_geo_usage
from app.core.rate_limit import enforce_rate_limit
from app.models.geo import GeoCheck, TrackedQuery
from app.models.project import Project
from app.models.user import User
from app.schemas import GeoCheckOut, TrackedQueryCreate, TrackedQueryOut
from app.services.geo.runner import run_geo_check

router = APIRouter(tags=["geo"])


async def _get_owned_project(db: AsyncSession, user: User, project_id: uuid.UUID) -> Project:
    project = await db.get(Project, project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


async def _get_owned_tracked_query(
    db: AsyncSession, user: User, tracked_query_id: uuid.UUID
) -> tuple[TrackedQuery, Project]:
    tracked_query = await db.get(TrackedQuery, tracked_query_id)
    if tracked_query is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tracked query not found")
    project = await db.get(Project, tracked_query.project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tracked query not found")
    return tracked_query, project


@router.post("/projects/{project_id}/tracked-queries", response_model=TrackedQueryOut)
async def create_tracked_query(
    project_id: uuid.UUID,
    payload: TrackedQueryCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_or_api_key),
    _: None = Depends(enforce_rate_limit),
) -> TrackedQuery:
    await _get_owned_project(db, user, project_id)
    tracked_query = TrackedQuery(
        project_id=project_id, query_text=payload.query_text, competitor_domains=payload.competitor_domains
    )
    db.add(tracked_query)
    await db.commit()
    await db.refresh(tracked_query)
    return tracked_query


@router.get("/projects/{project_id}/tracked-queries", response_model=list[TrackedQueryOut])
async def list_tracked_queries(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_or_api_key),
    _: None = Depends(enforce_rate_limit),
) -> list[TrackedQuery]:
    await _get_owned_project(db, user, project_id)
    result = await db.scalars(
        select(TrackedQuery).where(TrackedQuery.project_id == project_id).order_by(TrackedQuery.created_at.desc())
    )
    return list(result)


@router.delete("/tracked-queries/{tracked_query_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tracked_query(
    tracked_query_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_or_api_key),
    _: None = Depends(enforce_rate_limit),
) -> None:
    tracked_query, _ = await _get_owned_tracked_query(db, user, tracked_query_id)
    await db.delete(tracked_query)
    await db.commit()


@router.post("/tracked-queries/{tracked_query_id}/check", response_model=list[GeoCheckOut])
async def run_check(
    tracked_query_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_or_api_key),
    _: None = Depends(enforce_rate_limit),
) -> list[GeoCheck]:
    tracked_query, project = await _get_owned_tracked_query(db, user, tracked_query_id)
    await check_and_increment_geo_usage(db, user)

    outcomes = await run_geo_check(
        tracked_query.query_text, project.domain, project.brand_name, tracked_query.competitor_domains
    )

    rows = [
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
    db.add_all(rows)
    await db.commit()
    for row in rows:
        await db.refresh(row)
    return rows


@router.get("/tracked-queries/{tracked_query_id}/checks", response_model=list[GeoCheckOut])
async def list_checks(
    tracked_query_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_or_api_key),
    _: None = Depends(enforce_rate_limit),
) -> list[GeoCheck]:
    await _get_owned_tracked_query(db, user, tracked_query_id)
    result = await db.scalars(
        select(GeoCheck).where(GeoCheck.tracked_query_id == tracked_query_id).order_by(GeoCheck.created_at.desc())
    )
    return list(result)
