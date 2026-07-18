import asyncio
from datetime import datetime

import httpx
from lxml import etree

from app.services.tools.base import Finding, ToolResult, register_tool, score_from_findings

COMMON_SITEMAP_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap/sitemap.xml",
    "/wp-sitemap.xml",
    "/sitemap1.xml",
]

MAX_URLS_PER_SITEMAP = 50_000
MAX_BYTES_PER_SITEMAP = 50 * 1024 * 1024
CHILD_SITEMAP_SAMPLE_SIZE = 5


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


async def _find_sitemaps_from_robots(client: httpx.AsyncClient, base: str) -> list[str]:
    try:
        resp = await client.get(f"{base}/robots.txt")
    except httpx.HTTPError:
        return []
    if resp.status_code >= 400:
        return []
    sitemaps = []
    for line in resp.text.splitlines():
        field, _, value = line.partition(":")
        if field.strip().lower() == "sitemap" and value.strip():
            sitemaps.append(value.strip())
    return sitemaps


async def _probe_common_paths(client: httpx.AsyncClient, base: str) -> tuple[str | None, list[str]]:
    tried = []
    for path in COMMON_SITEMAP_PATHS:
        candidate = f"{base}{path}"
        tried.append(candidate)
        try:
            resp = await client.get(candidate)
        except httpx.HTTPError:
            continue
        if resp.status_code < 400:
            return candidate, tried
    return None, tried


def _validate_lastmod(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


async def _analyze_sitemap(client: httpx.AsyncClient, url: str, findings: list[Finding]) -> dict:
    try:
        resp = await client.get(url)
    except httpx.HTTPError as exc:
        findings.append(Finding("high", "sitemap_fetch_failed", f"Could not fetch sitemap {url}: {exc}"))
        return {"url": url, "error": str(exc)}

    if resp.status_code >= 400:
        findings.append(Finding("high", "sitemap_fetch_failed", f"Sitemap {url} returned {resp.status_code}"))
        return {"url": url, "status_code": resp.status_code}

    size_bytes = len(resp.content)
    if size_bytes > MAX_BYTES_PER_SITEMAP:
        findings.append(
            Finding("medium", "sitemap_too_large", f"Sitemap {url} is {size_bytes} bytes, over the 50MB uncompressed limit")
        )

    try:
        root = etree.fromstring(resp.content)
    except etree.XMLSyntaxError as exc:
        findings.append(Finding("critical", "sitemap_malformed_xml", f"Sitemap {url} is not valid XML: {exc}"))
        return {"url": url, "size_bytes": size_bytes, "malformed": True}

    root_tag = _localname(root.tag)

    if root_tag == "sitemapindex":
        child_locs = [_localname_find_text(child) for child in root if _localname(child.tag) == "sitemap"]
        child_locs = [loc for loc in child_locs if loc]
        sample = child_locs[:CHILD_SITEMAP_SAMPLE_SIZE]
        sampled_counts = await asyncio.gather(*(_count_urls_in_sitemap(client, loc) for loc in sample))
        valid_counts = [c for c in sampled_counts if c is not None]
        estimated_total = None
        if valid_counts:
            avg = sum(valid_counts) / len(valid_counts)
            estimated_total = round(avg * len(child_locs))

        return {
            "url": url,
            "type": "sitemapindex",
            "size_bytes": size_bytes,
            "child_sitemap_count": len(child_locs),
            "sampled_child_sitemaps": len(sample),
            "estimated_total_urls": estimated_total,
        }

    if root_tag == "urlset":
        url_entries = [child for child in root if _localname(child.tag) == "url"]
        url_count = len(url_entries)
        if url_count > MAX_URLS_PER_SITEMAP:
            findings.append(
                Finding("medium", "sitemap_too_many_urls", f"Sitemap {url} has {url_count} URLs, over the 50,000 limit -- split it")
            )

        bad_lastmods = 0
        checked = 0
        for entry in url_entries[:200]:  # sampling cap so a huge sitemap doesn't block the scan
            lastmod_el = next((c for c in entry if _localname(c.tag) == "lastmod"), None)
            if lastmod_el is not None and lastmod_el.text:
                checked += 1
                if not _validate_lastmod(lastmod_el.text.strip()):
                    bad_lastmods += 1
        if bad_lastmods:
            findings.append(
                Finding("low", "sitemap_invalid_lastmod", f"{bad_lastmods} of {checked} sampled <lastmod> values aren't valid dates")
            )

        return {"url": url, "type": "urlset", "size_bytes": size_bytes, "url_count": url_count}

    findings.append(Finding("medium", "sitemap_unrecognized_root", f"Sitemap {url} has unrecognized root element <{root_tag}>"))
    return {"url": url, "type": root_tag, "size_bytes": size_bytes}


def _localname_find_text(el) -> str | None:
    loc_el = next((c for c in el if _localname(c.tag) == "loc"), None)
    return loc_el.text.strip() if loc_el is not None and loc_el.text else None


async def _count_urls_in_sitemap(client: httpx.AsyncClient, url: str) -> int | None:
    try:
        resp = await client.get(url)
        if resp.status_code >= 400:
            return None
        root = etree.fromstring(resp.content)
        return sum(1 for child in root if _localname(child.tag) == "url")
    except (httpx.HTTPError, etree.XMLSyntaxError):
        return None


@register_tool("sitemap")
async def run(domain: str) -> ToolResult:
    base = domain if domain.startswith("http") else f"https://{domain}"
    findings: list[Finding] = []
    raw: dict = {"base_url": base}

    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        declared = await _find_sitemaps_from_robots(client, base)

        if declared:
            raw["discovery_method"] = "robots.txt"
            sitemap_urls = declared
        else:
            found, tried = await _probe_common_paths(client, base)
            raw["paths_tried"] = tried
            if found:
                raw["discovery_method"] = "common_path"
                sitemap_urls = [found]
                findings.append(
                    Finding("low", "sitemap_not_in_robots", "Sitemap exists but isn't declared in robots.txt")
                )
            else:
                raw["discovery_method"] = None
                sitemap_urls = []

        if not sitemap_urls:
            findings.append(Finding("high", "sitemap_not_found", "No XML sitemap found via robots.txt or common paths"))
            raw["sitemaps"] = []
            return ToolResult(tool="sitemap", status="ok", score=score_from_findings(findings), findings=findings, raw=raw)

        analyses = []
        for sitemap_url in sitemap_urls:
            analyses.append(await _analyze_sitemap(client, sitemap_url, findings))
        raw["sitemaps"] = analyses

    return ToolResult(tool="sitemap", status="ok", score=score_from_findings(findings), findings=findings, raw=raw)
