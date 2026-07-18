import httpx
import pytest
import respx

from app.services.render_client import RenderError, render


@pytest.mark.asyncio
@respx.mock
async def test_render_posts_expected_payload_and_parses_response():
    route = respx.post("http://localhost:4000/render").mock(
        return_value=httpx.Response(200, json={"status_code": 200, "title": "Example"})
    )

    result = await render("https://example.com", device="iPhone 13", throttle=True)

    assert result["title"] == "Example"
    sent_body = route.calls[0].request.content
    import json

    payload = json.loads(sent_body)
    assert payload["url"] == "https://example.com"
    assert payload["device"] == "iPhone 13"
    assert payload["throttle"] is True


@pytest.mark.asyncio
@respx.mock
async def test_render_raises_render_error_on_failure():
    respx.post("http://localhost:4000/render").mock(return_value=httpx.Response(502, json={"error": "boom"}))

    with pytest.raises(RenderError):
        await render("https://example.com")
