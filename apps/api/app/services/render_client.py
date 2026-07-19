import httpx

from app.core.config import get_settings


class RenderError(Exception):
    pass


async def render(
    url: str,
    device: str | None = None,
    throttle: bool = False,
    capture_screenshot: bool = False,
    full_page_screenshot: bool = False,
    timeout_ms: int = 20000,
) -> dict:
    settings = get_settings()
    payload = {
        "url": url,
        "device": device,
        "throttle": throttle,
        "capture_screenshot": capture_screenshot,
        "full_page_screenshot": full_page_screenshot,
        "timeout_ms": timeout_ms,
    }
    try:
        async with httpx.AsyncClient(timeout=(timeout_ms / 1000) + 10) as client:
            resp = await client.post(f"{settings.render_sidecar_url}/render", json=payload)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        raise RenderError(str(exc)) from exc


async def run_accessibility_scan(url: str, device: str | None = None, timeout_ms: int = 20000) -> dict:
    settings = get_settings()
    payload = {"url": url, "device": device, "timeout_ms": timeout_ms}
    try:
        async with httpx.AsyncClient(timeout=(timeout_ms / 1000) + 10) as client:
            resp = await client.post(f"{settings.render_sidecar_url}/accessibility", json=payload)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        raise RenderError(str(exc)) from exc


async def render_pdf(url: str, timeout_ms: int = 20000) -> bytes:
    settings = get_settings()
    payload = {"url": url, "timeout_ms": timeout_ms}
    try:
        async with httpx.AsyncClient(timeout=(timeout_ms / 1000) + 10) as client:
            resp = await client.post(f"{settings.render_sidecar_url}/pdf", json=payload)
        resp.raise_for_status()
        return resp.content
    except httpx.HTTPError as exc:
        raise RenderError(str(exc)) from exc
