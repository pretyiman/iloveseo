import pytest

import app.services.geo.runner as runner_module
from app.services.geo.providers import GeoProviderError, ProviderResult


@pytest.mark.asyncio
async def test_run_geo_check_handles_mixed_success_and_failure(monkeypatch):
    async def fake_perplexity(query_text):
        return ProviderResult(
            text="SEO Repair Kit is great for developers.",
            citation_urls=["https://seorepairkit.com/"],
            raw={},
        )

    async def fake_openai(query_text):
        raise GeoProviderError("OPENAI_API_KEY is not configured")

    monkeypatch.setattr(runner_module, "PROVIDERS", {"perplexity": fake_perplexity, "openai": fake_openai})

    outcomes = await runner_module.run_geo_check(
        query_text="best seo audit tool",
        domain="seorepairkit.com",
        brand_name="SEO Repair Kit",
        competitor_domains=["screamingfrog.co.uk"],
    )

    by_provider = {o.provider: o for o in outcomes}
    assert by_provider["perplexity"].status == "ok"
    assert by_provider["perplexity"].cited is True
    assert by_provider["perplexity"].position == 1
    assert by_provider["openai"].status == "error"
    assert "not configured" in by_provider["openai"].error_message


@pytest.mark.asyncio
async def test_run_geo_check_truncates_long_response_text(monkeypatch):
    long_text = "a" * (runner_module.RESPONSE_TEXT_MAX_CHARS + 500)

    async def fake_provider(query_text):
        return ProviderResult(text=long_text, citation_urls=[], raw={})

    monkeypatch.setattr(runner_module, "PROVIDERS", {"perplexity": fake_provider})

    outcomes = await runner_module.run_geo_check("q", "example.com", None, [])

    assert len(outcomes[0].response_text) == runner_module.RESPONSE_TEXT_MAX_CHARS
