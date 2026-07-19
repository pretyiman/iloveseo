import jwt
from fastapi import Depends, HTTPException, Request, status
from jwt import PyJWKClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api_keys import KEY_PREFIX, resolve_api_key
from app.core.config import get_settings
from app.core.db import get_db
from app.models.user import User

settings = get_settings()
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    """Lazy singleton: PyJWKClient caches fetched signing keys internally,
    so we only want one instance per process rather than one per request."""
    global _jwks_client
    if _jwks_client is None:
        if not settings.clerk_jwks_url:
            raise RuntimeError(
                "CLERK_JWKS_URL is not configured — set it to your Clerk "
                "instance's /.well-known/jwks.json URL"
            )
        _jwks_client = PyJWKClient(settings.clerk_jwks_url, cache_keys=True)
    return _jwks_client


def _get_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    return auth_header.split(" ", 1)[1]


async def _verify_clerk_jwt(token: str, db: AsyncSession) -> User:
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=settings.clerk_issuer or None,
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {exc}") from exc

    clerk_user_id = claims["sub"]
    # Clerk session tokens only include `email` if a custom claim was added
    # in the Clerk dashboard (JWT templates). Falls back to a placeholder
    # so login never breaks on that config being missing.
    email = claims.get("email") or f"{clerk_user_id}@unknown.clerk"

    user = await db.get(User, clerk_user_id)
    if user is None:
        user = User(id=clerk_user_id, email=email)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    """Clerk session auth only -- used by routes that must not be
    reachable with an API key (e.g. creating/revoking API keys themselves,
    to avoid a key being able to mint further keys)."""
    token = _get_bearer_token(request)
    return await _verify_clerk_jwt(token, db)


async def get_current_user_or_api_key(
    request: Request, db: AsyncSession = Depends(get_db)
) -> User:
    """Accepts either a Clerk session JWT (dashboard) or an API key
    (`srk_live_...`, external/CLI callers) on the same endpoints."""
    token = _get_bearer_token(request)
    if token.startswith(KEY_PREFIX):
        user = await resolve_api_key(db, token)
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or revoked API key")
        return user
    return await _verify_clerk_jwt(token, db)
