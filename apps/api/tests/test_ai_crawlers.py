import httpx
import pytest
import respx

from app.services.tools.ai_crawlers import _is_path_blocked, _parse_robots_groups, run

ROBOTS_BLOCK_SEARCH_CITATION_BOT = """
User-agent: *
Allow: /

User-agent: OAI-SearchBot
Disallow: /
"""

ROBOTS_BLOCK_TRAINING_ONLY = """
User-agent: *
Allow: /

User-agent: GPTBot
Disallow: /
"""

ROBOTS_ALLOW_ALL = """
User-agent: *
Allow: /
"""

LLMS_TXT_SMALL = "# Example\n\n- [Docs](https://example.com/docs)\n- [Pricing](https://example.com/pricing)\n"


def test_parse_robots_groups_splits_on_new_user_agent_after_rules():
    groups = _parse_robots_groups(ROBOTS_BLOCK_SEARCH_CITATION_BOT)
    assert groups["*"] == [("allow", "/")]
    assert groups["oai-searchbot"] == [("disallow", "/")]


def test_is_path_blocked_prefers_longest_match():
    rules = [("disallow", "/"), ("allow", "/blog")]
    assert _is_path_blocked(rules, "/blog/post") is False
    assert _is_path_blocked(rules, "/admin") is True


@pytest.mark.asyncio
@respx.mock
async def test_blocking_search_citation_bot_is_flagged():
    respx.get("https://example.com/robots.txt").mock(return_value=httpx.Response(200, text=ROBOTS_BLOCK_SEARCH_CITATION_BOT))
    respx.get("https://example.com/llms.txt").mock(return_value=httpx.Response(404))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "search_citation_bot_blocked" in codes
    oai = next(b for b in result.raw["bots"] if b["name"] == "OAI-SearchBot")
    assert oai["status"] == "blocked"


@pytest.mark.asyncio
@respx.mock
async def test_blocking_training_only_bot_is_not_flagged():
    respx.get("https://example.com/robots.txt").mock(return_value=httpx.Response(200, text=ROBOTS_BLOCK_TRAINING_ONLY))
    respx.get("https://example.com/llms.txt").mock(return_value=httpx.Response(404))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "search_citation_bot_blocked" not in codes
    gptbot = next(b for b in result.raw["bots"] if b["name"] == "GPTBot")
    assert gptbot["status"] == "blocked"


@pytest.mark.asyncio
@respx.mock
async def test_missing_robots_txt_defaults_everything_allowed():
    respx.get("https://example.com/robots.txt").mock(return_value=httpx.Response(404))
    respx.get("https://example.com/llms.txt").mock(return_value=httpx.Response(404))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "robots_txt_missing" in codes
    assert all(b["status"] == "allowed" for b in result.raw["bots"])


@pytest.mark.asyncio
@respx.mock
async def test_llms_txt_present_and_reasonably_sized():
    respx.get("https://example.com/robots.txt").mock(return_value=httpx.Response(200, text=ROBOTS_ALLOW_ALL))
    respx.get("https://example.com/llms.txt").mock(return_value=httpx.Response(200, text=LLMS_TXT_SMALL))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "llms_txt_missing" not in codes
    assert "llms_txt_too_large" not in codes
    assert result.raw["llms_txt_link_count"] == 2


@pytest.mark.asyncio
@respx.mock
async def test_llms_txt_missing_is_info_only_and_does_not_hurt_score():
    respx.get("https://example.com/robots.txt").mock(return_value=httpx.Response(200, text=ROBOTS_ALLOW_ALL))
    respx.get("https://example.com/llms.txt").mock(return_value=httpx.Response(404))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "llms_txt_missing" in codes
    assert result.score == 100


@pytest.mark.asyncio
@respx.mock
async def test_oversized_llms_txt_flagged():
    huge_llms_txt = "\n".join(f"- [Page {i}](https://example.com/{i})" for i in range(80))
    respx.get("https://example.com/robots.txt").mock(return_value=httpx.Response(200, text=ROBOTS_ALLOW_ALL))
    respx.get("https://example.com/llms.txt").mock(return_value=httpx.Response(200, text=huge_llms_txt))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "llms_txt_too_large" in codes
