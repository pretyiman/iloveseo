import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import Audit, AuditResult


async def get_previous_results_by_tool(
    db: AsyncSession, project_id: uuid.UUID, current_audit_id: uuid.UUID
) -> dict[str, AuditResult]:
    """Results from the most recent *other* completed audit for this
    project, keyed by tool name -- the baseline the current audit is
    diffed against."""
    previous_audit = await db.scalar(
        select(Audit)
        .where(Audit.project_id == project_id, Audit.id != current_audit_id, Audit.status == "completed")
        .order_by(Audit.created_at.desc())
        .limit(1)
    )
    if previous_audit is None:
        return {}

    results = await db.scalars(select(AuditResult).where(AuditResult.audit_id == previous_audit.id))
    return {r.tool: r for r in results}


def diff_result(current: AuditResult, previous: AuditResult | None) -> dict | None:
    if previous is None:
        return None

    current_codes = {f["code"] for f in (current.findings or [])}
    previous_codes = {f["code"] for f in (previous.findings or [])}

    score_delta = None
    if current.score is not None and previous.score is not None:
        score_delta = current.score - previous.score

    return {
        "previous_score": previous.score,
        "score_delta": score_delta,
        "new_finding_codes": sorted(current_codes - previous_codes),
        "resolved_finding_codes": sorted(previous_codes - current_codes),
    }
