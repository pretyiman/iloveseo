import types

import httpx
import pytest
import respx

import app.services.tools.speed as speed_module
from app.services.tools.speed import run


def _fake_settings(api_key: str = "test-psi-key"):
    return types.SimpleNamespace(psi_api_key=api_key)


def _psi_response(perf_score=0.95, lcp_category="FAST", include_field_data=True):
    body = {
        "lighthouseResult": {
            "categories": {
                "performance": {"score": perf_score},
                "accessibility": {"score": 0.98},
                "best-practices": {"score": 1.0},
                "seo": {"score": 1.0},
            },
            "audits": {
                "first-contentful-paint": {"numericValue": 900},
                "largest-contentful-paint": {"numericValue": 1800},
                "total-blocking-time": {"numericValue": 50},
                "cumulative-layout-shift": {"numericValue": 0.02},
                "speed-index": {"numericValue": 1500},
                "interactive": {"numericValue": 2000},
                "server-response-time": {"numericValue": 200},
                "render-blocking-resources": {
                    "score": 0.5,
                    "scoreDisplayMode": "numeric",
                    "title": "Eliminate render-blocking resources",
                    "description": "...",
                },
            },
        },
    }
    if include_field_data:
        body["loadingExperience"] = {
            "metrics": {
                "LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 1800, "category": lcp_category},
                "INTERACTION_TO_NEXT_PAINT": {"percentile": 120, "category": "FAST"},
                "CUMULATIVE_LAYOUT_SHIFT_SCORE": {"percentile": 2, "category": "FAST"},
            }
        }
    return body


@pytest.mark.asyncio
async def test_missing_api_key_returns_error(monkeypatch):
    monkeypatch.setattr(speed_module, "get_settings", lambda: _fake_settings(api_key=""))

    result = await run("example.com")

    assert result.status == "error"
    assert result.findings[0].code == "psi_api_key_missing"


@pytest.mark.asyncio
@respx.mock
async def test_fast_site_has_no_cwv_findings(monkeypatch):
    monkeypatch.setattr(speed_module, "get_settings", _fake_settings)
    respx.get(speed_module.PSI_ENDPOINT).mock(return_value=httpx.Response(200, json=_psi_response()))

    result = await run("example.com")

    assert result.status == "ok"
    assert result.score == 95
    codes = {f.code for f in result.findings}
    assert not any(c.startswith("cwv_") and c.endswith("_not_fast") for c in codes)
    assert "cwv_field_data_unavailable" not in codes
    assert len(result.raw["opportunities"]) == 1


@pytest.mark.asyncio
@respx.mock
async def test_poor_performance_score_flagged_critical(monkeypatch):
    monkeypatch.setattr(speed_module, "get_settings", _fake_settings)
    respx.get(speed_module.PSI_ENDPOINT).mock(return_value=httpx.Response(200, json=_psi_response(perf_score=0.3)))

    result = await run("example.com")

    assert result.score == 30
    codes = {f.code for f in result.findings}
    assert "performance_score_poor" in codes


@pytest.mark.asyncio
@respx.mock
async def test_slow_field_metric_flagged(monkeypatch):
    monkeypatch.setattr(speed_module, "get_settings", _fake_settings)
    respx.get(speed_module.PSI_ENDPOINT).mock(
        return_value=httpx.Response(200, json=_psi_response(lcp_category="SLOW"))
    )

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "cwv_lcp_not_fast" in codes


@pytest.mark.asyncio
@respx.mock
async def test_missing_field_data_is_info_only(monkeypatch):
    monkeypatch.setattr(speed_module, "get_settings", _fake_settings)
    respx.get(speed_module.PSI_ENDPOINT).mock(
        return_value=httpx.Response(200, json=_psi_response(include_field_data=False))
    )

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "cwv_field_data_unavailable" in codes


@pytest.mark.asyncio
@respx.mock
async def test_opportunity_surfaced_as_info_finding(monkeypatch):
    monkeypatch.setattr(speed_module, "get_settings", _fake_settings)
    respx.get(speed_module.PSI_ENDPOINT).mock(return_value=httpx.Response(200, json=_psi_response()))

    result = await run("example.com")

    matches = [f for f in result.findings if f.code == "opportunity_render-blocking-resources"]
    assert len(matches) == 1
    assert matches[0].severity == "info"
    assert matches[0].message == "Improvement opportunity: Eliminate render-blocking resources"


@pytest.mark.asyncio
@respx.mock
async def test_psi_error_response_returns_error_status(monkeypatch):
    monkeypatch.setattr(speed_module, "get_settings", _fake_settings)
    respx.get(speed_module.PSI_ENDPOINT).mock(
        return_value=httpx.Response(400, json={"error": {"message": "Invalid URL"}})
    )

    result = await run("example.com")

    assert result.status == "error"
    assert "Invalid URL" in result.findings[0].message
