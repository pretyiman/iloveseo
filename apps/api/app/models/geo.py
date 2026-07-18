import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class TrackedQuery(Base):
    """A question a project wants to monitor AI-answer-engine visibility
    for, e.g. "best project management software for small teams". Checked
    on demand (Phase 4 MVP) against each configured LLM provider."""

    __tablename__ = "tracked_queries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    query_text: Mapped[str] = mapped_column(String)
    # Domains to also check for in the same response, so a check surfaces
    # share-of-voice against named competitors in one pass rather than
    # requiring a separate tracked query per competitor.
    competitor_domains: Mapped[list] = mapped_column(JSONB, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GeoCheck(Base):
    """One provider's answer to one tracked query at one point in time."""

    __tablename__ = "geo_checks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tracked_query_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tracked_queries.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String)  # "perplexity" | "openai"
    status: Mapped[str] = mapped_column(String)  # "ok" | "error"
    cited: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-indexed rank among citation_urls
    competitor_mentions: Mapped[dict] = mapped_column(JSONB, default=dict)  # {domain: bool}
    citation_urls: Mapped[list] = mapped_column(JSONB, default=list)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
