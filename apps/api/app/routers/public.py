import asyncio

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.tools  # noqa: F401  (import triggers @register_tool side effects)
from app.core.config import get_settings
from app.core.db import get_db
from app.core.domain_safety import normalize_domain, validate_public_domain
from app.core.rate_limit import enforce_anonymous_scan_rate_limit, enforce_public_rate_limit
from app.models.audit import Audit
from app.models.project import Project
from app.schemas import AuditOut, ScanCreate, ScanOut, ScanResultItem
from app.services.audit_view import compose_audit_out
from app.services.render_client import RenderError, render_pdf
from app.services.tools.base import TOOL_REGISTRY

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


async def _run_tool_safe(name: str, fn, domain: str) -> ScanResultItem:
    """Deliberately a small standalone helper rather than reusing
    orchestrator.run_audit's run_one: that version writes each AuditResult
    row incrementally as it completes (what makes dashboard polling show
    partial progress), a property this stateless, no-DB-writes endpoint
    has no use for -- forcing a shared abstraction here would just
    entangle the two paths for no benefit."""
    try:
        result = await fn(domain)
    except Exception as exc:  # noqa: BLE001 -- a broken tool must not sink the whole scan
        return ScanResultItem(
            tool=name,
            status="error",
            score=None,
            findings=[{"severity": "critical", "code": "tool_crashed", "message": str(exc)}],
        )
    result_dict = result.to_dict()
    return ScanResultItem(
        tool=result_dict["tool"], status=result_dict["status"], score=result_dict["score"], findings=result_dict["findings"]
    )


@router.post("/scan", response_model=ScanOut)
async def scan_domain(
    payload: ScanCreate,
    _: None = Depends(enforce_anonymous_scan_rate_limit),
) -> ScanOut:
    """Anonymous, no-login, nothing-persisted scan -- no Project/Audit rows
    are created at all. Runs only the fast tools (TOOL_REGISTRY already
    excludes Page Crawl, which is Celery-only) and skips AI Visibility
    entirely, since that costs real per-call money with no per-user quota
    to meter an anonymous caller against."""
    domain = normalize_domain(payload.domain)
    validate_public_domain(domain)

    results = await asyncio.gather(*(_run_tool_safe(name, fn, domain) for name, fn in TOOL_REGISTRY.items()))
    return ScanOut(domain=domain, results=list(results))
