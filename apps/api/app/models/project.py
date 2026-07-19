import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


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
