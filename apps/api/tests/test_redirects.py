import httpx
import pytest
import respx

from app.services.tools.redirects import run


@pytest.mark.asyncio
@respx.mock
async def test_no_redirect_scores_high():
    respx.get("https://example.com/").mock(return_value=httpx.Response(200))

    result = await run("example.com")

    assert result.status == "ok"
    assert result.score == 100
    assert result.raw["hop_count"] == 0
    assert result.raw["final_url"] == "https://example.com"


@pytest.mark.asyncio
@respx.mock
async def test_single_permanent_redirect_to_https_is_clean():
    respx.get("https://example.com/").mock(
        return_value=httpx.Response(301, headers={"location": "https://example.com/new"})
    )
    respx.get("https://example.com/new").mock(return_value=httpx.Response(200))

    result = await run("example.com")

    assert result.raw["hop_count"] == 1
    assert result.raw["final_url"] == "https://example.com/new"
    blocking = [f for f in result.findings if f.severity in ("critical", "high", "medium")]
    assert blocking == []


@pytest.mark.asyncio
@respx.mock
async def test_long_chain_flagged():
    respx.get("https://example.com/").mock(return_value=httpx.Response(301, headers={"location": "https://example.com/1"}))
    respx.get("https://example.com/1").mock(return_value=httpx.Response(301, headers={"location": "https://example.com/2"}))
    respx.get("https://example.com/2").mock(return_value=httpx.Response(301, headers={"location": "https://example.com/3"}))
    respx.get("https://example.com/3").mock(return_value=httpx.Response(200))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "long_redirect_chain" in codes
    assert result.raw["hop_count"] == 3


@pytest.mark.asyncio
@respx.mock
async def test_temporary_redirect_flagged():
    respx.get("https://example.com/").mock(return_value=httpx.Response(302, headers={"location": "https://example.com/new"}))
    respx.get("https://example.com/new").mock(return_value=httpx.Response(200))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "temporary_redirect" in codes


@pytest.mark.asyncio
@respx.mock
async def test_redirect_loop_detected():
    respx.get("https://example.com/a").mock(return_value=httpx.Response(301, headers={"location": "https://example.com/b"}))
    respx.get("https://example.com/b").mock(return_value=httpx.Response(301, headers={"location": "https://example.com/a"}))

    result = await run("https://example.com/a")

    codes = {f.code for f in result.findings}
    assert "redirect_loop" in codes


@pytest.mark.asyncio
@respx.mock
async def test_final_destination_not_https_flagged():
    respx.get("https://example.com/").mock(return_value=httpx.Response(301, headers={"location": "http://example.com/new"}))
    respx.get("http://example.com/new").mock(return_value=httpx.Response(200))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "final_destination_not_https" in codes


@pytest.mark.asyncio
@respx.mock
async def test_excessive_hops_flagged():
    for i in range(11):
        respx.get(f"https://example.com/{i}").mock(
            return_value=httpx.Response(301, headers={"location": f"https://example.com/{i + 1}"})
        )
    respx.get("https://example.com/11").mock(return_value=httpx.Response(200))

    result = await run("https://example.com/0")

    codes = {f.code for f in result.findings}
    assert "too_many_hops" in codes
