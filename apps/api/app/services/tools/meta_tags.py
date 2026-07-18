import httpx
from bs4 import BeautifulSoup

from app.services.tools.base import Finding, ToolResult, register_tool, score_from_findings

TITLE_PIXEL_LIMIT = 600
DESCRIPTION_PIXEL_LIMIT = 920
TITLE_MIN_CHARS = 15
DESCRIPTION_MIN_CHARS = 50

# Approximate Arial-ish per-character pixel widths at a 16px baseline.
# Character-count pass/fail bands (the industry-standard 50-60 / 120-160
# rule every competitor tool uses) are known-inaccurate: Google truncates
# by rendered pixel width, not character count, so a title full of "W"s
# truncates far earlier than one full of "i"s at the same length. This is
# a calibrated approximation, not a pixel-perfect render -- good enough to
# be directionally correct without spinning up a headless browser for it.
_CHAR_WIDTH: dict[str, int] = {}
for _c in "ijl.,:;'!|":
    _CHAR_WIDTH[_c] = 4
for _c in " ":
    _CHAR_WIDTH[_c] = 5
for _c in "frtI":
    _CHAR_WIDTH[_c] = 6
for _c in "abcdeghknopqsuvxyz0123456789":
    _CHAR_WIDTH[_c] = 9
for _c in "ABCDEFGHKNOPQRSUVXYZJLT":
    _CHAR_WIDTH[_c] = 11
for _c in "mw":
    _CHAR_WIDTH[_c] = 14
for _c in "MW":
    _CHAR_WIDTH[_c] = 16
_DEFAULT_WIDTH = 9


def estimate_pixel_width(text: str) -> int:
    return sum(_CHAR_WIDTH.get(ch, _DEFAULT_WIDTH) for ch in text)


@register_tool("meta_tags")
async def run(domain: str) -> ToolResult:
    url = domain if domain.startswith("http") else f"https://{domain}"
    findings: list[Finding] = []

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            resp = await client.get(url, headers={"User-Agent": "SEORepairKit/1.0 (+audit)"})
    except httpx.HTTPError as exc:
        return ToolResult(
            tool="meta_tags",
            status="error",
            score=None,
            findings=[Finding("critical", "fetch_failed", f"Could not fetch page: {exc}")],
            raw={"url": url},
        )

    soup = BeautifulSoup(resp.text, "lxml")
    raw: dict = {"url": url, "status_code": resp.status_code}

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None
    raw["title"] = title
    if not title:
        findings.append(Finding("critical", "title_missing", "Page has no <title> tag"))
    else:
        px = estimate_pixel_width(title)
        raw["title_pixel_width_estimate"] = px
        if px > TITLE_PIXEL_LIMIT:
            findings.append(
                Finding(
                    "medium",
                    "title_too_long",
                    f"Title is ~{px}px wide (est.), likely truncated past ~{TITLE_PIXEL_LIMIT}px in search results",
                )
            )
        elif len(title) < TITLE_MIN_CHARS:
            findings.append(Finding("low", "title_too_short", "Title is short enough it may not be descriptive"))

    desc_tag = soup.find("meta", attrs={"name": "description"})
    description = desc_tag.get("content", "").strip() if desc_tag else None
    raw["description"] = description
    if not description:
        findings.append(Finding("high", "description_missing", "Page has no meta description"))
    else:
        px = estimate_pixel_width(description)
        raw["description_pixel_width_estimate"] = px
        if px > DESCRIPTION_PIXEL_LIMIT:
            findings.append(
                Finding(
                    "medium",
                    "description_too_long",
                    f"Description is ~{px}px wide (est.), likely truncated past ~{DESCRIPTION_PIXEL_LIMIT}px",
                )
            )
        elif len(description) < DESCRIPTION_MIN_CHARS:
            findings.append(
                Finding("low", "description_too_short", "Description is short enough it may not be compelling")
            )

    canonical_tag = soup.find("link", rel="canonical")
    raw["canonical"] = canonical_tag.get("href") if canonical_tag else None
    if not canonical_tag:
        findings.append(Finding("medium", "canonical_missing", "No canonical link tag found"))

    robots_tag = soup.find("meta", attrs={"name": "robots"})
    robots_content = robots_tag.get("content", "").lower() if robots_tag else ""
    raw["robots"] = robots_content or None
    if "noindex" in robots_content:
        findings.append(Finding("high", "noindex", "Page is marked noindex"))

    viewport_tag = soup.find("meta", attrs={"name": "viewport"})
    raw["viewport"] = viewport_tag.get("content") if viewport_tag else None
    if not viewport_tag:
        findings.append(
            Finding("medium", "viewport_missing", "No viewport meta tag -- page likely fails mobile rendering")
        )

    og_fields = {}
    for prop in ("og:title", "og:description", "og:image", "og:type", "og:url"):
        tag = soup.find("meta", property=prop)
        og_fields[prop] = tag.get("content") if tag else None
    raw["open_graph"] = og_fields
    missing_og = [k for k, v in og_fields.items() if not v]
    if len(missing_og) == len(og_fields):
        findings.append(Finding("low", "og_missing", "No Open Graph tags found -- links will render poorly when shared"))
    elif missing_og:
        findings.append(
            Finding("info", "og_incomplete", f"Open Graph tags incomplete: missing {', '.join(missing_og)}")
        )

    twitter_card = soup.find("meta", attrs={"name": "twitter:card"})
    raw["twitter_card"] = twitter_card.get("content") if twitter_card else None
    if not twitter_card:
        findings.append(Finding("info", "twitter_card_missing", "No Twitter Card tag found"))

    json_ld = soup.find_all("script", type="application/ld+json")
    raw["json_ld_count"] = len(json_ld)
    if not json_ld:
        findings.append(Finding("info", "structured_data_missing", "No JSON-LD structured data found"))

    return ToolResult(
        tool="meta_tags", status="ok", score=score_from_findings(findings), findings=findings, raw=raw
    )
