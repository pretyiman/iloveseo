import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_or_api_key
from app.core.config import get_settings
from app.core.db import get_db
from app.core.plan_limits import check_and_increment_usage
from app.core.rate_limit import enforce_rate_limit
from app.core.share_tokens import generate_share_token
from app.models.audit import Audit
from app.models.project import Project
from app.models.user import User
from app.schemas import AuditCompareOut, AuditCreate, AuditOut, AuditShareOut
from app.services.audit_view import compose_audit_out
from app.services.diffing import diff_result
from app.services.orchestrator import run_audit

router = APIRouter(prefix="/audits", tags=["audits"])


async def _get_owned_project(db: AsyncSession, user: User, project_id: uuid.UUID) -> Project:
    project = await db.get(Project, project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


@router.post("", response_model=AuditOut)
async def create_audit(
    payload: AuditCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_or_api_key),
    _: None = Depends(enforce_rate_limit),
) -> Audit:
    project = await _get_owned_project(db, user, payload.project_id)
    await check_and_increment_usage(db, user)

    audit = Audit(project_id=project.id, status="pending")
    db.add(audit)
    await db.commit()
    await db.refresh(audit)

    background_tasks.add_task(run_audit, audit.id, project.domain)

    audit.results = []
    audit.ai_visibility = None
    return audit


async def _load_full_audit(db: AsyncSession, user: User, audit_id: uuid.UUID) -> Audit:
    """Shared by GET /audits/{id} and GET /audits/compare -- fetches an
    owned audit with its results (diffed against the project's own
    previous audit) and AI Visibility summary attached."""
    audit = await db.get(Audit, audit_id)
    if audit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Audit not found")

    project = await db.get(Project, audit.project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Audit not found")

    return await compose_audit_out(db, audit, project)


@router.get("/compare", response_model=AuditCompareOut)
async def compare_audits(
    a: uuid.UUID,
    b: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_or_api_key),
    _: None = Depends(enforce_rate_limit),
) -> AuditCompareOut:
    audit_a = await _load_full_audit(db, user, a)
    audit_b = await _load_full_audit(db, user, b)

    results_b_by_tool = {r.tool: r for r in audit_b.results}
    diff_by_tool = {
        result_a.tool: diff_result(result_a, results_b_by_tool.get(result_a.tool)) for result_a in audit_a.results
    }

    return AuditCompareOut(
        audit_a=AuditOut.model_validate(audit_a),
        audit_b=AuditOut.model_validate(audit_b),
        diff_by_tool=diff_by_tool,
    )


@router.get("/{audit_id}", response_model=AuditOut)
async def get_audit(
    audit_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_or_api_key),
    _: None = Depends(enforce_rate_limit),
) -> Audit:
    return await _load_full_audit(db, user, audit_id)


async def _get_owned_audit(db: AsyncSession, user: User, audit_id: uuid.UUID) -> Audit:
    audit = await db.get(Audit, audit_id)
    if audit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Audit not found")
    project = await db.get(Project, audit.project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Audit not found")
    return audit


@router.post("/{audit_id}/share", response_model=AuditShareOut)
async def share_audit(
    audit_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_or_api_key),
    _: None = Depends(enforce_rate_limit),
) -> AuditShareOut:
    """Idempotent -- returns the existing share link if this audit is
    already shared, otherwise mints one. Also used by "Download PDF" in the
    dashboard, since the render sidecar can only render a public URL."""
    audit = await _get_owned_audit(db, user, audit_id)
    if audit.share_token is None:
        audit.share_token = generate_share_token()
        await db.commit()

    settings = get_settings()
    return AuditShareOut(share_token=audit.share_token, share_url=f"{settings.web_public_url}/report/{audit.share_token}")


@router.delete("/{audit_id}/share", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_audit_share(
    audit_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_or_api_key),
    _: None = Depends(enforce_rate_limit),
) -> None:
    audit = await _get_owned_audit(db, user, audit_id)
    audit.share_token = None
    await db.commit()
