import re

import httpx
from bs4 import BeautifulSoup

from app.services.tools.base import Finding, ToolResult, register_tool
from app.services.tools.signatures import SIGNATURES

CONFIRMED_THRESHOLD = 80


def _match_signal(signal, html: str, headers: httpx.Headers, cookie_names: str, meta_generator: str) -> bool:
    if signal.source == "html":
        return bool(re.search(signal.pattern, html, re.IGNORECASE))
    if signal.source == "header":
        value = headers.get(signal.header_name or "", "")
        return bool(value) and bool(re.search(signal.pattern, value, re.IGNORECASE))
    if signal.source == "cookie":
        return bool(re.search(signal.pattern, cookie_names, re.IGNORECASE))
    if signal.source == "meta_generator":
        return bool(meta_generator) and bool(re.search(signal.pattern, meta_generator, re.IGNORECASE))
    return False


@register_tool("tech_checker")
async def run(domain: str) -> ToolResult:
    url = domain if domain.startswith("http") else f"https://{domain}"

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            resp = await client.get(url, headers={"User-Agent": "SEORepairKit/1.0 (+audit)"})
    except httpx.HTTPError as exc:
        return ToolResult(
            tool="tech_checker",
            status="error",
            score=None,
            findings=[Finding("critical", "fetch_failed", f"Could not fetch page: {exc}")],
            raw={"url": url},
        )

    html = resp.text
    soup = BeautifulSoup(html, "lxml")
    generator_tag = soup.find("meta", attrs={"name": "generator"})
    meta_generator = generator_tag.get("content", "") if generator_tag else ""
    cookie_names = " ".join(resp.headers.get_list("set-cookie"))

    detections = []
    for sig in SIGNATURES:
        score = 0
        for signal in sig.signals:
            if _match_signal(signal, html, resp.headers, cookie_names, meta_generator):
                score += signal.weight
        score = min(score, 100)
        if score > 0:
            detections.append(
                {
                    "name": sig.name,
                    "category": sig.category,
                    "confidence": score,
                    "status": "confirmed" if score >= CONFIRMED_THRESHOLD else "possible",
                }
            )

    detections.sort(key=lambda d: (d["status"] != "confirmed", -d["confidence"]))

    grouped: dict[str, list[dict]] = {}
    for d in detections:
        grouped.setdefault(d["category"], []).append(d)

    findings: list[Finding] = []
    if not detections:
        findings.append(
            Finding("info", "no_technologies_detected", "No known technology signatures matched this page")
        )

    raw = {"url": url, "detections": detections, "by_category": grouped, "status_code": resp.status_code}

    return ToolResult(tool="tech_checker", status="ok", score=None, findings=findings, raw=raw)
