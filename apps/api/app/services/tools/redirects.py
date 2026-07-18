import time
from urllib.parse import urljoin, urlparse

import httpx

from app.services.tools.base import Finding, ToolResult, register_tool, score_from_findings

MAX_HOPS = 10
PERMANENT_CODES = {301, 308}
TEMPORARY_CODES = {302, 303, 307}


def _classify(status_code: int) -> str:
    if status_code in PERMANENT_CODES:
        return "permanent"
    if status_code in TEMPORARY_CODES:
        return "temporary"
    return "terminal"


@register_tool("redirects")
async def run(domain: str) -> ToolResult:
    url = domain if domain.startswith("http") else f"https://{domain}"
    findings: list[Finding] = []
    hops: list[dict] = []
    visited: set[str] = set()

    async with httpx.AsyncClient(follow_redirects=False, timeout=15) as client:
        current = url
        for _ in range(MAX_HOPS):
            if current in visited:
                findings.append(Finding("critical", "redirect_loop", f"Redirect loop detected at {current}"))
                break
            visited.add(current)

            start = time.monotonic()
            try:
                resp = await client.get(current, headers={"User-Agent": "SEORepairKit/1.0 (+audit)"})
            except httpx.HTTPError as exc:
                if not hops:
                    return ToolResult(
                        tool="redirects",
                        status="error",
                        score=None,
                        findings=[Finding("critical", "fetch_failed", f"Could not fetch page: {exc}")],
                        raw={"url": url},
                    )
                findings.append(Finding("high", "hop_fetch_failed", f"Could not fetch {current}: {exc}"))
                break
            elapsed_ms = round((time.monotonic() - start) * 1000)

            hop_type = _classify(resp.status_code)
            location = resp.headers.get("location")
            hops.append(
                {
                    "url": current,
                    "status_code": resp.status_code,
                    "type": hop_type,
                    "location": location,
                    "response_time_ms": elapsed_ms,
                }
            )

            if hop_type == "terminal" or not location:
                break
            current = urljoin(current, location)
        else:
            findings.append(
                Finding("high", "too_many_hops", f"Redirect chain exceeds {MAX_HOPS} hops, likely broken")
            )

    redirect_hops = [h for h in hops if h["type"] != "terminal"]
    if len(redirect_hops) > 2:
        findings.append(
            Finding("medium", "long_redirect_chain", f"Redirect chain has {len(redirect_hops)} hops (recommended: <=2)")
        )
    if any(h["type"] == "temporary" for h in redirect_hops):
        findings.append(
            Finding("medium", "temporary_redirect", "Chain includes a temporary (302/303/307) redirect")
        )

    final_url = hops[-1]["url"] if hops else url
    final_is_https = urlparse(final_url).scheme == "https"
    if not final_is_https:
        findings.append(Finding("medium", "final_destination_not_https", "Final destination is not served over HTTPS"))

    raw = {"url": url, "hops": hops, "final_url": final_url, "final_is_https": final_is_https, "hop_count": len(redirect_hops)}

    return ToolResult(tool="redirects", status="ok", score=score_from_findings(findings), findings=findings, raw=raw)
