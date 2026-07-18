import httpx
import pytest
import respx

from app.services.tools.structured_data import run

NO_JSON_LD_HTML = "<html><head></head><body></body></html>"


def _html_with_ld(payload: str) -> str:
    return f'<html><head><script type="application/ld+json">{payload}</script></head></html>'


COMPLETE_ARTICLE = _html_with_ld(
    '{"@type": "Article", "headline": "Title", "image": "https://example.com/a.jpg", '
    '"datePublished": "2026-01-01", "author": {"@type": "Person", "name": "A"}}'
)

INCOMPLETE_ARTICLE = _html_with_ld('{"@type": "Article", "headline": "Title"}')

COMPLETE_PRODUCT = _html_with_ld(
    '{"@type": "Product", "name": "Widget", "image": "https://example.com/w.jpg", '
    '"aggregateRating": {"@type": "AggregateRating", "ratingValue": "4.5", "reviewCount": "10"}, '
    '"offers": {"@type": "Offer", "price": "9.99", "priceCurrency": "USD", "availability": "https://schema.org/InStock"}}'
)

INCOMPLETE_PRODUCT = _html_with_ld('{"@type": "Product", "name": "Widget"}')

FAQ_PAGE = _html_with_ld(
    '{"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": "Q", '
    '"acceptedAnswer": {"@type": "Answer", "text": "A"}}]}'
)

GRAPH_HTML = _html_with_ld(
    '{"@graph": [{"@type": "Organization", "name": "Acme", "url": "https://example.com"}, '
    '{"@type": "WebSite", "name": "Acme Site"}]}'
)

MALFORMED_JSON = '<html><head><script type="application/ld+json">{not valid json</script></head></html>'


@pytest.mark.asyncio
@respx.mock
async def test_no_structured_data_is_info_only():
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=NO_JSON_LD_HTML))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "no_structured_data" in codes
    assert result.score == 100


@pytest.mark.asyncio
@respx.mock
async def test_complete_article_has_no_missing_properties():
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=COMPLETE_ARTICLE))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "missing_required_properties" not in codes
    assert result.raw["types_found"] == ["Article"]


@pytest.mark.asyncio
@respx.mock
async def test_incomplete_article_flags_missing_properties():
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=INCOMPLETE_ARTICLE))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "missing_required_properties" in codes
    item = result.raw["items"][0]
    assert set(item["missing_properties"]) == {"image", "datePublished", "author"}


@pytest.mark.asyncio
@respx.mock
async def test_complete_product_has_no_missing_properties():
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=COMPLETE_PRODUCT))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "missing_required_properties" not in codes


@pytest.mark.asyncio
@respx.mock
async def test_incomplete_product_flags_offer_and_rating():
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=INCOMPLETE_PRODUCT))

    result = await run("example.com")

    item = result.raw["items"][0]
    assert "offers" in item["missing_properties"]
    assert "aggregateRating or review" in item["missing_properties"]


@pytest.mark.asyncio
@respx.mock
async def test_faqpage_flagged_as_deprecated():
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=FAQ_PAGE))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "deprecated_rich_result_type" in codes
    deprecated_finding = next(f for f in result.findings if f.code == "deprecated_rich_result_type")
    assert deprecated_finding.severity == "info"


@pytest.mark.asyncio
@respx.mock
async def test_graph_structure_extracts_nested_items():
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=GRAPH_HTML))

    result = await run("example.com")

    assert set(result.raw["types_found"]) == {"Organization", "WebSite"}


@pytest.mark.asyncio
@respx.mock
async def test_malformed_json_ld_flagged():
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=MALFORMED_JSON))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "invalid_json_ld" in codes


@pytest.mark.asyncio
@respx.mock
async def test_multiple_items_of_same_type_aggregate_into_one_finding():
    html = (
        '<html><head>'
        '<script type="application/ld+json">{"@type": "Article", "headline": "A"}</script>'
        '<script type="application/ld+json">{"@type": "Article", "headline": "B"}</script>'
        '</head></html>'
    )
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=html))

    result = await run("example.com")

    finding = next(f for f in result.findings if f.code == "missing_required_properties")
    assert "2 'Article'" in finding.message
