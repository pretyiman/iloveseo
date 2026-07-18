import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_db
from app.core.plan_limits import check_and_increment_usage
from app.models.audit import Audit, AuditResult
from app.models.project import Project
from app.models.user import User
from app.schemas import AuditCreate, AuditOut
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
    user: User = Depends(get_current_user),
) -> Audit:
    project = await _get_owned_project(db, user, payload.project_id)
    await check_and_increment_usage(db, user)

    audit = Audit(project_id=project.id, status="pending")
    db.add(audit)
    await db.commit()
    await db.refresh(audit)

    background_tasks.add_task(run_audit, audit.id, project.domain)

    audit.results = []
    return audit


@router.get("/{audit_id}", response_model=AuditOut)
async def get_audit(
    audit_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Audit:
    audit = await db.get(Audit, audit_id)
    if audit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Audit not found")

    project = await db.get(Project, audit.project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Audit not found")

    results = await db.scalars(
        select(AuditResult).where(AuditResult.audit_id == audit_id).order_by(AuditResult.created_at)
    )
    audit.results = list(results)
    return audit
