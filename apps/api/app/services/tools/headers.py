import asyncio
import socket
import ssl
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from urllib.parse import urlparse

import httpx

from app.services.tools.base import Finding, ToolResult, register_tool, score_from_findings

SECURITY_HEADERS: dict[str, tuple[str, str]] = {
    "x-frame-options": ("x_frame_options_missing", "low"),
    "content-security-policy": ("csp_missing", "medium"),
    "x-content-type-options": ("x_content_type_options_missing", "low"),
    "referrer-policy": ("referrer_policy_missing", "low"),
    "permissions-policy": ("permissions_policy_missing", "info"),
}

# Header-signature -> (vendor, source description). Checked in order;
# first match wins per header. Real fingerprints used by
# SecurityHeaders.com / Wappalyzer-style CDN detection.
CDN_SIGNATURES: list[tuple[str, str, str]] = [
    ("server", "cloudflare", "Cloudflare"),
    ("cf-ray", "", "Cloudflare"),
    ("server", "akamaighost", "Akamai"),
    ("x-akamai-transformed", "", "Akamai"),
    ("x-served-by", "cache-", "Fastly"),
    ("via", "varnish", "Varnish"),
    ("x-amz-cf-id", "", "AWS CloudFront"),
    ("x-amz-cf-pop", "", "AWS CloudFront"),
    ("x-sucuri-id", "", "Sucuri"),
    ("x-sucuri-cache", "", "Sucuri"),
    ("x-iinfo", "", "Incapsula"),
    ("x-cdn", "incapsula", "Incapsula"),
    ("server", "nginx", "Nginx (origin, not a CDN)"),
]


def _classify_redirect(status_code: int) -> str:
    return "permanent" if status_code in (301, 308) else "temporary"


def _scan_csp(csp_value: str) -> list[Finding]:
    findings: list[Finding] = []
    lowered = csp_value.lower()
    if "unsafe-inline" in lowered:
        findings.append(
            Finding("medium", "csp_unsafe_inline", "CSP allows 'unsafe-inline', undermining XSS protection")
        )
    if "unsafe-eval" in lowered:
        findings.append(Finding("medium", "csp_unsafe_eval", "CSP allows 'unsafe-eval', undermining XSS protection"))
    if " *;" in f" {lowered};" or lowered.strip().endswith("*") or "script-src *" in lowered:
        findings.append(Finding("medium", "csp_wildcard_source", "CSP contains a wildcard (*) script source"))
    return findings


def _detect_cdn(headers: httpx.Headers) -> str | None:
    for header_name, needle, vendor in CDN_SIGNATURES:
        value = headers.get(header_name, "")
        if value and (needle == "" or needle in value.lower()):
            return vendor
    return None


def _audit_cookies(set_cookie_headers: list[str], is_https: bool) -> tuple[list[Finding], list[dict]]:
    findings: list[Finding] = []
    cookies_info: list[dict] = []
    for raw in set_cookie_headers:
        jar: SimpleCookie = SimpleCookie()
        try:
            jar.load(raw)
        except Exception:  # noqa: BLE001 -- a malformed Set-Cookie header shouldn't crash the scan
            continue
        for name, morsel in jar.items():
            secure = bool(morsel["secure"])
            httponly = bool(morsel["httponly"])
            samesite = morsel["samesite"] or None
            cookies_info.append({"name": name, "secure": secure, "httponly": httponly, "samesite": samesite})
            if is_https and not secure:
                findings.append(Finding("medium", "cookie_missing_secure", f"Cookie '{name}' is missing the Secure flag"))
            if not httponly:
                findings.append(
                    Finding("medium", "cookie_missing_httponly", f"Cookie '{name}' is missing the HttpOnly flag")
                )
            if not samesite:
                findings.append(Finding("low", "cookie_missing_samesite", f"Cookie '{name}' has no SameSite attribute"))
    return findings, cookies_info


