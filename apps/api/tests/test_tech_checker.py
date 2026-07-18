import httpx
import pytest
import respx

from app.services.tools.tech_checker import run

WORDPRESS_HTML = """
<html><head>
<meta name="generator" content="WordPress 6.5">
<link rel="stylesheet" href="/wp-content/themes/astra/style.css">
</head><body>
<script src="/wp-includes/js/jquery/jquery.min.js"></script>
</body></html>
"""

VUE_ONLY_HTML = """
<html><body><div id="app" data-v-1a2b3c4d></div></body></html>
"""

EMPTY_HTML = "<html><head></head><body><p>Hello</p></body></html>"


@pytest.mark.asyncio
@respx.mock
async def test_wordpress_site_is_confirmed():
    respx.get("https://example.com").mock(return_value=httpx.Response(200, text=WORDPRESS_HTML))

    result = await run("example.com")

    wp = next(d for d in result.raw["detections"] if d["name"] == "WordPress")
    assert wp["status"] == "confirmed"
    assert wp["confidence"] == 100
    # jQuery and Astra theme should also be picked up from the same page
    names = {d["name"] for d in result.raw["detections"]}
    assert "jQuery" in names
    assert "Astra" in names


@pytest.mark.asyncio
@respx.mock
async def test_no_signatures_match_flags_info_finding():
    respx.get("https://example.com").mock(return_value=httpx.Response(200, text=EMPTY_HTML))

    result = await run("example.com")

    assert result.raw["detections"] == []
    codes = {f.code for f in result.findings}
    assert "no_technologies_detected" in codes


@pytest.mark.asyncio
@respx.mock
async def test_single_medium_signal_is_possible_not_confirmed():
    respx.get("https://example.com").mock(return_value=httpx.Response(200, text=VUE_ONLY_HTML))

    result = await run("example.com")

    vue = next(d for d in result.raw["detections"] if d["name"] == "Vue.js")
    assert vue["status"] == "possible"
    assert vue["confidence"] < 80


@pytest.mark.asyncio
@respx.mock
async def test_cdn_detected_via_header_and_grouped_by_category():
    respx.get("https://example.com").mock(
        return_value=httpx.Response(200, text=EMPTY_HTML, headers={"cf-ray": "abc123-SJC", "server": "cloudflare"})
    )

    result = await run("example.com")

    cf = next(d for d in result.raw["detections"] if d["name"] == "Cloudflare")
    assert cf["status"] == "confirmed"
    assert "Cloudflare" in [d["name"] for d in result.raw["by_category"]["CDN"]]


@pytest.mark.asyncio
@respx.mock
async def test_confirmed_results_sort_before_possible():
    respx.get("https://example.com").mock(return_value=httpx.Response(200, text=WORDPRESS_HTML))

    result = await run("example.com")

    statuses = [d["status"] for d in result.raw["detections"]]
    first_possible = statuses.index("possible") if "possible" in statuses else len(statuses)
    assert all(s == "confirmed" for s in statuses[:first_possible])
