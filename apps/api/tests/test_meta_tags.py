import httpx
import pytest
import respx

from app.services.tools.meta_tags import estimate_pixel_width, run

GOOD_HTML = """
<html><head>
<title>Great Widgets For Sale Online</title>
<meta name="description" content="Buy the best widgets online with free shipping and a 30 day return policy on every order.">
<link rel="canonical" href="https://example.com/">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta property="og:title" content="Great Widgets">
<meta property="og:description" content="Buy the best widgets online.">
<meta property="og:image" content="https://example.com/og.png">
<meta property="og:type" content="website">
<meta property="og:url" content="https://example.com/">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{"@context": "https://schema.org"}</script>
</head><body></body></html>
"""

BARE_HTML = "<html><head></head><body></body></html>"


@pytest.mark.asyncio
@respx.mock
async def test_well_optimized_page_scores_high():
    respx.get("https://example.com").mock(return_value=httpx.Response(200, text=GOOD_HTML))

    result = await run("example.com")

    assert result.status == "ok"
    assert result.score == 100
    assert result.findings == []
    assert result.raw["title"] == "Great Widgets For Sale Online"


@pytest.mark.asyncio
@respx.mock
async def test_bare_page_flags_everything_missing():
    respx.get("https://example.com").mock(return_value=httpx.Response(200, text=BARE_HTML))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "title_missing" in codes
    assert "description_missing" in codes
    assert "canonical_missing" in codes
    assert "viewport_missing" in codes
    assert result.score < 100


@pytest.mark.asyncio
@respx.mock
async def test_fetch_failure_returns_error_status():
    respx.get("https://down.example.com").mock(side_effect=httpx.ConnectError("boom"))

    result = await run("down.example.com")

    assert result.status == "error"
    assert result.score is None
    assert result.findings[0].code == "fetch_failed"


def test_pixel_width_penalizes_wide_characters_more_than_narrow():
    wide = "MMMMMMMMMM"
    narrow = "iiiiiiiiii"
    assert estimate_pixel_width(wide) > estimate_pixel_width(narrow)
