from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import httpx

from app.core.config import get_settings

PERPLEXITY_ENDPOINT = "https://api.perplexity.ai/chat/completions"
OPENAI_RESPONSES_ENDPOINT = "https://api.openai.com/v1/responses"


class GeoProviderError(Exception):
    pass


@dataclass
class ProviderResult:
    text: str
    citation_urls: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


async def query_perplexity(prompt: str) -> ProviderResult:
    """Perplexity's Sonar models are natively search-grounded -- every
    response includes a top-level `citations` array of the URLs consulted,
    no special tool configuration needed. Response shape verified against
    current Perplexity API docs (OpenAI-chat-completion-compatible, plus
    the `citations` field)."""
    settings = get_settings()
    if not settings.perplexity_api_key:
        raise GeoProviderError("PERPLEXITY_API_KEY is not configured")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                PERPLEXITY_ENDPOINT,
                headers={"Authorization": f"Bearer {settings.perplexity_api_key}"},
                json={"model": "sonar", "messages": [{"role": "user", "content": prompt}]},
            )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise GeoProviderError(f"Perplexity request failed: {exc}") from exc

    data = resp.json()
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise GeoProviderError(f"Unexpected Perplexity response shape: {exc}") from exc

    return ProviderResult(text=text, citation_urls=data.get("citations", []), raw=data)


async def query_openai(prompt: str) -> ProviderResult:
    """Uses the Responses API with the built-in web_search tool so the
    answer reflects live search grounding rather than base model
    knowledge -- closer to what a user sees from ChatGPT search. Citation
    URLs come from `url_citation` annotations on the output_text content,
    per current OpenAI API docs. NOTE: not live-tested against the real
    API in this build (no API key configured in this environment) -- the
    request/response shape is verified against current docs but should be
    re-confirmed against a real response before relying on it in
    production."""
    settings = get_settings()
    if not settings.openai_api_key:
        raise GeoProviderError("OPENAI_API_KEY is not configured")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                OPENAI_RESPONSES_ENDPOINT,
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={"model": "gpt-4o", "input": prompt, "tools": [{"type": "web_search"}]},
            )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise GeoProviderError(f"OpenAI request failed: {exc}") from exc

    data = resp.json()
    text_parts: list[str] = []
    citation_urls: list[str] = []
    for item in data.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") != "output_text":
                continue
            text_parts.append(content.get("text", ""))
            for annotation in content.get("annotations", []):
                if annotation.get("type") == "url_citation" and annotation.get("url"):
                    citation_urls.append(annotation["url"])

    return ProviderResult(text="".join(text_parts), citation_urls=citation_urls, raw=data)


ProviderFn = Callable[[str], Awaitable[ProviderResult]]
PROVIDERS: dict[str, ProviderFn] = {
    "perplexity": query_perplexity,
    "openai": query_openai,
}
