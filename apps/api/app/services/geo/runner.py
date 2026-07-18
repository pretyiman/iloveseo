import asyncio
from dataclasses import dataclass, field

from app.services.geo.analysis import detect_citation, detect_competitor_mentions
from app.services.geo.providers import PROVIDERS, GeoProviderError

RESPONSE_TEXT_MAX_CHARS = 4000


@dataclass
class GeoCheckOutcome:
    provider: str
    status: str  # "ok" | "error"
    cited: bool | None = None
    position: int | None = None
    competitor_mentions: dict = field(default_factory=dict)
    citation_urls: list = field(default_factory=list)
    response_text: str | None = None
    error_message: str | None = None


async def _run_one(provider: str, query_text: str, domain: str, brand_name: str | None, competitor_domains: list[str]) -> GeoCheckOutcome:
    fn = PROVIDERS[provider]
    try:
        result = await fn(query_text)
    except GeoProviderError as exc:
        return GeoCheckOutcome(provider=provider, status="error", error_message=str(exc))

    citation = detect_citation(domain, brand_name, result.text, result.citation_urls)
    competitor_mentions = detect_competitor_mentions(competitor_domains, result.text, result.citation_urls)

    return GeoCheckOutcome(
        provider=provider,
        status="ok",
        cited=citation.cited,
        position=citation.position,
        competitor_mentions=competitor_mentions,
        citation_urls=result.citation_urls,
        response_text=result.text[:RESPONSE_TEXT_MAX_CHARS],
    )


async def run_geo_check(query_text: str, domain: str, brand_name: str | None, competitor_domains: list[str]) -> list[GeoCheckOutcome]:
    return list(
        await asyncio.gather(
            *(_run_one(provider, query_text, domain, brand_name, competitor_domains) for provider in PROVIDERS)
        )
    )
