import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# Plain strings rather than a Postgres enum type, deliberately: new tool
# names and statuses will be added often in the early phases and a string
# column needs no migration to accommodate them.


class Audit(Base):
    """One orchestrator run against a project. Fans out to every
    registered tool concurrently; status reflects the run as a whole."""

    __tablename__ = "audits"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id"), index=True
    )
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|running|completed|failed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditResult(Base):
    """One tool's output within an audit. Written as soon as that tool
    finishes so the dashboard can poll and show live, incremental progress."""

    __tablename__ = "audit_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    audit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("audits.id"), index=True)
    tool: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String)  # running|ok|error
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    findings: Mapped[list] = mapped_column(JSONB, default=list)
    raw: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Only set for tools that run as a separate background job (Page Crawl,
    # via Celery) rather than inline in the fast asyncio.gather batch --
    # lets the dashboard show incremental progress while status=="running".
    progress: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
