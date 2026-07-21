import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.tools  # noqa: F401  (import triggers @register_tool side effects)
from app.core.config import get_settings
from app.core.db import get_db
from app.core.domain_safety import normalize_domain, validate_public_domain
from app.core.rate_limit import enforce_anonymous_scan_rate_limit, enforce_public_rate_limit
from app.core.share_tokens import generate_share_token
from app.models.audit import Audit, AuditResult
from app.models.project import Project
from app.models.user import User
from app.schemas import AuditOut, ScanCreate, ScanOut, ScanResultItem
from app.services.audit_view import compose_audit_out
from app.services.render_client import RenderError, render_pdf
from app.services.tools.base import TOOL_REGISTRY

# Fixed system row that owns every anonymous scan's Project/Audit -- lets
# anonymous scans get a real share_token (and therefore the existing
# share/PDF machinery) without inventing a parallel "ownerless" concept, and
# without ever matching a real Clerk user id (those are always "user_...").
ANONYMOUS_SCAN_USER_ID = "system_anonymous_scan_user"
ANONYMOUS_SCAN_USER_EMAIL = "anonymous-scan@system.local"

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


async def _run_tool_safe(name: str, fn, domain: str) -> dict:
    """Deliberately a small standalone helper rather than reusing
    orchestrator.run_audit's run_one: that version writes each AuditResult
    row incrementally as it completes (what makes dashboard polling show
    partial progress), a property this endpoint (which persists everything
    in one shot at the end, not incrementally) has no use for -- forcing a
    shared abstraction here would just entangle the two paths for no
    benefit. Returns the full result dict (including `raw`) so the caller
    can both build the API response and persist an AuditResult row from the
    same data -- `raw` is what feeds tech-stack/all-headers detail on the
    shared report page."""
    try:
        result = await fn(domain)
    except Exception as exc:  # noqa: BLE001 -- a broken tool must not sink the whole scan
        return {
            "tool": name,
            "status": "error",
            "score": None,
            "findings": [{"severity": "critical", "code": "tool_crashed", "message": str(exc)}],
            "raw": {},
        }
    return result.to_dict()


async def _get_or_create_anonymous_scan_user(db: AsyncSession) -> User:
    user = await db.get(User, ANONYMOUS_SCAN_USER_ID)
    if user is None:
        user = User(id=ANONYMOUS_SCAN_USER_ID, email=ANONYMOUS_SCAN_USER_EMAIL)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


@router.post("/scan", response_model=ScanOut)
async def scan_domain(
    payload: ScanCreate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(enforce_anonymous_scan_rate_limit),
) -> ScanOut:
    """Anonymous, no-login scan. Still runs only the fast tools
    (TOOL_REGISTRY already excludes Page Crawl, which is Celery-only) and
    still skips AI Visibility entirely -- that costs real per-call money
    with no per-user quota to meter an anonymous caller against, and this
    endpoint's own IP rate limit is the only thing bounding cost here.

    Unlike the original version of this endpoint, results *are* now
    persisted (as a real Project/Audit/AuditResult, owned by a fixed
    system "anonymous scan" user -- see ANONYMOUS_SCAN_USER_ID above) so a
    signed-out visitor can immediately share or download a PDF of their own
    scan via the same /public/audits/{share_token} machinery every other
    report already uses, without needing an account."""
    domain = normalize_domain(payload.domain)
    validate_public_domain(domain)

    result_dicts = await asyncio.gather(*(_run_tool_safe(name, fn, domain) for name, fn in TOOL_REGISTRY.items()))

    user = await _get_or_create_anonymous_scan_user(db)
    project = Project(user_id=user.id, domain=domain, is_competitor_only=True)
    db.add(project)
    await db.flush()

    audit = Audit(
        project_id=project.id,
        status="completed",
        completed_at=datetime.now(UTC),
        share_token=generate_share_token(),
    )
    db.add(audit)
    await db.flush()

    for result_dict in result_dicts:
        db.add(
            AuditResult(
                audit_id=audit.id,
                tool=result_dict["tool"],
                status=result_dict["status"],
                score=result_dict["score"],
                findings=result_dict["findings"],
                raw=result_dict["raw"],
            )
        )
    await db.commit()

    settings = get_settings()
    return ScanOut(
        domain=domain,
        results=[
            ScanResultItem(
                tool=rd["tool"], status=rd["status"], score=rd["score"], findings=rd["findings"]
            )
            for rd in result_dicts
        ],
        share_token=audit.share_token,
        share_url=f"{settings.web_public_url}/report/{audit.share_token}",
    )
