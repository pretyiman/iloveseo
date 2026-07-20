import ipaddress
import socket
from urllib.parse import urlparse

from fastapi import HTTPException, status


def normalize_domain(value: str) -> str:
    value = value.strip()
    if "://" in value:
        value = urlparse(value).netloc or value
    return value.rstrip("/").removeprefix("www.")


def validate_public_domain(domain: str) -> None:
    """Basic SSRF guard for the unauthenticated anonymous-scan endpoint --
    a Clerk/API-key account provides some accountability on the existing
    authenticated project-creation path, so this isn't retrofitted there.
    Rejects loopback/private/link-local targets before any tool touches
    the domain."""
    hostname = domain.split(":")[0]
    try:
        resolved = socket.gethostbyname(hostname)
    except socket.gaierror as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Could not resolve domain: {domain}") from exc

    ip = ipaddress.ip_address(resolved)
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This domain cannot be scanned.")
