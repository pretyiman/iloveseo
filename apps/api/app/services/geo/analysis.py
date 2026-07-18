from dataclasses import dataclass
from urllib.parse import urlparse


def _normalize_domain(domain: str) -> str:
    return domain.strip().lower().removeprefix("www.")


def _url_host(url: str) -> str | None:
    try:
        host = urlparse(url).hostname
    except ValueError:
        return None
    return host.lower().removeprefix("www.") if host else None


@dataclass
class CitationResult:
    cited: bool
    position: int | None  # 1-indexed rank among citation_urls, if cited via URL
    cited_via_url: bool
    mentioned_in_text: bool


def detect_citation(domain: str, brand_name: str | None, text: str, citation_urls: list[str]) -> CitationResult:
    """A domain is 'cited' if either its URL appears in the provider's
    citation list (search-grounded providers) or its domain/brand name is
    named in the answer text -- AI answers frequently name a brand without
    linking to it, so text-mention alone still counts as visibility even
    without a verifiable citation URL."""
    normalized_domain = _normalize_domain(domain)

    position = None
    for i, url in enumerate(citation_urls):
        if _url_host(url) == normalized_domain:
            position = i + 1
            break
    cited_via_url = position is not None

    lowered_text = text.lower()
    mentioned_in_text = normalized_domain in lowered_text or bool(brand_name and brand_name.lower() in lowered_text)

    return CitationResult(
        cited=cited_via_url or mentioned_in_text,
        position=position,
        cited_via_url=cited_via_url,
        mentioned_in_text=mentioned_in_text,
    )


def detect_competitor_mentions(competitor_domains: list[str], text: str, citation_urls: list[str]) -> dict[str, bool]:
    cited_hosts = {_url_host(url) for url in citation_urls}
    lowered_text = text.lower()
    mentions: dict[str, bool] = {}
    for competitor in competitor_domains:
        normalized = _normalize_domain(competitor)
        mentions[competitor] = normalized in cited_hosts or normalized in lowered_text
    return mentions
