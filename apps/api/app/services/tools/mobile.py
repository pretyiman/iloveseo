import re

from app.services.render_client import RenderError, render
from app.services.tools.base import Finding, ToolResult, register_tool, score_from_findings

MIN_TAP_TARGET_PX = 44  # Apple HIG / WCAG 2.5.5, also used internally by Google's mobile usability checks
MIN_FONT_SIZE_PX = 12
TAP_TARGET_CROWDING_GAP_PX = 8
HORIZONTAL_OVERFLOW_TOLERANCE_PX = 5
MAX_TAP_TARGETS_FOR_CROWDING_CHECK = 150

PRIMARY_DEVICE = "iPhone 13"
SECONDARY_DEVICE = "Pixel 5"


def _viewport_checks(viewport_meta: str | None) -> tuple[list[Finding], bool]:
    findings: list[Finding] = []
    if not viewport_meta:
        findings.append(Finding("critical", "viewport_missing", "No viewport meta tag found"))
        return findings, False

    lowered = viewport_meta.lower()
    has_device_width = "width=device-width" in lowered.replace(" ", "")
    if not has_device_width:
        findings.append(
            Finding("high", "viewport_incorrect", f"Viewport meta tag doesn't set width=device-width: '{viewport_meta}'")
        )

    zoom_blocked = "user-scalable=no" in lowered.replace(" ", "") or bool(
        re.search(r"maximum-scale\s*=\s*1(\.0*)?\b", lowered)
    )
    if zoom_blocked:
        findings.append(Finding("high", "zoom_blocked", "Viewport disables pinch-zoom (user-scalable=no / maximum-scale=1)"))

    return findings, has_device_width and not zoom_blocked


def _tap_target_checks(tap_targets: list[dict]) -> tuple[list[Finding], bool]:
    findings: list[Finding] = []
    too_small = [t for t in tap_targets if t["width"] < MIN_TAP_TARGET_PX or t["height"] < MIN_TAP_TARGET_PX]
    if too_small:
        examples = ", ".join(f"<{t['tag']}> '{t['text'][:20]}' ({t['width']}x{t['height']}px)" for t in too_small[:5])
        findings.append(
            Finding(
                "medium",
                "tap_targets_too_small",
                f"{len(too_small)} tap targets are smaller than {MIN_TAP_TARGET_PX}x{MIN_TAP_TARGET_PX}px, e.g. {examples}",
            )
        )

    crowded_pairs = 0
    sample = tap_targets[:MAX_TAP_TARGETS_FOR_CROWDING_CHECK]
    for i, a in enumerate(sample):
        for b in sample[i + 1 :]:
            dx = max(b["x"] - (a["x"] + a["width"]), a["x"] - (b["x"] + b["width"]), 0)
            dy = max(b["y"] - (a["y"] + a["height"]), a["y"] - (b["y"] + b["height"]), 0)
            gap = max(dx, dy)
            if 0 < gap < TAP_TARGET_CROWDING_GAP_PX:
                crowded_pairs += 1
    if crowded_pairs:
        findings.append(
            Finding("low", "tap_targets_crowded", f"{crowded_pairs} pairs of tap targets are closer than {TAP_TARGET_CROWDING_GAP_PX}px apart")
        )

    return findings, len(too_small) == 0


def _font_size_checks(font_sizes: list[float]) -> tuple[list[Finding], bool]:
    too_small = [s for s in font_sizes if s < MIN_FONT_SIZE_PX]
    if not too_small:
        return [], True
    finding = Finding(
        "medium",
        "font_too_small",
        f"{len(too_small)} text elements render smaller than {MIN_FONT_SIZE_PX}px on mobile",
    )
    return [finding], False


def _overflow_checks(scroll_width: int, inner_width: int) -> tuple[list[Finding], bool]:
    if scroll_width - inner_width > HORIZONTAL_OVERFLOW_TOLERANCE_PX:
        return [
            Finding(
                "high",
                "horizontal_overflow",
                f"Page content ({scroll_width}px) overflows the viewport ({inner_width}px), causing horizontal scroll",
            )
        ], False
    return [], True


@register_tool("mobile")
async def run(domain: str) -> ToolResult:
    url = domain if domain.startswith("http") else f"https://{domain}"

    try:
        primary = await render(
            url, device=PRIMARY_DEVICE, throttle=True, capture_screenshot=True, full_page_screenshot=True
        )
    except RenderError as exc:
        return ToolResult(
            tool="mobile",
            status="error",
            score=None,
            findings=[Finding("critical", "render_failed", f"Could not render page: {exc}")],
            raw={"url": url},
        )

    findings: list[Finding] = []

    viewport_findings, viewport_ok = _viewport_checks(primary["viewport_meta_content"])
    findings.extend(viewport_findings)

    tap_findings, tap_ok = _tap_target_checks(primary["tap_targets"])
    findings.extend(tap_findings)

    font_findings, font_ok = _font_size_checks(primary["font_sizes"])
    findings.extend(font_findings)

    overflow_findings, overflow_ok = _overflow_checks(primary["scroll_width"], primary["inner_width"])
    findings.extend(overflow_findings)

    if primary["console_errors"]:
        findings.append(
            Finding("info", "console_errors", f"{len(primary['console_errors'])} JavaScript error(s) during render")
        )

    mobile_friendly = viewport_ok and tap_ok and font_ok and overflow_ok

    secondary_tap_too_small = None
    try:
        secondary = await render(url, device=SECONDARY_DEVICE, throttle=False, capture_screenshot=False)
        secondary_tap_too_small = sum(
            1 for t in secondary["tap_targets"] if t["width"] < MIN_TAP_TARGET_PX or t["height"] < MIN_TAP_TARGET_PX
        )
    except RenderError:
        pass  # secondary device is a cross-check, not required for the result to be usable

    raw = {
        "url": url,
        "mobile_friendly": mobile_friendly,
        "primary_device": PRIMARY_DEVICE,
        "viewport_meta": primary["viewport_meta_content"],
        "tap_target_count": len(primary["tap_targets"]),
        "tap_targets_too_small": sum(
            1 for t in primary["tap_targets"] if t["width"] < MIN_TAP_TARGET_PX or t["height"] < MIN_TAP_TARGET_PX
        ),
        "font_sizes_sampled": len(primary["font_sizes"]),
        "scroll_width": primary["scroll_width"],
        "inner_width": primary["inner_width"],
        "secondary_device": SECONDARY_DEVICE,
        "secondary_tap_targets_too_small": secondary_tap_too_small,
        "screenshot_base64": primary["screenshot_base64"],
    }

    return ToolResult(tool="mobile", status="ok", score=score_from_findings(findings), findings=findings, raw=raw)
