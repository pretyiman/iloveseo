import socket

import pytest
from fastapi import HTTPException

from app.core.domain_safety import normalize_domain, validate_public_domain


def test_normalize_domain_strips_scheme_www_and_trailing_slash():
    assert normalize_domain("https://www.Example.com/") == "Example.com"
    assert normalize_domain("example.com") == "example.com"


@pytest.mark.parametrize("resolved_ip", ["127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.1.1"])
def test_validate_public_domain_rejects_non_public_addresses(monkeypatch, resolved_ip):
    monkeypatch.setattr(socket, "gethostbyname", lambda host: resolved_ip)
    with pytest.raises(HTTPException) as exc_info:
        validate_public_domain("whatever.example")
    assert exc_info.value.status_code == 400


def test_validate_public_domain_accepts_a_public_address(monkeypatch):
    monkeypatch.setattr(socket, "gethostbyname", lambda host: "93.184.216.34")
    validate_public_domain("example.com")  # does not raise


def test_validate_public_domain_rejects_unresolvable_domain(monkeypatch):
    def _raise(host):
        raise socket.gaierror("not found")

    monkeypatch.setattr(socket, "gethostbyname", _raise)
    with pytest.raises(HTTPException) as exc_info:
        validate_public_domain("does-not-exist.invalid")
    assert exc_info.value.status_code == 400
