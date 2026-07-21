import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.share_tokens import generate_share_token
from app.models.audit import Audit, AuditResult
from app.models.project import Project
from app.models.user import User
from app.services.audit_view import compose_audit_out
from app.services.gmail_sender import get_google_access_token, send_email
from app.services.monitoring_email import build_report_email_html
from app.services.orchestrator import run_audit

FREQUENCY_DELTAS = {
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
    "monthly": timedelta(days=30),
}


class MonitoringNotConfiguredError(Exception):
    pass


def compute_next_run_at(frequency: str) -> datetime:
    return datetime.now(UTC) + FREQUENCY_DELTAS[frequency]


async def _wait_for_completion(audit_id, timeout_seconds: int = 300, interval_seconds: int = 3) -> None:
    """Waits for the *whole* audit, including Page Crawl -- unlike the
    dashboard's own polling (which is fine settling for "the fast batch is
    done, Page Crawl might still be running"), an emailed report should
    reflect the complete picture. Uses its own throwaway sessions per
    poll rather than the caller's session, since `run_audit` writes via
    entirely separate sessions and expire_on_commit=False means a shared
    session would otherwise keep returning a stale cached Audit."""
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while True:
        async with SessionLocal() as db:
            audit = await db.get(Audit, audit_id)
            results = list(await db.scalars(select(AuditResult).where(AuditResult.audit_id == audit_id)))

        still_running = any(r.status == "running" for r in results)
        if audit is not None and audit.status in ("completed", "failed") and not still_running:
            return
        if asyncio.get_event_loop().time() >= deadline:
            raise TimeoutError(f"Timed out waiting for audit {audit_id} to complete")
        await asyncio.sleep(interval_seconds)


async def send_monitoring_report(db: AsyncSession, project: Project, user: User) -> Audit:
    """Shared by the manual "send now" endpoint and the Celery Beat
    periodic task: runs a fresh audit, waits for it to fully finish,
    shares it, and emails a summary + link from the user's own connected
    Gmail to the configured recipient."""
    if not project.monitoring_recipient_email:
        raise MonitoringNotConfiguredError("Set a recipient email before sending a report.")

    audit = Audit(project_id=project.id, status="pending")
    db.add(audit)
    await db.commit()
    await db.refresh(audit)

    await run_audit(audit.id, project.domain)
    await _wait_for_completion(audit.id)
    await db.refresh(audit)

    if audit.share_token is None:
        audit.share_token = generate_share_token()
        await db.commit()

    audit = await compose_audit_out(db, audit, project)

    settings = get_settings()
    share_url = f"{settings.web_public_url}/report/{audit.share_token}"
    html = build_report_email_html(project, audit, share_url, project.monitoring_message)

    access_token = await get_google_access_token(user.id)
    await send_email(access_token, project.monitoring_recipient_email, f"SEO report for {project.domain}", html)

    project.monitoring_last_sent_at = datetime.now(UTC)
    await db.commit()
    return audit
