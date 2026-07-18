import asyncio
import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.services.tools.base import Finding, ToolResult, register_tool, score_from_findings

MAX_RECIPROCITY_CHECKS = 10
# Simplified BCP47: language(-script)(-region), or the literal x-default.
LOCALE_PATTERN = re.compile(r"^[a-zA-Z]{2,3}(-[a-zA-Z]{4})?(-([a-zA-Z]{2}|\d{3}))?$")


def _is_valid_locale(value: str) -> bool:
    if value.lower() == "x-default":
        return True
    return bool(LOCALE_PATTERN.match(value))


def _extract_hreflang_links(soup: BeautifulSoup, base_url: str) -> list[dict]:
    links = []
    for tag in soup.find_all("link", rel="alternate"):
        hreflang = tag.get("hreflang")
        href = tag.get("href")
        if hreflang and href:
            links.append({"hreflang": hreflang.strip(), "href": urljoin(base_url, href)})
    return links


async def _check_reciprocity(client: httpx.AsyncClient, original_url: str, alt: dict) -> bool | None:
    try:
        resp = await client.get(alt["href"], headers={"User-Agent": "SEORepairKit/1.0 (+audit)"}, timeout=10)
        soup = BeautifulSoup(resp.text, "lxml")
        back_links = _extract_hreflang_links(soup, str(resp.url))
        normalized_original = original_url.rstrip("/")
        return any(link["href"].rstrip("/") == normalized_original for link in back_links)
    except httpx.HTTPError:
        return None  # couldn't verify -- doesn't count as a failure


@register_tool("hreflang")
async def run(domain: str) -> ToolResult:
    url = domain if domain.startswith("http") else f"https://{domain}"
    findings: list[Finding] = []

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            resp = await client.get(url, headers={"User-Agent": "SEORepairKit/1.0 (+audit)"})
    except httpx.HTTPError as exc:
        return ToolResult(
            tool="hreflang",
            status="error",
            score=None,
            findings=[Finding("critical", "fetch_failed", f"Could not fetch page: {exc}")],
            raw={"url": url},
        )

    soup = BeautifulSoup(resp.text, "lxml")
    page_url = str(resp.url)
    links = _extract_hreflang_links(soup, page_url)
    raw: dict = {"url": page_url, "hreflang_count": len(links), "links": links}

    if not links:
        findings.append(Finding("info", "no_hreflang", "No hreflang tags found on this page"))
        return ToolResult(tool="hreflang", status="ok", score=score_from_findings(findings), findings=findings, raw=raw)

    invalid = [link for link in links if not _is_valid_locale(link["hreflang"])]
    if invalid:
        bad_codes = ", ".join(sorted({link["hreflang"] for link in invalid}))
        findings.append(Finding("high", "invalid_locale_code", f"Invalid hreflang locale code(s): {bad_codes}"))

    if any(link["hreflang"].lower() == "uk" for link in links):
        findings.append(
            Finding(
                "low",
                "uk_locale_confusion",
                "hreflang='uk' means Ukrainian (ISO 639-1), not United Kingdom -- use 'en-gb' for UK English",
            )
        )

    by_code: dict[str, set[str]] = {}
    for link in links:
        by_code.setdefault(link["hreflang"].lower(), set()).add(link["href"].rstrip("/"))
    conflicts = {code: hrefs for code, hrefs in by_code.items() if len(hrefs) > 1}
    if conflicts:
        findings.append(
            Finding(
                "high",
                "conflicting_hreflang",
                f"{len(conflicts)} hreflang code(s) point to multiple different URLs: {', '.join(sorted(conflicts))}",
            )
        )

    has_x_default = any(link["hreflang"].lower() == "x-default" for link in links)
    locale_specific_count = sum(1 for link in links if link["hreflang"].lower() != "x-default")
    if locale_specific_count > 1 and not has_x_default:
        findings.append(Finding("low", "missing_x_default", "Multiple locale variants declared but no x-default hreflang"))

    self_referencing = any(link["href"].rstrip("/") == page_url.rstrip("/") for link in links)
    if not self_referencing:
        findings.append(Finding("medium", "missing_self_reference", "Page doesn't include a self-referencing hreflang tag"))

    to_check = [link for link in links if link["href"].rstrip("/") != page_url.rstrip("/")][:MAX_RECIPROCITY_CHECKS]
    async with httpx.AsyncClient(follow_redirects=True) as client:
        results = await asyncio.gather(*(_check_reciprocity(client, page_url, link) for link in to_check))
    non_reciprocal = [link["href"] for link, ok in zip(to_check, results) if ok is False]
    raw["reciprocity_checked"] = len(to_check)
    raw["non_reciprocal_urls"] = non_reciprocal
    if non_reciprocal:
        findings.append(
            Finding("medium", "non_reciprocal_hreflang", f"{len(non_reciprocal)} alternate URLs don't link back to this page")
        )

    return ToolResult(tool="hreflang", status="ok", score=score_from_findings(findings), findings=findings, raw=raw)
