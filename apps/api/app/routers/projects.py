import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_or_api_key
from app.core.db import get_db
from app.core.domain_safety import normalize_domain
from app.core.rate_limit import enforce_rate_limit
from app.models.audit import Audit
from app.models.project import MONITORING_FREQUENCIES, Project
from app.models.user import User
from app.schemas import AuditOut, AuditSummaryOut, MonitoringOut, MonitoringUpdate, ProjectCreate, ProjectOut
from app.services.gmail_sender import GmailNotConnectedError
from app.services.monitoring import MonitoringNotConfiguredError, compute_next_run_at, send_monitoring_report

router = APIRouter(prefix="/projects", tags=["projects"])


async def _get_owned_project(db: AsyncSession, user: User, project_id: uuid.UUID) -> Project:
    project = await db.get(Project, project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


@router.post("", response_model=ProjectOut)
async def create_project(
    payload: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_or_api_key),
    _: None = Depends(enforce_rate_limit),
) -> Project:
    project = Project(
        user_id=user.id,
        domain=normalize_domain(payload.domain),
        brand_name=payload.brand_name,
        is_competitor_only=payload.is_competitor_only,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_or_api_key),
    _: None = Depends(enforce_rate_limit),
) -> list[Project]:
    result = await db.scalars(
        select(Project)
        .where(Project.user_id == user.id, Project.is_competitor_only.is_(False))
        .order_by(Project.created_at.desc())
    )
    return list(result)


@router.get("/{project_id}/audits", response_model=list[AuditSummaryOut])
async def list_project_audits(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_or_api_key),
    _: None = Depends(enforce_rate_limit),
) -> list[Audit]:
    await _get_owned_project(db, user, project_id)

    result = await db.scalars(select(Audit).where(Audit.project_id == project_id).order_by(Audit.created_at.desc()))
    return list(result)


@router.get("/{project_id}/monitoring", response_model=MonitoringOut)
async def get_monitoring(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_or_api_key),
    _: None = Depends(enforce_rate_limit),
) -> Project:
    return await _get_owned_project(db, user, project_id)


@router.put("/{project_id}/monitoring", response_model=MonitoringOut)
async def update_monitoring(
    project_id: uuid.UUID,
    payload: MonitoringUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_or_api_key),
    _: None = Depends(enforce_rate_limit),
) -> Project:
    project = await _get_owned_project(db, user, project_id)

    if payload.enabled:
        if payload.frequency not in MONITORING_FREQUENCIES:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"frequency must be one of {MONITORING_FREQUENCIES}"
            )
        if not payload.recipient_email:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "recipient_email is required to enable monitoring")
        project.monitoring_next_run_at = compute_next_run_at(payload.frequency)
    else:
        project.monitoring_next_run_at = None

    project.monitoring_enabled = payload.enabled
    project.monitoring_frequency = payload.frequency
    project.monitoring_recipient_email = payload.recipient_email
    project.monitoring_message = payload.message
    await db.commit()
    await db.refresh(project)
    return project


@router.post("/{project_id}/monitoring/send-now", response_model=AuditOut)
async def send_monitoring_report_now(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_or_api_key),
    _: None = Depends(enforce_rate_limit),
) -> Audit:
    project = await _get_owned_project(db, user, project_id)
    try:
        return await send_monitoring_report(db, project, user)
    except GmailNotConnectedError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except MonitoringNotConfiguredError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
