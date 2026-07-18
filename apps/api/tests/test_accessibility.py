import pytest

import app.services.tools.accessibility as accessibility_module
from app.services.render_client import RenderError
from app.services.tools.accessibility import run


def _scan(violations=None, passes=10, incomplete=0):
    return {"url": "https://example.com", "violations": violations or [], "passes_count": passes, "incomplete_count": incomplete}


def _violation(id_, impact, node_count=1):
    return {
        "id": id_,
        "impact": impact,
        "description": "desc",
        "help": f"Fix {id_}",
        "help_url": f"https://dequeuniversity.com/rules/axe/{id_}",
        "tags": [],
        "node_count": node_count,
        "sample_targets": [],
    }


@pytest.mark.asyncio
async def test_clean_page_scores_high(monkeypatch):
    async def fake_scan(url, device=None, timeout_ms=20000):
        return _scan()

    monkeypatch.setattr(accessibility_module, "run_accessibility_scan", fake_scan)

    result = await run("example.com")

    assert result.status == "ok"
    assert result.score == 100
    assert result.findings == []


@pytest.mark.asyncio
async def test_impact_severities_mapped_correctly(monkeypatch):
    async def fake_scan(url, device=None, timeout_ms=20000):
        return _scan(
            violations=[
                _violation("color-contrast", "serious"),
                _violation("image-alt", "critical"),
                _violation("landmark-one-main", "moderate"),
                _violation("empty-heading", "minor"),
            ]
        )

    monkeypatch.setattr(accessibility_module, "run_accessibility_scan", fake_scan)

    result = await run("example.com")

    by_code = {f.code: f.severity for f in result.findings}
    assert by_code["axe_color-contrast"] == "high"
    assert by_code["axe_image-alt"] == "critical"
    assert by_code["axe_landmark-one-main"] == "medium"
    assert by_code["axe_empty-heading"] == "low"


@pytest.mark.asyncio
async def test_scan_failure_returns_error_status(monkeypatch):
    async def failing_scan(url, device=None, timeout_ms=20000):
        raise RenderError("sidecar unreachable")

    monkeypatch.setattr(accessibility_module, "run_accessibility_scan", failing_scan)

    result = await run("example.com")

    assert result.status == "error"
    assert result.findings[0].code == "scan_failed"
