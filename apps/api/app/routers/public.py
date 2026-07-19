from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.rate_limit import enforce_public_rate_limit
from app.models.audit import Audit
from app.models.project import Project
from app.schemas import AuditOut
from app.services.audit_view import compose_audit_out
from app.services.render_client import RenderError, render_pdf

# Deliberately no auth dependency anywhere in this router -- a share_token
# itself *is* the access grant (see app/core/share_tokens.py), the same way
# a "anyone with the link" doc share works.
router = APIRouter(prefix="/public", tags=["public"])


async def _get_shared_audit(db: AsyncSession, share_token: str) -> tuple[Audit, Project]:
    audit = await db.scalar(select(Audit).where(Audit.share_token == share_token))
    if audit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    project = await db.get(Project, audit.project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    return audit, project


@router.get("/audits/{share_token}", response_model=AuditOut)
async def get_shared_audit(
    share_token: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(enforce_public_rate_limit),
) -> Audit:
    audit, project = await _get_shared_audit(db, share_token)
    return await compose_audit_out(db, audit, project)


@router.get("/audits/{share_token}/pdf")
async def get_shared_audit_pdf(
    share_token: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(enforce_public_rate_limit),
) -> Response:
    audit, project = await _get_shared_audit(db, share_token)
    settings = get_settings()
    try:
        pdf_bytes = await render_pdf(f"{settings.web_public_url}/report/{share_token}")
    except RenderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"PDF rendering failed: {exc}") from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{project.domain}-seo-audit.pdf"'},
    )
