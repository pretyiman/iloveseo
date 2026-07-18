import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class UsageCounter(Base):
    """Scans used by a user within one billing period. One row per
    (user, period_start); incremented atomically when an audit is created,
    checked against the plan's monthly quota before the audit is allowed."""

    __tablename__ = "usage_counters"
    __table_args__ = (UniqueConstraint("user_id", "period_start", name="uq_usage_user_period"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    period_start: Mapped[date] = mapped_column(Date)
    scans_used: Mapped[int] = mapped_column(Integer, default=0)
    # Tracked separately from scans_used: GEO checks call paid LLM APIs
    # per provider, unlike the free HTTP-based audit tools, so they need
    # their own (tighter) quota.
    geo_checks_used: Mapped[int] = mapped_column(Integer, default=0)
