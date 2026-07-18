import httpx
import pytest
import respx
from bs4 import BeautifulSoup

from app.services.crawl import (
    PageRecord,
    _classify_content_type,
    _find_mixed_content,
    _heading_issues,
    _is_soft_404,
    _minhash,
    _similarity,
    _structured_data_types,
    _visible_text,
    build_tool_result,
    crawl_site,
)


def test_classify_content_type():
    assert _classify_content_type("/") == "homepage"
    assert _classify_content_type("") == "homepage"
    assert _classify_content_type("/blog/my-post") == "blog_post"
    assert _classify_content_type("/services/consulting") == "service_page"
    assert _classify_content_type("/random-page") == "other"


def test_visible_text_strips_script_and_style():
    html = "<html><body><script>var x=1;</script><style>.a{}</style><p>Hello world</p></body></html>"
    assert _visible_text(html) == "Hello world"


def test_minhash_similarity_high_for_near_identical_text():
    text_a = "The quick brown fox jumps over the lazy dog every single morning without fail"
    text_b = "The quick brown fox jumps over the lazy dog every single morning without fail!"
    text_c = "Completely unrelated content about database indexing strategies for large scale systems"

    sig_a, sig_b, sig_c = _minhash(text_a), _minhash(text_b), _minhash(text_c)

    assert _similarity(sig_a, sig_b) > _similarity(sig_a, sig_c)


def test_heading_issues_detects_missing_h1():
    soup = BeautifulSoup("<html><body><h2>Sub</h2></body></html>", "lxml")
    count, issues = _heading_issues(soup)
    assert count == 0
    assert "missing_h1" in issues


def test_heading_issues_detects_multiple_h1():
    soup = BeautifulSoup("<html><body><h1>A</h1><h1>B</h1></body></html>", "lxml")
    count, issues = _heading_issues(soup)
    assert count == 2
    assert "multiple_h1" in issues


def test_heading_issues_detects_skipped_level():
    soup = BeautifulSoup("<html><body><h1>A</h1><h3>Skipped</h3></body></html>", "lxml")
    _, issues = _heading_issues(soup)
    assert "skipped_heading_level" in issues


def test_heading_issues_clean_page_has_no_issues():
    soup = BeautifulSoup("<html><body><h1>A</h1><h2>B</h2><h3>C</h3></body></html>", "lxml")
    count, issues = _heading_issues(soup)
    assert count == 1
    assert issues == []


def test_is_soft_404_detects_phrase():
    assert _is_soft_404(200, "Sorry, page not found on this server", word_count=50)


def test_is_soft_404_detects_very_low_word_count():
    assert _is_soft_404(200, "oops", word_count=1)


def test_is_soft_404_ignores_normal_page():
    assert not _is_soft_404(200, "A perfectly normal page with plenty of real content here", word_count=200)


def test_is_soft_404_ignores_non_200():
    assert not _is_soft_404(404, "page not found", word_count=1)


def test_find_mixed_content_on_https_page():
    soup = BeautifulSoup('<img src="http://example.com/a.png">', "lxml")
    mixed = _find_mixed_content("https://example.com/", soup)
    assert mixed == ["http://example.com/a.png"]


def test_find_mixed_content_ignored_on_http_page():
    soup = BeautifulSoup('<img src="http://example.com/a.png">', "lxml")
    assert _find_mixed_content("http://example.com/", soup) == []


def test_structured_data_types_extracts_type():
    soup = BeautifulSoup(
        '<script type="application/ld+json">{"@type": "Product", "name": "Widget"}</script>', "lxml"
    )
    assert _structured_data_types(soup) == ["Product"]


@pytest.mark.asyncio
@respx.mock
async def test_crawl_site_discovers_linked_pages():
    respx.get("https://example.com/robots.txt").mock(return_value=httpx.Response(404))
    respx.get("https://example.com/sitemap.xml").mock(return_value=httpx.Response(404))
    for path in ["/sitemap_index.xml", "/sitemap/sitemap.xml", "/wp-sitemap.xml", "/sitemap1.xml"]:
        respx.get(f"https://example.com{path}").mock(return_value=httpx.Response(404))

    respx.get("https://example.com/").mock(
        return_value=httpx.Response(
            200,
            text="<html><head><title>Home</title></head><body><h1>Welcome</h1>"
            + "<p>" + " ".join(["word"] * 150) + "</p>"
            + '<a href="/about">About</a></body></html>',
        )
    )
    respx.get("https://example.com/about").mock(
        return_value=httpx.Response(
            200,
            text="<html><head><title>About</title></head><body><h1>About us</h1>"
            + "<p>" + " ".join(["word"] * 150) + "</p></body></html>",
        )
    )
    respx.post("http://localhost:4000/render").mock(return_value=httpx.Response(502))

    crawl_data = await crawl_site("example.com", max_pages=10)

    urls = {p.url for p in crawl_data["pages"]}
    assert "https://example.com" in urls
    assert "https://example.com/about" in urls
    about_page = next(p for p in crawl_data["pages"] if p.url == "https://example.com/about")
    assert about_page.indexability == "indexable"
    assert about_page.thin_content is False


def _make_page(url, **overrides):
    defaults = dict(
        url=url, depth=0, status_code=200, redirected=False, title="T", meta_description="D", canonical=None,
        word_count=500, content_type="other", thin_content=False, h1_count=1, heading_issues=[], broken_images=[],
        internal_link_count=0, external_link_count=0, mixed_content=[], structured_data_types=[],
        indexability="indexable", is_soft_404=False, content_hash="hash-" + url, minhash=_minhash("filler " * 50),
    )
    defaults.update(overrides)
    return PageRecord(**defaults)


def test_build_tool_result_flags_thin_content_and_errors():
    pages = [
        _make_page("https://example.com/a", thin_content=True),
        _make_page("https://example.com/b", status_code=500, indexability="error_page"),
    ]
    result = build_tool_result(
        {"pages": pages, "sitemap_urls": set(), "inbound_counts": {}, "js_diff_pages": [], "max_pages": 10}
    )
    codes = {f.code for f in result.findings}
    assert "thin_content_pages" in codes
    assert "crawl_errors" in codes


def test_build_tool_result_flags_exact_duplicates():
    same_hash_text = _minhash("identical content here " * 30)
    pages = [
        _make_page("https://example.com/a", content_hash="dup", minhash=same_hash_text),
        _make_page("https://example.com/b", content_hash="dup", minhash=same_hash_text),
    ]
    result = build_tool_result(
        {"pages": pages, "sitemap_urls": set(), "inbound_counts": {}, "js_diff_pages": [], "max_pages": 10}
    )
    codes = {f.code for f in result.findings}
    assert "duplicate_content" in codes
    assert len(result.raw["duplicate_clusters"]) == 1
    assert set(result.raw["duplicate_clusters"][0]) == {"https://example.com/a", "https://example.com/b"}


def test_build_tool_result_sitemap_coverage():
    pages = [_make_page("https://example.com/a")]
    result = build_tool_result(
        {
            "pages": pages,
            "sitemap_urls": {"https://example.com/a", "https://example.com/never-crawled"},
            "inbound_counts": {},
            "js_diff_pages": [],
            "max_pages": 10,
        }
    )
    codes = {f.code for f in result.findings}
    assert "sitemap_urls_not_crawled" in codes
    assert result.raw["sitemap_coverage"]["sitemap_not_crawled"] == 1
