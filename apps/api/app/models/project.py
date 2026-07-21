import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

MONITORING_FREQUENCIES = ("daily", "weekly", "monthly")


class Project(Base):
    """A domain a user has added to track. One project = one root domain."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    domain: Mapped[str] = mapped_column(String, index=True)
    # Optional -- used by the GEO tracker (Phase 4) to detect mentions in
    # LLM answer text, since AI answers often name a brand without citing
    # its URL. Domain alone only catches citation-URL matches.
    brand_name: Mapped[str | None] = mapped_column(String, nullable=True)
    # One-off competitor lookups (created by the History & Compare page's
    # "compare vs. competitor" flow) are real Project rows so audits/GEO
    # checks work unchanged, but are excluded from the main "Your sites"
    # list -- see list_projects in app/routers/projects.py.
    is_competitor_only: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Scheduled monitoring -- a periodic re-audit + comparison report,
    # emailed from the owning user's own connected Gmail (not a
    # transactional email service) to `monitoring_recipient_email`, e.g.
    # the site owner a freelancer/consultant is pitching.
    monitoring_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    monitoring_frequency: Mapped[str | None] = mapped_column(String, nullable=True)  # daily|weekly|monthly
    monitoring_recipient_email: Mapped[str | None] = mapped_column(String, nullable=True)
    monitoring_message: Mapped[str | None] = mapped_column(String, nullable=True)
    monitoring_last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    monitoring_next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
