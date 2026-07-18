import asyncio
import socket
import ssl
from datetime import datetime, timezone
from urllib.parse import urlparse

import dns.asyncresolver
import dns.exception
import dns.resolver
import httpx

from app.services.tools.base import Finding, ToolResult, register_tool, score_from_findings

# Any of these substrings appearing in the negotiated cipher name indicates
# a known-weak cipher (stream ciphers, export-grade, no forward secrecy).
WEAK_CIPHER_MARKERS = ["RC4", "DES", "3DES", "NULL", "EXPORT", "_MD5", "PSK", "ANON"]

HSTS_PRELOAD_API = "https://hstspreload.org/api/v2/status"


def _grade_cipher(cipher_name: str) -> str:
    upper = cipher_name.upper()
    return "weak" if any(marker in upper for marker in WEAK_CIPHER_MARKERS) else "strong"


def _get_tls_info(hostname: str) -> dict:
    """Blocking TLS handshake -- run via asyncio.to_thread. ssl/socket have
    no async equivalent worth depending on for a single once-per-scan
    connection."""
    ctx = ssl.create_default_context()
    with socket.create_connection((hostname, 443), timeout=10) as sock:
        with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
            cert = ssock.getpeercert()
            protocol = ssock.version()
            cipher = ssock.cipher()

    not_after = cert.get("notAfter")
    expires_at = (
        datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc) if not_after else None
    )
    days_until_expiry = (expires_at - datetime.now(timezone.utc)).days if expires_at else None
    cipher_name = cipher[0] if cipher else None

    return {
        "protocol": protocol,
        "cipher": cipher_name,
        "cipher_grade": _grade_cipher(cipher_name) if cipher_name else None,
        "issuer": dict(x[0] for x in cert.get("issuer", [])),
        "expires_at": expires_at.isoformat() if expires_at else None,
        "days_until_expiry": days_until_expiry,
    }


async def _txt_records(name: str) -> list[str]:
    try:
        answers = await dns.asyncresolver.resolve(name, "TXT", lifetime=5)
        return ["".join(part.decode() if isinstance(part, bytes) else part for part in rec.strings) for rec in answers]
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.Timeout, dns.resolver.NoNameservers):
        return []


async def _check_hsts_preload(client: httpx.AsyncClient, hostname: str) -> str | None:
    try:
        resp = await client.get(HSTS_PRELOAD_API, params={"domain": hostname}, timeout=10)
        resp.raise_for_status()
        return resp.json().get("status")
    except httpx.HTTPError:
        return None


@register_tool("ssl_dns")
async def run(domain: str) -> ToolResult:
    url = domain if domain.startswith("http") else f"https://{domain}"
    hostname = urlparse(url).hostname or domain
    findings: list[Finding] = []
    raw: dict = {"hostname": hostname}

    if not url.startswith("https"):
        return ToolResult(
            tool="ssl_dns",
            status="ok",
            score=0,
            findings=[Finding("critical", "not_https", "Site does not serve over HTTPS -- no TLS to evaluate")],
            raw=raw,
        )

    try:
        tls_info = await asyncio.to_thread(_get_tls_info, hostname)
        raw["tls"] = tls_info
    except (OSError, ssl.SSLError) as exc:
        return ToolResult(
            tool="ssl_dns",
            status="error",
            score=None,
            findings=[Finding("critical", "tls_handshake_failed", f"Could not complete TLS handshake: {exc}")],
            raw=raw,
        )

    days_left = tls_info["days_until_expiry"]
    if days_left is not None:
        if days_left < 14:
            findings.append(Finding("critical", "cert_expiring_soon", f"TLS certificate expires in {days_left} days"))
        elif days_left < 30:
            findings.append(Finding("medium", "cert_expiring_soon", f"TLS certificate expires in {days_left} days"))

    if tls_info["protocol"] in ("TLSv1", "TLSv1.1"):
        findings.append(Finding("high", "weak_tls_protocol", f"Server negotiated outdated {tls_info['protocol']}"))

    if tls_info["cipher_grade"] == "weak":
        findings.append(Finding("high", "weak_cipher", f"Server negotiated a weak cipher: {tls_info['cipher']}"))

    async with httpx.AsyncClient() as client:
        preload_status, spf_records, dmarc_records = await asyncio.gather(
            _check_hsts_preload(client, hostname),
            _txt_records(hostname),
            _txt_records(f"_dmarc.{hostname}"),
        )

    raw["hsts_preload_status"] = preload_status

    spf = [r for r in spf_records if r.startswith("v=spf1")]
    raw["spf"] = spf[0] if spf else None
    if not spf:
        findings.append(
            Finding("low", "spf_missing", "No SPF record found -- reduces protection against email spoofing of this domain")
        )

    dmarc = [r for r in dmarc_records if r.startswith("v=DMARC1")]
    raw["dmarc"] = dmarc[0] if dmarc else None
    if not dmarc:
        findings.append(Finding("low", "dmarc_missing", "No DMARC record found at _dmarc subdomain"))
    elif "p=none" in dmarc[0].lower():
        findings.append(
            Finding("info", "dmarc_monitoring_only", "DMARC policy is 'p=none' (monitoring only, not enforcing)")
        )

    return ToolResult(tool="ssl_dns", status="ok", score=score_from_findings(findings), findings=findings, raw=raw)
