import json
from collections.abc import Iterator

import httpx
from bs4 import BeautifulSoup

from app.services.tools.base import Finding, ToolResult, register_tool, score_from_findings

# Rich results Google has fully retired the *search-appearance* for --
# the schema.org markup itself remains valid and causes no errors, it just
# no longer earns a special SERP treatment. Confirmed against Google Search
# Central docs as of this build: FAQPage rich results were restricted to
# authoritative gov/health sites in Aug 2023 and the feature was removed
# entirely on 2026-05-07; HowTo rich results were deprecated on mobile in
# Aug 2023 and desktop in Sept 2023.
DEPRECATION_NOTES: dict[str, str] = {
    "FAQPage": "FAQ rich results were removed from Google Search on 2026-05-07",
    "HowTo": "HowTo rich results were deprecated in 2023",
}

REQUIRED_PROPERTIES: dict[str, list[str]] = {
    "Review": ["reviewRating", "author"],
    "Article": ["headline", "image", "datePublished", "author"],
    "NewsArticle": ["headline", "image", "datePublished", "author"],
    "BlogPosting": ["headline", "image", "datePublished", "author"],
    "BreadcrumbList": ["itemListElement"],
    "Organization": ["name", "url"],
    "LocalBusiness": ["name", "address"],
    "Event": ["name", "startDate", "location"],
    "VideoObject": ["name", "description", "uploadDate", "thumbnailUrl"],
    "Recipe": ["name", "image", "recipeIngredient", "recipeInstructions"],
    "JobPosting": ["title", "description", "datePosted", "hiringOrganization", "jobLocation"],
}


def _validate_product(item: dict) -> list[str]:
    # Google requires name + image, plus either a rating/review or an
    # offer -- and if an offer is present, price/priceCurrency/availability
    # are mandatory for the Product rich result specifically.
    missing = [p for p in ("name", "image") if p not in item]
    if "aggregateRating" not in item and "review" not in item:
        missing.append("aggregateRating or review")
    offers = item.get("offers")
    if not offers:
        missing.append("offers")
    else:
        offer = offers[0] if isinstance(offers, list) and offers else offers
        if isinstance(offer, dict):
            missing.extend(f"offers.{p}" for p in ("price", "priceCurrency", "availability") if p not in offer)
    return missing


SPECIAL_VALIDATORS = {"Product": _validate_product}


def _validate_item(item_type: str, item: dict) -> list[str]:
    if item_type in SPECIAL_VALIDATORS:
        return SPECIAL_VALIDATORS[item_type](item)
    required = REQUIRED_PROPERTIES.get(item_type)
    return [p for p in required if p not in item] if required else []


def _iter_ld_items(data) -> Iterator[dict]:
    if isinstance(data, list):
        for item in data:
            yield from _iter_ld_items(item)
    elif isinstance(data, dict):
        if isinstance(data.get("@graph"), list):
            for item in data["@graph"]:
                yield from _iter_ld_items(item)
        elif "@type" in data:
            yield data


@register_tool("structured_data")
async def run(domain: str) -> ToolResult:
    url = domain if domain.startswith("http") else f"https://{domain}"
    findings: list[Finding] = []

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            resp = await client.get(url, headers={"User-Agent": "SEORepairKit/1.0 (+audit)"})
    except httpx.HTTPError as exc:
        return ToolResult(
            tool="structured_data",
            status="error",
            score=None,
            findings=[Finding("critical", "fetch_failed", f"Could not fetch page: {exc}")],
            raw={"url": url},
        )

    soup = BeautifulSoup(resp.text, "lxml")
    scripts = soup.find_all("script", type="application/ld+json")

    parse_errors = 0
    all_items: list[dict] = []
    for script in scripts:
        try:
            data = json.loads(script.string or "")
        except (ValueError, TypeError):
            parse_errors += 1
            continue
        all_items.extend(_iter_ld_items(data))

    if parse_errors:
        findings.append(Finding("medium", "invalid_json_ld", f"{parse_errors} JSON-LD block(s) failed to parse as valid JSON"))

    if not all_items:
        findings.append(Finding("info", "no_structured_data", "No structured data found on this page"))
        return ToolResult(
            tool="structured_data", status="ok", score=score_from_findings(findings), findings=findings,
            raw={"url": url, "types_found": [], "items": []},
        )

    types_found: set[str] = set()
    validated: list[dict] = []
    missing_by_type: dict[str, int] = {}

    for item in all_items:
        raw_type = item.get("@type")
        types = raw_type if isinstance(raw_type, list) else [raw_type]
        for t in types:
            if not isinstance(t, str):
                continue
            types_found.add(t)
            missing = _validate_item(t, item)
            validated.append({"type": t, "missing_properties": missing})
            if missing:
                missing_by_type[t] = missing_by_type.get(t, 0) + 1

    for t in sorted(types_found & DEPRECATION_NOTES.keys()):
        findings.append(Finding("info", "deprecated_rich_result_type", f"'{t}' markup found -- {DEPRECATION_NOTES[t]}"))

    for t, count in missing_by_type.items():
        findings.append(
            Finding(
                "medium",
                "missing_required_properties",
                f"{count} '{t}' item(s) are missing properties required for rich-result eligibility",
            )
        )

    raw = {"url": url, "types_found": sorted(types_found), "items": validated}
    return ToolResult(tool="structured_data", status="ok", score=score_from_findings(findings), findings=findings, raw=raw)
