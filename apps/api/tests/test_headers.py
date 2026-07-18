import httpx
import pytest
import respx

import app.services.tools.headers as headers_module
from app.services.tools.headers import run

GOOD_TLS_INFO = {
    "protocol": "TLSv1.3",
    "cipher": "TLS_AES_256_GCM_SHA384",
    "expires_at": "2027-01-01T00:00:00+00:00",
    "days_until_expiry": 300,
    "issuer": {"organizationName": "Let's Encrypt"},
}

FULL_SECURITY_HEADERS = {
    "x-frame-options": "DENY",
    "content-security-policy": "default-src 'self'",
    "strict-transport-security": "max-age=63072000; includeSubDomains; preload",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "permissions-policy": "geolocation=()",
    "set-cookie": "session=abc123; Secure; HttpOnly; SameSite=Strict",
}


@pytest.fixture(autouse=True)
def _patch_tls(monkeypatch):
    async def fake_to_thread(fn, *args):
        return GOOD_TLS_INFO

    import asyncio

    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)


@pytest.mark.asyncio
@respx.mock
async def test_fully_hardened_site_scores_high():
    respx.get("https://example.com").mock(
        return_value=httpx.Response(200, headers=FULL_SECURITY_HEADERS)
    )

    result = await run("example.com")

    assert result.status == "ok"
    assert result.score == 100
    blocking = [f for f in result.findings if f.severity in ("critical", "high", "medium")]
    assert blocking == []


@pytest.mark.asyncio
@respx.mock
async def test_bare_headers_flag_everything_missing():
    respx.get("https://example.com").mock(return_value=httpx.Response(200, headers={}))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "hsts_missing" in codes
    assert "csp_missing" in codes
    assert "x_frame_options_missing" in codes


@pytest.mark.asyncio
@respx.mock
async def test_http_scheme_flags_not_https_and_skips_tls():
    respx.get("http://example.com").mock(return_value=httpx.Response(200, headers={}))

    result = await run("http://example.com")

    codes = {f.code for f in result.findings}
    assert "not_https" in codes
    assert "hsts_missing" not in codes  # not applicable, not "missing"
    assert result.raw["hsts"] == "not_applicable"


@pytest.mark.asyncio
@respx.mock
async def test_csp_weaknesses_detected():
    headers = dict(FULL_SECURITY_HEADERS)
    headers["content-security-policy"] = "script-src 'unsafe-inline' 'unsafe-eval' *"
    respx.get("https://example.com").mock(return_value=httpx.Response(200, headers=headers))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "csp_unsafe_inline" in codes
    assert "csp_unsafe_eval" in codes


@pytest.mark.asyncio
@respx.mock
async def test_insecure_cookie_flagged():
    headers = dict(FULL_SECURITY_HEADERS)
    headers["set-cookie"] = "session=abc123"
    respx.get("https://example.com").mock(return_value=httpx.Response(200, headers=headers))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "cookie_missing_secure" in codes
    assert "cookie_missing_httponly" in codes
    assert "cookie_missing_samesite" in codes


@pytest.mark.asyncio
@respx.mock
async def test_cdn_detected_from_header_signature():
    headers = dict(FULL_SECURITY_HEADERS)
    headers["server"] = "cloudflare"
    respx.get("https://example.com").mock(return_value=httpx.Response(200, headers=headers))

    result = await run("example.com")

    assert result.raw["cdn"] == "Cloudflare"


@pytest.mark.asyncio
@respx.mock
async def test_expiring_cert_flagged(monkeypatch):
    import asyncio

    async def fake_to_thread(fn, *args):
        return {**GOOD_TLS_INFO, "days_until_expiry": 5}

    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)
    respx.get("https://example.com").mock(return_value=httpx.Response(200, headers=FULL_SECURITY_HEADERS))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "cert_expiring_soon" in codes