def _get_tls_info(hostname: str) -> dict:
    """Blocking TLS handshake to read certificate + protocol info. Run via
    asyncio.to_thread since ssl/socket here has no async equivalent worth
    depending on for a single once-per-scan connection."""
    ctx = ssl.create_default_context()
    with socket.create_connection((hostname, 443), timeout=10) as sock:
        with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
            cert = ssock.getpeercert()
            protocol = ssock.version()
            cipher = ssock.cipher()

    not_after = cert.get("notAfter")
    expires_at = None
    days_until_expiry = None
    if not_after:
        expires_at = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        days_until_expiry = (expires_at - datetime.now(timezone.utc)).days

    return {
        "protocol": protocol,
        "cipher": cipher[0] if cipher else None,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "days_until_expiry": days_until_expiry,
        "issuer": dict(x[0] for x in cert.get("issuer", [])),
    }


@register_tool("http_headers")
async def run(domain: str) -> ToolResult:
    url = domain if domain.startswith("http") else f"https://{domain}"
    findings: list[Finding] = []

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            resp = await client.get(url, headers={"User-Agent": "SEORepairKit/1.0 (+audit)"})
    except httpx.HTTPError as exc:
        return ToolResult(
            tool="http_headers",
            status="error",
            score=None,
            findings=[Finding("critical", "fetch_failed", f"Could not fetch page: {exc}")],
            raw={"url": url},
        )

    is_https = urlparse(str(resp.url)).scheme == "https"
    raw: dict = {
        "url": str(resp.url),
        "status_code": resp.status_code,
        "is_https": is_https,
        "headers": dict(resp.headers),
    }

    if not is_https:
        findings.append(Finding("critical", "not_https", "Site does not serve over HTTPS"))
        raw["hsts"] = "not_applicable"
    else:
        if "strict-transport-security" not in resp.headers:
            findings.append(
                Finding("high", "hsts_missing", "Strict-Transport-Security header missing on an HTTPS site")
            )
        raw["hsts"] = resp.headers.get("strict-transport-security")

    for header_name, (code, severity) in SECURITY_HEADERS.items():
        if header_name not in resp.headers:
            findings.append(Finding(severity, code, f"Missing '{header_name}' response header"))

    csp = resp.headers.get("content-security-policy")
    if csp:
        findings.extend(_scan_csp(csp))

    if "server" in resp.headers:
        raw["server"] = resp.headers["server"]
        findings.append(Finding("info", "server_header_present", f"Server header leaks: {resp.headers['server']}"))
    if "x-powered-by" in resp.headers:
        raw["x_powered_by"] = resp.headers["x-powered-by"]
        findings.append(
            Finding("info", "x_powered_by_present", f"X-Powered-By header leaks: {resp.headers['x-powered-by']}")
        )

    raw["cdn"] = _detect_cdn(resp.headers)

    cookie_findings, cookies_info = _audit_cookies(resp.headers.get_list("set-cookie"), is_https)
    findings.extend(cookie_findings)
    raw["cookies"] = cookies_info

    if is_https:
        try:
            hostname = urlparse(str(resp.url)).hostname
            tls_info = await asyncio.to_thread(_get_tls_info, hostname)
            raw["tls"] = tls_info
            days_left = tls_info["days_until_expiry"]
            if days_left is not None:
                if days_left < 14:
                    findings.append(
                        Finding("critical", "cert_expiring_soon", f"TLS certificate expires in {days_left} days")
                    )
                elif days_left < 30:
                    findings.append(
                        Finding("medium", "cert_expiring_soon", f"TLS certificate expires in {days_left} days")
                    )
            if tls_info["protocol"] in ("TLSv1", "TLSv1.1"):
                findings.append(
                    Finding("high", "weak_tls_protocol", f"Server negotiated outdated {tls_info['protocol']}")
                )
        except (OSError, ssl.SSLError) as exc:
            raw["tls"] = {"error": str(exc)}

    return ToolResult(
        tool="http_headers", status="ok", score=score_from_findings(findings), findings=findings, raw=raw
    )
