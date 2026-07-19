from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey
from app.models.subscription import Subscription
from app.models.usage import UsageCounter
from app.models.user import User

# Monthly audit-run quota per plan. Free is deliberately tight enough to
# convert serious users but generous enough to fully evaluate the product
# on one real project.
PLAN_SCAN_LIMITS = {
    "free": 10,
    "pro": 200,
    "agency": 2000,
}

# GEO checks call paid LLM APIs (one call per configured provider), unlike
# the free HTTP-based audit tools -- kept much tighter than scan limits so
# a single user can't run up real API spend on the free plan.
PLAN_GEO_CHECK_LIMITS = {
    "free": 5,
    "pro": 100,
    "agency": 1000,
}

# Active (non-revoked) API keys a user may hold at once -- not a monthly
# counter like the two above, just a ceiling checked at creation time.
PLAN_API_KEY_LIMITS = {
    "free": 1,
    "pro": 5,
    "agency": 20,
}


def _current_period_start() -> date:
    return date.today().replace(day=1)


async def _get_or_create_counter(db: AsyncSession, user: User) -> UsageCounter:
    period_start = _current_period_start()
    counter = await db.scalar(
        select(UsageCounter).where(UsageCounter.user_id == user.id, UsageCounter.period_start == period_start)
    )
    if counter is None:
        # Explicit 0s, not reliance on the column's `default=` -- that only
        # applies at flush time, so a freshly-constructed counter's
        # attributes read back as None until then, breaking the
        # immediate `>= limit` comparisons below.
        counter = UsageCounter(user_id=user.id, period_start=period_start, scans_used=0, geo_checks_used=0)
        db.add(counter)
    return counter


async def _current_plan(db: AsyncSession, user: User) -> str:
    sub = await db.scalar(select(Subscription).where(Subscription.user_id == user.id))
    return sub.plan if sub and sub.status == "active" else "free"


async def check_and_increment_usage(db: AsyncSession, user: User) -> None:
    """Raises 402 if the user is over their plan's monthly scan quota,
    otherwise increments usage and lets the caller proceed. Called once
    per audit creation, before the orchestrator is allowed to run."""

    plan = await _current_plan(db, user)
    limit = PLAN_SCAN_LIMITS.get(plan, PLAN_SCAN_LIMITS["free"])
    counter = await _get_or_create_counter(db, user)

    if counter.scans_used >= limit:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            f"Monthly scan limit reached for the '{plan}' plan ({limit} scans).",
        )

    counter.scans_used += 1
    await db.commit()


async def check_and_increment_geo_usage(db: AsyncSession, user: User) -> None:
    """Same idea as check_and_increment_usage but against the separate,
    tighter GEO-check quota, since each check costs real per-provider LLM
    API spend rather than a free HTTP request."""

    plan = await _current_plan(db, user)
    limit = PLAN_GEO_CHECK_LIMITS.get(plan, PLAN_GEO_CHECK_LIMITS["free"])
    counter = await _get_or_create_counter(db, user)

    if counter.geo_checks_used >= limit:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            f"Monthly GEO check limit reached for the '{plan}' plan ({limit} checks).",
        )

    counter.geo_checks_used += 1
    await db.commit()


async def check_api_key_limit(db: AsyncSession, user: User) -> None:
    """Raises 402 if the user already holds the max active API keys for
    their plan. Unlike the scan/GEO quotas, this doesn't increment
    anything -- creating the ApiKey row itself is the state change."""

    plan = await _current_plan(db, user)
    limit = PLAN_API_KEY_LIMITS.get(plan, PLAN_API_KEY_LIMITS["free"])

    active_count = await db.scalar(
        select(func.count())
        .select_from(ApiKey)
        .where(ApiKey.user_id == user.id, ApiKey.revoked_at.is_(None))
    )

    if active_count >= limit:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            f"Active API key limit reached for the '{plan}' plan ({limit} keys). "
            "Revoke an existing key before creating a new one.",
        )
