from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


def _current_period_start() -> date:
    return date.today().replace(day=1)


async def check_and_increment_usage(db: AsyncSession, user: User) -> None:
    """Raises 402 if the user is over their plan's monthly scan quota,
    otherwise increments usage and lets the caller proceed. Called once
    per audit creation, before the orchestrator is allowed to run."""

    sub = await db.scalar(select(Subscription).where(Subscription.user_id == user.id))
    plan = sub.plan if sub and sub.status == "active" else "free"
    limit = PLAN_SCAN_LIMITS.get(plan, PLAN_SCAN_LIMITS["free"])

    period_start = _current_period_start()
    counter = await db.scalar(
        select(UsageCounter).where(
            UsageCounter.user_id == user.id, UsageCounter.period_start == period_start
        )
    )
    if counter is None:
        counter = UsageCounter(user_id=user.id, period_start=period_start, scans_used=0)
        db.add(counter)

    if counter.scans_used >= limit:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            f"Monthly scan limit reached for the '{plan}' plan ({limit} scans).",
        )

    counter.scans_used += 1
    await db.commit()
