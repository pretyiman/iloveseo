import asyncio
import uuid
from datetime import UTC, datetime

import app.services.tools  # noqa: F401  (import triggers @register_tool side effects)
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models.audit import Audit, AuditResult
from app.models.project import Project
from app.services.geo.auto_check import run_default_geo_check
from app.services.tools.base import TOOL_REGISTRY
from app.tasks import run_page_crawl_task


async def run_audit(audit_id: uuid.UUID, domain: str) -> None:
    """Fans out every registered fast tool concurrently against `domain` and
    writes each AuditResult row as soon as that tool finishes, so a client
    polling GET /audits/{id} sees results appear incrementally rather than
    waiting for the slowest tool. Runs as a FastAPI BackgroundTask, so it
    needs its own DB session -- it outlives the request that started it.

    Page Crawl is dispatched separately as a Celery task rather than joining
    the asyncio.gather batch below: a full-site crawl can take minutes, so it
    gets its own AuditResult row (status="running", with incremental
    `progress`) that the Celery worker updates independently. It's kicked
    off immediately, before the fast batch, so it isn't delayed by it -- but
    the overall Audit.status flips to "completed" as soon as the fast batch
    finishes, regardless of whether the crawl is still running.

    After the fast batch, also runs a best-effort AI Visibility (GEO) check
    for the project (see app/services/geo/auto_check.py) -- folded into every
    audit rather than a separate manual step, per product decision. Never
    allowed to fail or delay the audit itself.
    """
    async with SessionLocal() as db:
        audit = await db.get(Audit, audit_id)
        if audit is None:
            return
        project = await db.get(Project, audit.project_id)
        audit.status = "running"

        crawl_result = AuditResult(
            audit_id=audit_id,
            tool="page_crawl",
            status="running",
            score=None,
            findings=[],
            raw={},
            progress={"pages_crawled": 0, "pages_total_estimate": get_settings().page_crawl_max_pages},
        )
        db.add(crawl_result)
        await db.commit()
        await db.refresh(crawl_result)
        run_page_crawl_task.delay(str(crawl_result.id), domain)

        async def run_one(name: str, fn) -> None:
            try:
                result = await fn(domain)
            except Exception as exc:  # noqa: BLE001 -- a broken tool must not sink the whole audit
                result_dict = {
                    "tool": name,
                    "status": "error",
                    "score": None,
                    "findings": [
                        {"severity": "critical", "code": "tool_crashed", "message": str(exc)}
                    ],
                    "raw": {},
                }
            else:
                result_dict = result.to_dict()

            async with SessionLocal() as write_db:
                write_db.add(
                    AuditResult(
                        audit_id=audit_id,
                        tool=result_dict["tool"],
                        status=result_dict["status"],
                        score=result_dict["score"],
                        findings=result_dict["findings"],
                        raw=result_dict["raw"],
                    )
                )
                await write_db.commit()

        await asyncio.gather(*(run_one(name, fn) for name, fn in TOOL_REGISTRY.items()))

        if project is not None:
            await run_default_geo_check(db, project)

        audit.status = "completed"
        audit.completed_at = datetime.now(UTC)
        await db.commit()
