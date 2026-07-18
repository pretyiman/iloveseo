import httpx
import pytest
import respx

from app.services.tools.sitemap import run

URLSET_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/</loc><lastmod>2026-01-01</lastmod></url>
  <url><loc>https://example.com/about</loc><lastmod>not-a-date</lastmod></url>
</urlset>
"""

SITEMAP_INDEX_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/sitemap-a.xml</loc></sitemap>
  <sitemap><loc>https://example.com/sitemap-b.xml</loc></sitemap>
</sitemapindex>
"""

CHILD_URLSET_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/1</loc></url>
  <url><loc>https://example.com/2</loc></url>
  <url><loc>https://example.com/3</loc></url>
</urlset>
"""

MALFORMED_XML = b"<urlset><url><loc>https://example.com/</loc></urlset"


@pytest.mark.asyncio
@respx.mock
async def test_no_sitemap_found_anywhere():
    respx.get("https://example.com/robots.txt").mock(return_value=httpx.Response(404))
    for path in [
        "/sitemap.xml",
        "/sitemap_index.xml",
        "/sitemap/sitemap.xml",
        "/wp-sitemap.xml",
        "/sitemap1.xml",
    ]:
        respx.get(f"https://example.com{path}").mock(return_value=httpx.Response(404))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "sitemap_not_found" in codes
    assert result.raw["sitemaps"] == []


@pytest.mark.asyncio
@respx.mock
async def test_sitemap_declared_in_robots_txt_is_parsed():
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /\nSitemap: https://example.com/sitemap.xml\n")
    )
    respx.get("https://example.com/sitemap.xml").mock(return_value=httpx.Response(200, content=URLSET_XML))

    result = await run("example.com")

    assert result.raw["discovery_method"] == "robots.txt"
    sitemap = result.raw["sitemaps"][0]
    assert sitemap["type"] == "urlset"
    assert sitemap["url_count"] == 2
    codes = {f.code for f in result.findings}
    assert "sitemap_invalid_lastmod" in codes
    assert "sitemap_not_in_robots" not in codes


@pytest.mark.asyncio
@respx.mock
async def test_fallback_to_common_path_flags_not_in_robots():
    respx.get("https://example.com/robots.txt").mock(return_value=httpx.Response(404))
    respx.get("https://example.com/sitemap.xml").mock(return_value=httpx.Response(200, content=URLSET_XML))

    result = await run("example.com")

    assert result.raw["discovery_method"] == "common_path"
    codes = {f.code for f in result.findings}
    assert "sitemap_not_in_robots" in codes


@pytest.mark.asyncio
@respx.mock
async def test_sitemap_index_estimates_total_urls():
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text="Sitemap: https://example.com/sitemap_index.xml\n")
    )
    respx.get("https://example.com/sitemap_index.xml").mock(return_value=httpx.Response(200, content=SITEMAP_INDEX_XML))
    respx.get("https://example.com/sitemap-a.xml").mock(return_value=httpx.Response(200, content=CHILD_URLSET_XML))
    respx.get("https://example.com/sitemap-b.xml").mock(return_value=httpx.Response(200, content=CHILD_URLSET_XML))

    result = await run("example.com")

    sitemap = result.raw["sitemaps"][0]
    assert sitemap["type"] == "sitemapindex"
    assert sitemap["child_sitemap_count"] == 2
    assert sitemap["estimated_total_urls"] == 6


@pytest.mark.asyncio
@respx.mock
async def test_malformed_xml_flagged_critical():
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text="Sitemap: https://example.com/sitemap.xml\n")
    )
    respx.get("https://example.com/sitemap.xml").mock(return_value=httpx.Response(200, content=MALFORMED_XML))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "sitemap_malformed_xml" in codes
    assert any(f.severity == "critical" for f in result.findings if f.code == "sitemap_malformed_xml")


@pytest.mark.asyncio
@respx.mock
async def test_too_many_urls_flagged():
    big_urlset = (
        b'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + b"".join(b"<url><loc>https://example.com/%d</loc></url>" % i for i in range(50_001))
        + b"</urlset>"
    )
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text="Sitemap: https://example.com/sitemap.xml\n")
    )
    respx.get("https://example.com/sitemap.xml").mock(return_value=httpx.Response(200, content=big_urlset))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "sitemap_too_many_urls" in codes
