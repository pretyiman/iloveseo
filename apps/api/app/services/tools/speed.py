import httpx

from app.core.config import get_settings
from app.services.tools.base import Finding, ToolResult, register_tool

PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
CATEGORIES = ["performance", "accessibility", "best-practices", "seo"]

# PSI field-data (CrUX) metric key -> our short name.
FIELD_METRIC_KEYS = {
    "LARGEST_CONTENTFUL_PAINT_MS": "lcp",
    "INTERACTION_TO_NEXT_PAINT": "inp",
    "CUMULATIVE_LAYOUT_SHIFT_SCORE": "cls",
    "FIRST_CONTENTFUL_PAINT_MS": "fcp",
    "EXPERIMENTAL_TIME_TO_FIRST_BYTE": "ttfb",
}

LAB_AUDIT_IDS = {
    "first-contentful-paint": "fcp_ms",
    "largest-contentful-paint": "lcp_ms",
    "total-blocking-time": "tbt_ms",
    "cumulative-layout-shift": "cls",
    "speed-index": "speed_index_ms",
    "interactive": "tti_ms",
    "server-response-time": "ttfb_ms",
}


@register_tool("speed")
async def run(domain: str) -> ToolResult:
    settings = get_settings()
    url = domain if domain.startswith("http") else f"https://{domain}"

    if not settings.psi_api_key:
        return ToolResult(
            tool="speed",
            status="error",
            score=None,
            findings=[
                Finding("critical", "psi_api_key_missing", "PSI_API_KEY is not configured -- Speed Test cannot run")
            ],
            raw={"url": url},
        )

    params = [("url", url), ("key", settings.psi_api_key), ("strategy", "mobile")]
    params += [("category", c) for c in CATEGORIES]

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(PSI_ENDPOINT, params=params)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as exc:
        try:
            message = exc.response.json().get("error", {}).get("message", str(exc))
        except ValueError:
            message = str(exc)
        return ToolResult(
            tool="speed",
            status="error",
            score=None,
            findings=[Finding("critical", "psi_request_failed", f"PageSpeed Insights request failed: {message}")],
            raw={"url": url},
        )
    except httpx.HTTPError as exc:
        return ToolResult(
            tool="speed",
            status="error",
            score=None,
            findings=[Finding("critical", "psi_request_failed", f"PageSpeed Insights request failed: {exc}")],
            raw={"url": url},
        )

    findings: list[Finding] = []
    lighthouse = data.get("lighthouseResult", {})
    categories = lighthouse.get("categories", {})
    audits = lighthouse.get("audits", {})

    scores: dict[str, int] = {}
    for cat_key in CATEGORIES:
        cat = categories.get(cat_key)
        if cat and cat.get("score") is not None:
            scores[cat_key] = round(cat["score"] * 100)

    perf_score = scores.get("performance")
    if perf_score is not None:
        if perf_score < 50:
            findings.append(Finding("critical", "performance_score_poor", f"Performance score is {perf_score}/100"))
        elif perf_score < 90:
            findings.append(
                Finding("medium", "performance_score_needs_improvement", f"Performance score is {perf_score}/100")
            )

    for cat_key in ("accessibility", "best-practices", "seo"):
        cat_score = scores.get(cat_key)
        if cat_score is not None and cat_score < 90:
            findings.append(
                Finding("low", f"{cat_key.replace('-', '_')}_score_low", f"{cat_key} score is {cat_score}/100")
            )

    lab_metrics: dict[str, int] = {}
    for audit_id, out_key in LAB_AUDIT_IDS.items():
        audit = audits.get(audit_id)
        if audit and audit.get("numericValue") is not None:
            lab_metrics[out_key] = round(audit["numericValue"])

    # Field (real-user CrUX) data: trust Google's own FAST/AVERAGE/SLOW
    # category per metric rather than recomputing pass/fail against a
    # hardcoded threshold ourselves. Google periodically refines the
    # underlying sampling methodology (e.g. the June 2026 change to how
    # INP is sampled on interaction-heavy pages); that refinement is
    # already reflected in `category` by the time it reaches us, so
    # deferring to it is more correct than re-deriving our own cutoff.
    field_data = data.get("loadingExperience", {}).get("metrics", {})
    field_metrics: dict[str, dict] = {}
    if field_data:
        for api_key, out_key in FIELD_METRIC_KEYS.items():
            metric = field_data.get(api_key)
            if not metric:
                continue
            field_metrics[out_key] = {"percentile": metric.get("percentile"), "category": metric.get("category")}
            if metric.get("category") and metric["category"] != "FAST":
                findings.append(
                    Finding(
                        "medium",
                        f"cwv_{out_key}_not_fast",
                        f"Field data: {out_key.upper()} is {metric['category'].lower()} (percentile {metric.get('percentile')})",
                    )
                )
    else:
        findings.append(
            Finding(
                "info",
                "cwv_field_data_unavailable",
                "No real-user (CrUX) field data available, likely low traffic -- lab data only",
            )
        )

    opportunities = [
        {"id": audit_id, "title": audit.get("title"), "description": audit.get("description")}
        for audit_id, audit in audits.items()
        if audit.get("score") is not None and audit["score"] < 0.9 and audit.get("scoreDisplayMode") in ("numeric", "binary")
    ][:10]

    raw = {
        "url": url,
        "strategy": "mobile",
        "scores": scores,
        "lab_metrics": lab_metrics,
        "field_metrics": field_metrics,
        "opportunities": opportunities,
    }

    return ToolResult(tool="speed", status="ok", score=perf_score, findings=findings, raw=raw)
