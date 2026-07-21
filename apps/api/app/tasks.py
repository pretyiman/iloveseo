import asyncio
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.db import SessionLocal, engine
from app.models.audit import AuditResult
from app.models.project import Project
from app.models.user import User
from app.services.crawl import build_tool_result, crawl_site

logger = logging.getLogger(__name__)


@celery_app.task(name="run_page_crawl")
def run_page_crawl_task(audit_result_id: str, domain: str) -> None:
    asyncio.run(_run_page_crawl_and_cleanup(uuid.UUID(audit_result_id), domain))


async def _run_page_crawl_and_cleanup(audit_result_id: uuid.UUID, domain: str) -> None:
    try:
        await _run_page_crawl(audit_result_id, domain)
    finally:
        # Celery (--pool=solo, and prefork workers too) runs many tasks
        # sequentially in one process, each via its own asyncio.run() /
        # event loop. SQLAlchemy's async engine pools asyncpg connections
        # bound to the loop that created them -- reusing that pool from a
        # closed loop in the *next* task's loop produces "Event loop is
        # closed" / "NoneType has no attribute 'send'" failures. Disposing
        # here, inside the same loop the connections were opened on, drops
        # the pool cleanly so the next task's loop starts with fresh ones.
        await engine.dispose()


async def _run_page_crawl(audit_result_id: uuid.UUID, domain: str) -> None:
    max_pages = get_settings().page_crawl_max_pages

    async def on_progress(done: int, total: int) -> None:
        async with SessionLocal() as db:
            result = await db.get(AuditResult, audit_result_id)
            if result:
                result.progress = {"pages_crawled": done, "pages_total_estimate": total}
                await db.commit()

    try:
        crawl_data = await crawl_site(domain, max_pages, on_progress=on_progress)
        tool_result = build_tool_result(crawl_data)
    except Exception as exc:  # noqa: BLE001 -- must still resolve the row, not leave it stuck at "running"
        async with SessionLocal() as db:
            result = await db.get(AuditResult, audit_result_id)
            if result:
                result.status = "error"
                result.findings = [{"severity": "critical", "code": "crawl_failed", "message": str(exc)}]
                result.progress = None
                await db.commit()
        return

    async with SessionLocal() as db:
        result = await db.get(AuditResult, audit_result_id)
        if result:
            result.status = tool_result.status
            result.score = tool_result.score
            result.findings = [f.__dict__ for f in tool_result.findings]
            result.raw = tool_result.raw
            result.progress = None
            await db.commit()


@celery_app.task(name="run_due_monitoring_reports")
def run_due_monitoring_reports_task() -> None:
    asyncio.run(_run_due_monitoring_reports_and_cleanup())


async def _run_due_monitoring_reports_and_cleanup() -> None:
    try:
        await _run_due_monitoring_reports()
    finally:
        await engine.dispose()


async def _run_due_monitoring_reports() -> None:
    """Beat-scheduled, hourly: finds every project whose monitoring
    schedule has come due and sends its report, reusing the exact same
    `send_monitoring_report` the manual "send now" endpoint calls. Each
    project gets its own session/commit so one failure (e.g. Gmail not
    connected, or a transient audit error) can't roll back or block the
    rest of the batch -- and `monitoring_next_run_at` is advanced either
    way, so a persistently-failing project retries next cycle instead of
    being hammered every Beat tick."""
    # Deferred import: app.services.monitoring -> app.services.orchestrator
    # -> app.tasks (to dispatch the Page Crawl task) would otherwise be a
    # circular import at module load time.
    from app.services.monitoring import compute_next_run_at, send_monitoring_report

    now = datetime.now(UTC)
    async with SessionLocal() as db:
        due_project_ids = list(
            await db.scalars(
                select(Project.id).where(
                    Project.monitoring_enabled.is_(True),
                    Project.monitoring_next_run_at <= now,
                )
            )
        )

    for project_id in due_project_ids:
        async with SessionLocal() as db:
            project = await db.get(Project, project_id)
            if project is None or not project.monitoring_enabled:
                continue
            user = await db.get(User, project.user_id)
            try:
                if user is None:
                    raise RuntimeError(f"No user found for project {project.id}")
                await send_monitoring_report(db, project, user)
            except Exception:
                logger.exception("Scheduled monitoring report failed for project %s", project.id)
            finally:
                if project.monitoring_frequency:
                    project.monitoring_next_run_at = compute_next_run_at(project.monitoring_frequency)
                    await db.commit()
