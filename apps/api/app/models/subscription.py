import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Subscription(Base):
    """Mirrors the user's Stripe subscription. Kept in sync entirely via
    webhook events (see app/routers/billing.py) — never written to from
    request handlers directly, so Stripe is always the source of truth."""

    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    stripe_customer_id: Mapped[str] = mapped_column(String, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String, nullable=True)
    plan: Mapped[str] = mapped_column(String, default="free")  # free|pro|agency
    status: Mapped[str] = mapped_column(String, default="active")  # active|past_due|canceled
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
