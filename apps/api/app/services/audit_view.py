from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import Audit, AuditResult
from app.models.project import Project
from app.services.diffing import diff_result, get_previous_results_by_tool
from app.services.geo.auto_check import build_ai_visibility_summary


async def compose_audit_out(db: AsyncSession, audit: Audit, project: Project) -> Audit:
    """Attaches results (diffed against the project's previous audit) and
    an AI Visibility summary to an already-fetched Audit -- shared by every
    read path that returns a full AuditOut: the owned GET /audits/{id},
    GET /audits/compare, and the public GET /public/audits/{share_token}."""
    results = list(
        await db.scalars(
            select(AuditResult).where(AuditResult.audit_id == audit.id).order_by(AuditResult.created_at)
        )
    )
    previous_by_tool = await get_previous_results_by_tool(db, audit.project_id, audit.id)
    for result in results:
        result.diff = diff_result(result, previous_by_tool.get(result.tool))

    audit.results = results
    audit.ai_visibility = await build_ai_visibility_summary(db, project)
    return audit
