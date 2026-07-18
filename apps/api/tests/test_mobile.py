import pytest

import app.services.tools.mobile as mobile_module
from app.services.render_client import RenderError
from app.services.tools.mobile import run

GOOD_TAP_TARGET = {"tag": "a", "text": "Home", "x": 10, "y": 10, "width": 60, "height": 60}


def _base_render_result(**overrides):
    result = {
        "viewport_meta_content": "width=device-width, initial-scale=1",
        "tap_targets": [GOOD_TAP_TARGET],
        "font_sizes": [16, 18, 16],
        "scroll_width": 390,
        "inner_width": 390,
        "console_errors": [],
        "screenshot_base64": "abc123",
    }
    result.update(overrides)
    return result


def _patch_render(monkeypatch, primary_result, secondary_result=None, secondary_raises=False):
    async def fake_render(url, device=None, throttle=False, capture_screenshot=False, full_page_screenshot=False, timeout_ms=20000):
        if device == mobile_module.PRIMARY_DEVICE:
            return primary_result
        if secondary_raises:
            raise RenderError("secondary device unavailable")
        return secondary_result or _base_render_result()

    monkeypatch.setattr(mobile_module, "render", fake_render)


@pytest.mark.asyncio
async def test_good_page_is_mobile_friendly(monkeypatch):
    _patch_render(monkeypatch, _base_render_result())

    result = await run("example.com")

    assert result.status == "ok"
    assert result.raw["mobile_friendly"] is True
    assert result.score == 100


@pytest.mark.asyncio
async def test_missing_viewport_flagged_critical(monkeypatch):
    _patch_render(monkeypatch, _base_render_result(viewport_meta_content=None))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "viewport_missing" in codes
    assert result.raw["mobile_friendly"] is False


@pytest.mark.asyncio
async def test_zoom_blocked_flagged(monkeypatch):
    _patch_render(monkeypatch, _base_render_result(viewport_meta_content="width=device-width, user-scalable=no"))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "zoom_blocked" in codes


@pytest.mark.asyncio
async def test_small_tap_targets_flagged(monkeypatch):
    small_target = {"tag": "button", "text": "Buy", "x": 0, "y": 0, "width": 20, "height": 20}
    _patch_render(monkeypatch, _base_render_result(tap_targets=[small_target]))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "tap_targets_too_small" in codes
    assert result.raw["tap_targets_too_small"] == 1
    assert result.raw["mobile_friendly"] is False


@pytest.mark.asyncio
async def test_crowded_tap_targets_flagged(monkeypatch):
    a = {"tag": "a", "text": "A", "x": 0, "y": 0, "width": 50, "height": 50}
    b = {"tag": "a", "text": "B", "x": 52, "y": 0, "width": 50, "height": 50}  # 2px gap
    _patch_render(monkeypatch, _base_render_result(tap_targets=[a, b]))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "tap_targets_crowded" in codes


@pytest.mark.asyncio
async def test_small_font_flagged(monkeypatch):
    _patch_render(monkeypatch, _base_render_result(font_sizes=[16, 10, 11]))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "font_too_small" in codes


@pytest.mark.asyncio
async def test_horizontal_overflow_flagged(monkeypatch):
    _patch_render(monkeypatch, _base_render_result(scroll_width=600, inner_width=390))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "horizontal_overflow" in codes


@pytest.mark.asyncio
async def test_render_failure_returns_error_status(monkeypatch):
    async def failing_render(url, **kwargs):
        raise RenderError("sidecar unreachable")

    monkeypatch.setattr(mobile_module, "render", failing_render)

    result = await run("example.com")

    assert result.status == "error"
    assert result.findings[0].code == "render_failed"


@pytest.mark.asyncio
async def test_secondary_device_failure_does_not_break_result(monkeypatch):
    _patch_render(monkeypatch, _base_render_result(), secondary_raises=True)

    result = await run("example.com")

    assert result.status == "ok"
    assert result.raw["secondary_tap_targets_too_small"] is None
