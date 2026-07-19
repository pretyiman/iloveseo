import secrets


def generate_share_token() -> str:
    """A share token grants read-only access to one report to anyone who
    has the link -- like a "anyone with the link" doc share, not an
    account credential -- so it's stored and compared in plaintext rather
    than hashed like an API key."""
    return secrets.token_urlsafe(24)
