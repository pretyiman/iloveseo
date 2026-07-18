import types

import httpx
import pytest
import respx

import app.services.geo.providers as providers_module
from app.services.geo.providers import GeoProviderError, query_openai, query_perplexity


def _settings(perplexity_api_key="", openai_api_key=""):
    return types.SimpleNamespace(perplexity_api_key=perplexity_api_key, openai_api_key=openai_api_key)


@pytest.mark.asyncio
async def test_perplexity_raises_when_not_configured(monkeypatch):
    monkeypatch.setattr(providers_module, "get_settings", lambda: _settings())

    with pytest.raises(GeoProviderError, match="not configured"):
        await query_perplexity("best crm for startups")


@pytest.mark.asyncio
@respx.mock
async def test_perplexity_parses_text_and_citations(monkeypatch):
    monkeypatch.setattr(providers_module, "get_settings", lambda: _settings(perplexity_api_key="pplx-key"))
    respx.post(providers_module.PERPLEXITY_ENDPOINT).mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "SEO Repair Kit is a solid pick."}}],
                "citations": ["https://seorepairkit.com/", "https://competitor.com/"],
            },
        )
    )

    result = await query_perplexity("best seo audit tool")

    assert result.text == "SEO Repair Kit is a solid pick."
    assert result.citation_urls == ["https://seorepairkit.com/", "https://competitor.com/"]


@pytest.mark.asyncio
@respx.mock
async def test_perplexity_http_error_raises_geo_provider_error(monkeypatch):
    monkeypatch.setattr(providers_module, "get_settings", lambda: _settings(perplexity_api_key="pplx-key"))
    respx.post(providers_module.PERPLEXITY_ENDPOINT).mock(return_value=httpx.Response(401, json={"error": "bad key"}))

    with pytest.raises(GeoProviderError):
        await query_perplexity("best seo audit tool")


@pytest.mark.asyncio
@respx.mock
async def test_perplexity_malformed_response_raises(monkeypatch):
    monkeypatch.setattr(providers_module, "get_settings", lambda: _settings(perplexity_api_key="pplx-key"))
    respx.post(providers_module.PERPLEXITY_ENDPOINT).mock(return_value=httpx.Response(200, json={"unexpected": True}))

    with pytest.raises(GeoProviderError):
        await query_perplexity("best seo audit tool")


@pytest.mark.asyncio
async def test_openai_raises_when_not_configured(monkeypatch):
    monkeypatch.setattr(providers_module, "get_settings", lambda: _settings())

    with pytest.raises(GeoProviderError, match="not configured"):
        await query_openai("best crm for startups")


@pytest.mark.asyncio
@respx.mock
async def test_openai_parses_output_text_and_url_citations(monkeypatch):
    monkeypatch.setattr(providers_module, "get_settings", lambda: _settings(openai_api_key="sk-key"))
    respx.post(providers_module.OPENAI_RESPONSES_ENDPOINT).mock(
        return_value=httpx.Response(
            200,
            json={
                "output": [
                    {"type": "web_search_call", "id": "ws_1", "status": "completed"},
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "SEO Repair Kit is a good choice for developers.",
                                "annotations": [
                                    {
                                        "type": "url_citation",
                                        "url": "https://seorepairkit.com/",
                                        "title": "SEO Repair Kit",
                                        "start_index": 0,
                                        "end_index": 10,
                                    }
                                ],
                            }
                        ],
                    },
                ]
            },
        )
    )

    result = await query_openai("best seo audit tool")

    assert "SEO Repair Kit" in result.text
    assert result.citation_urls == ["https://seorepairkit.com/"]


@pytest.mark.asyncio
@respx.mock
async def test_openai_http_error_raises_geo_provider_error(monkeypatch):
    monkeypatch.setattr(providers_module, "get_settings", lambda: _settings(openai_api_key="sk-key"))
    respx.post(providers_module.OPENAI_RESPONSES_ENDPOINT).mock(return_value=httpx.Response(500, json={"error": "boom"}))

    with pytest.raises(GeoProviderError):
        await query_openai("best seo audit tool")
