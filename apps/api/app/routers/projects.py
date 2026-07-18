from urllib.parse import urlparse

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.project import Project
from app.models.user import User
from app.schemas import ProjectCreate, ProjectOut

router = APIRouter(prefix="/projects", tags=["projects"])


def _normalize_domain(value: str) -> str:
    value = value.strip()
    if "://" in value:
        value = urlparse(value).netloc or value
    return value.rstrip("/").removeprefix("www.")


@router.post("", response_model=ProjectOut)
async def create_project(
    payload: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Project:
    project = Project(user_id=user.id, domain=_normalize_domain(payload.domain))
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Project]:
    result = await db.scalars(select(Project).where(Project.user_id == user.id).order_by(Project.created_at.desc()))
    return list(result)
