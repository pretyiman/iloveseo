import httpx
import pytest
import respx

from app.services.tools.hreflang import run

NO_HREFLANG_HTML = "<html><head></head><body></body></html>"

CLEAN_HTML = """
<html><head>
<link rel="alternate" hreflang="en" href="https://example.com/">
<link rel="alternate" hreflang="fr" href="https://example.com/fr/">
<link rel="alternate" hreflang="x-default" href="https://example.com/">
</head><body></body></html>
"""

FR_PAGE_RECIPROCAL_HTML = """
<html><head>
<link rel="alternate" hreflang="en" href="https://example.com/">
<link rel="alternate" hreflang="fr" href="https://example.com/fr/">
</head><body></body></html>
"""

FR_PAGE_NOT_RECIPROCAL_HTML = "<html><head></head><body></body></html>"


@pytest.mark.asyncio
@respx.mock
async def test_no_hreflang_is_info_only():
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=NO_HREFLANG_HTML))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "no_hreflang" in codes
    assert result.score == 100


@pytest.mark.asyncio
@respx.mock
async def test_clean_reciprocal_setup_has_no_blocking_findings():
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=CLEAN_HTML))
    respx.get("https://example.com/fr/").mock(return_value=httpx.Response(200, text=FR_PAGE_RECIPROCAL_HTML))

    result = await run("example.com")

    blocking = [f for f in result.findings if f.severity in ("critical", "high", "medium")]
    assert blocking == []


@pytest.mark.asyncio
@respx.mock
async def test_invalid_locale_code_flagged():
    html = '<html><head><link rel="alternate" hreflang="english" href="https://example.com/en/"></head></html>'
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=html))
    respx.get("https://example.com/en/").mock(return_value=httpx.Response(200, text=NO_HREFLANG_HTML))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "invalid_locale_code" in codes


@pytest.mark.asyncio
@respx.mock
async def test_uk_locale_confusion_flagged():
    html = '<html><head><link rel="alternate" hreflang="uk" href="https://example.com/uk/"></head></html>'
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=html))
    respx.get("https://example.com/uk/").mock(return_value=httpx.Response(200, text=NO_HREFLANG_HTML))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "uk_locale_confusion" in codes


@pytest.mark.asyncio
@respx.mock
async def test_conflicting_hreflang_flagged():
    html = """
    <html><head>
    <link rel="alternate" hreflang="fr" href="https://example.com/fr-a/">
    <link rel="alternate" hreflang="fr" href="https://example.com/fr-b/">
    </head></html>
    """
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=html))
    respx.get("https://example.com/fr-a/").mock(return_value=httpx.Response(200, text=NO_HREFLANG_HTML))
    respx.get("https://example.com/fr-b/").mock(return_value=httpx.Response(200, text=NO_HREFLANG_HTML))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "conflicting_hreflang" in codes


@pytest.mark.asyncio
@respx.mock
async def test_missing_x_default_flagged():
    html = """
    <html><head>
    <link rel="alternate" hreflang="en" href="https://example.com/">
    <link rel="alternate" hreflang="fr" href="https://example.com/fr/">
    </head></html>
    """
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=html))
    respx.get("https://example.com/fr/").mock(return_value=httpx.Response(200, text=FR_PAGE_RECIPROCAL_HTML))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "missing_x_default" in codes


@pytest.mark.asyncio
@respx.mock
async def test_missing_self_reference_flagged():
    html = '<html><head><link rel="alternate" hreflang="fr" href="https://example.com/fr/"></head></html>'
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=html))
    respx.get("https://example.com/fr/").mock(return_value=httpx.Response(200, text=NO_HREFLANG_HTML))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "missing_self_reference" in codes


@pytest.mark.asyncio
@respx.mock
async def test_non_reciprocal_alternate_flagged():
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=CLEAN_HTML))
    respx.get("https://example.com/fr/").mock(return_value=httpx.Response(200, text=FR_PAGE_NOT_RECIPROCAL_HTML))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "non_reciprocal_hreflang" in codes
    assert result.raw["non_reciprocal_urls"] == ["https://example.com/fr/"]
