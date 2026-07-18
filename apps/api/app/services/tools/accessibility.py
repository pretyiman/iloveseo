from app.services.render_client import RenderError, run_accessibility_scan
from app.services.tools.base import Finding, ToolResult, register_tool, score_from_findings

# axe-core's own impact taxonomy, mapped onto ours.
IMPACT_TO_SEVERITY = {
    "critical": "critical",
    "serious": "high",
    "moderate": "medium",
    "minor": "low",
}


@register_tool("accessibility")
async def run(domain: str) -> ToolResult:
    url = domain if domain.startswith("http") else f"https://{domain}"

    try:
        scan = await run_accessibility_scan(url)
    except RenderError as exc:
        return ToolResult(
            tool="accessibility",
            status="error",
            score=None,
            findings=[Finding("critical", "scan_failed", f"Could not run accessibility scan: {exc}")],
            raw={"url": url},
        )

    findings: list[Finding] = []
    for violation in scan["violations"]:
        severity = IMPACT_TO_SEVERITY.get(violation["impact"], "medium")
        plural = "s" if violation["node_count"] != 1 else ""
        findings.append(
            Finding(
                severity,
                f"axe_{violation['id']}",
                f"{violation['help']} ({violation['node_count']} element{plural}) -- {violation['help_url']}",
            )
        )

    raw = {
        "url": url,
        "violations": scan["violations"],
        "passes_count": scan["passes_count"],
        "incomplete_count": scan["incomplete_count"],
    }

    return ToolResult(tool="accessibility", status="ok", score=score_from_findings(findings), findings=findings, raw=raw)
