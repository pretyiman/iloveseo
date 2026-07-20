import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_or_api_key
from app.core.db import get_db
from app.core.domain_safety import normalize_domain
from app.core.rate_limit import enforce_rate_limit
from app.models.audit import Audit
from app.models.project import Project
from app.models.user import User
from app.schemas import AuditSummaryOut, ProjectCreate, ProjectOut

router = APIRouter(prefix="/projects", tags=["projects"])


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
    project = await db.get(Project, project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

    result = await db.scalars(select(Audit).where(Audit.project_id == project_id).order_by(Audit.created_at.desc()))
    return list(result)
