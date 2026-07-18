import asyncio

import dns.asyncresolver
import dns.resolver
import httpx
import pytest
import respx

import app.services.tools.ssl_dns as ssl_dns_module
from app.services.tools.ssl_dns import run

GOOD_TLS_INFO = {
    "protocol": "TLSv1.3",
    "cipher": "TLS_AES_256_GCM_SHA384",
    "cipher_grade": "strong",
    "issuer": {"organizationName": "Let's Encrypt"},
    "expires_at": "2027-01-01T00:00:00+00:00",
    "days_until_expiry": 300,
}


class _FakeRecord:
    def __init__(self, strings: list[bytes]):
        self.strings = strings


def _patch_tls(monkeypatch, tls_info=GOOD_TLS_INFO):
    async def fake_to_thread(fn, *args):
        return tls_info

    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)


def _patch_dns(monkeypatch, spf: str | None = "v=spf1 include:_spf.google.com ~all", dmarc: str | None = "v=DMARC1; p=reject;"):
    async def fake_resolve(name, rdtype, lifetime=5):
        if name == "example.com" and spf:
            return [_FakeRecord([spf.encode()])]
        if name == "_dmarc.example.com" and dmarc:
            return [_FakeRecord([dmarc.encode()])]
        raise dns.resolver.NXDOMAIN()

    monkeypatch.setattr(dns.asyncresolver, "resolve", fake_resolve)


@pytest.mark.asyncio
@respx.mock
async def test_healthy_domain_scores_high(monkeypatch):
    _patch_tls(monkeypatch)
    _patch_dns(monkeypatch)
    respx.get("https://hstspreload.org/api/v2/status").mock(return_value=httpx.Response(200, json={"status": "preloaded"}))

    result = await run("example.com")

    assert result.status == "ok"
    assert result.score == 100
    assert result.raw["spf"].startswith("v=spf1")
    assert result.raw["dmarc"].startswith("v=DMARC1")
    assert result.raw["hsts_preload_status"] == "preloaded"


@pytest.mark.asyncio
async def test_not_https_scores_zero():
    result = await run("http://example.com")

    assert result.score == 0
    assert result.findings[0].code == "not_https"


@pytest.mark.asyncio
@respx.mock
async def test_expiring_cert_flagged(monkeypatch):
    _patch_tls(monkeypatch, {**GOOD_TLS_INFO, "days_until_expiry": 5})
    _patch_dns(monkeypatch)
    respx.get("https://hstspreload.org/api/v2/status").mock(return_value=httpx.Response(200, json={"status": "unknown"}))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "cert_expiring_soon" in codes
    assert any(f.severity == "critical" for f in result.findings if f.code == "cert_expiring_soon")


@pytest.mark.asyncio
@respx.mock
async def test_weak_protocol_and_cipher_flagged(monkeypatch):
    _patch_tls(monkeypatch, {**GOOD_TLS_INFO, "protocol": "TLSv1.1", "cipher": "ECDHE-RSA-RC4-SHA", "cipher_grade": "weak"})
    _patch_dns(monkeypatch)
    respx.get("https://hstspreload.org/api/v2/status").mock(return_value=httpx.Response(200, json={"status": "unknown"}))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "weak_tls_protocol" in codes
    assert "weak_cipher" in codes


@pytest.mark.asyncio
@respx.mock
async def test_missing_spf_and_dmarc_flagged(monkeypatch):
    _patch_tls(monkeypatch)
    _patch_dns(monkeypatch, spf=None, dmarc=None)
    respx.get("https://hstspreload.org/api/v2/status").mock(return_value=httpx.Response(200, json={"status": "unknown"}))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "spf_missing" in codes
    assert "dmarc_missing" in codes


@pytest.mark.asyncio
@respx.mock
async def test_dmarc_monitoring_only_flagged(monkeypatch):
    _patch_tls(monkeypatch)
    _patch_dns(monkeypatch, dmarc="v=DMARC1; p=none;")
    respx.get("https://hstspreload.org/api/v2/status").mock(return_value=httpx.Response(200, json={"status": "unknown"}))

    result = await run("example.com")

    codes = {f.code for f in result.findings}
    assert "dmarc_monitoring_only" in codes


@pytest.mark.asyncio
async def test_tls_handshake_failure_returns_error(monkeypatch):
    async def fake_to_thread(fn, *args):
        raise OSError("connection refused")

    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)

    result = await run("example.com")

    assert result.status == "error"
    assert result.findings[0].code == "tls_handshake_failed"
