import asyncio

import httpx

from app.services.tools.base import Finding, ToolResult, register_tool, score_from_findings

# purpose: "training" bots feed model training; "search_citation" bots power
# live AI-answer citations (ChatGPT Search, Perplexity, Claude, AI
# Overviews). The two are frequently split per-vendor now specifically so a
# site can opt out of training while staying eligible to be cited -- e.g.
# OpenAI's GPTBot (training) vs OAI-SearchBot (search), Anthropic's
# ClaudeBot (training) vs Claude-SearchBot (search).
TRACKED_BOTS: list[dict] = [
    {"name": "GPTBot", "vendor": "OpenAI", "purpose": "training"},
    {"name": "OAI-SearchBot", "vendor": "OpenAI", "purpose": "search_citation"},
    {"name": "ChatGPT-User", "vendor": "OpenAI", "purpose": "user_action"},
    {"name": "ClaudeBot", "vendor": "Anthropic", "purpose": "training"},
    {"name": "Claude-SearchBot", "vendor": "Anthropic", "purpose": "search_citation"},
    {"name": "Claude-User", "vendor": "Anthropic", "purpose": "user_action"},
    {"name": "PerplexityBot", "vendor": "Perplexity", "purpose": "search_citation"},
    {"name": "Google-Extended", "vendor": "Google", "purpose": "training"},
    {"name": "Applebot-Extended", "vendor": "Apple", "purpose": "training"},
    {"name": "Bytespider", "vendor": "ByteDance", "purpose": "training"},
    {"name": "CCBot", "vendor": "Common Crawl", "purpose": "training"},
]

LLMS_TXT_MAX_RECOMMENDED_LINKS = 50


def _parse_robots_groups(text: str) -> dict[str, list[tuple[str, str]]]:
    """Maps each literal user-agent token (lowercased) to its ordered
    (directive, path) rules, per RFC 9309 group semantics: consecutive
    User-agent lines share a group; the group closes at the first
    Allow/Disallow line, and a later User-agent line starts a new group."""
    groups: dict[str, list[tuple[str, str]]] = {}
    current_agents: list[str] = []
    collecting = True
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field = field.strip().lower()
        value = value.strip()

        if field == "user-agent":
            if not collecting:
                current_agents = []
                collecting = True
            current_agents.append(value.lower())
            groups.setdefault(value.lower(), [])
        elif field in ("disallow", "allow"):
            collecting = False
            for agent in current_agents:
                groups[agent].append((field, value))
    return groups


def _is_path_blocked(rules: list[tuple[str, str]], path: str = "/") -> bool:
    best_len = -1
    best_allow = True
    for directive, rule_path in rules:
        if rule_path == "":
            continue  # an empty Disallow means "allow everything" and adds no constraint
        if path.startswith(rule_path) and len(rule_path) > best_len:
            best_len = len(rule_path)
            best_allow = directive == "allow"
    return not best_allow


def _effective_rules(groups: dict[str, list[tuple[str, str]]], bot_name: str) -> list[tuple[str, str]] | None:
    key = bot_name.lower()
    if key in groups:
        return groups[key]
    if "*" in groups:
        return groups["*"]
    return None


@register_tool("ai_crawlers")
async def run(domain: str) -> ToolResult:
    base = domain if domain.startswith("http") else f"https://{domain}"
    findings: list[Finding] = []
    raw: dict = {"base_url": base}

    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        robots_resp, llms_resp = await asyncio.gather(
            client.get(f"{base}/robots.txt", headers={"User-Agent": "SEORepairKit/1.0 (+audit)"}),
            client.get(f"{base}/llms.txt", headers={"User-Agent": "SEORepairKit/1.0 (+audit)"}),
            return_exceptions=True,
        )

    bot_results: list[dict] = []
    if isinstance(robots_resp, Exception) or robots_resp.status_code >= 400:
        raw["robots_txt_found"] = False
        findings.append(
            Finding("low", "robots_txt_missing", "No robots.txt found -- all crawlers default to fully allowed")
        )
        groups: dict[str, list[tuple[str, str]]] = {}
    else:
        raw["robots_txt_found"] = True
        groups = _parse_robots_groups(robots_resp.text)

    for bot in TRACKED_BOTS:
        rules = _effective_rules(groups, bot["name"])
        if rules is None:
            status = "allowed"
        else:
            status = "blocked" if _is_path_blocked(rules) else "allowed"
        bot_results.append({**bot, "status": status})

        if status == "blocked" and bot["purpose"] == "search_citation":
            findings.append(
                Finding(
                    "medium",
                    "search_citation_bot_blocked",
                    f"{bot['name']} ({bot['vendor']}) is blocked -- this can reduce citations in AI-generated answers",
                )
            )

    raw["bots"] = bot_results

    if isinstance(llms_resp, Exception) or llms_resp.status_code >= 400:
        raw["llms_txt_found"] = False
        findings.append(
            Finding(
                "info",
                "llms_txt_missing",
                "No llms.txt found. Not a confirmed Google ranking signal (Google has said it doesn't use it) "
                "but some AI answer engines use it as a curated content map -- optional hygiene, not required.",
            )
        )
    else:
        raw["llms_txt_found"] = True
        link_count = llms_resp.text.count("](")
        raw["llms_txt_link_count"] = link_count
        if link_count > LLMS_TXT_MAX_RECOMMENDED_LINKS:
            findings.append(
                Finding(
                    "low",
                    "llms_txt_too_large",
                    f"llms.txt has ~{link_count} links -- keep it to a curated {LLMS_TXT_MAX_RECOMMENDED_LINKS} or "
                    "fewer rather than dumping the full sitemap",
                )
            )

    return ToolResult(
        tool="ai_crawlers", status="ok", score=score_from_findings(findings), findings=findings, raw=raw
    )
