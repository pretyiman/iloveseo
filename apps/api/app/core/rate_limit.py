import time

from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis

from app.core.auth import get_current_user_or_api_key
from app.core.config import get_settings
from app.models.user import User

settings = get_settings()
_redis_client: Redis | None = None


def _get_redis_client() -> Redis:
    """Lazy singleton, matching the JWKS client pattern in app/core/auth.py
    -- one connection pool per process, not one per request."""
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def _check_fixed_window(key: str) -> None:
    client = _get_redis_client()
    count = await client.incr(key)
    if count == 1:
        await client.expire(key, 60)

    if count > settings.rate_limit_per_minute:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Rate limit exceeded ({settings.rate_limit_per_minute} requests/minute).",
        )


async def enforce_rate_limit(user: User = Depends(get_current_user_or_api_key)) -> None:
    """Fixed-window limiter, keyed per user (not per key, so rotating keys
    doesn't reset it) at settings.rate_limit_per_minute requests/minute.
    Covers both dashboard and API-key traffic on routes that depend on it,
    closing the "no API-level rate limiting" gap now that this API is
    reachable by external callers."""
    window = int(time.time() // 60)
    await _check_fixed_window(f"ratelimit:{user.id}:{window}")


async def enforce_public_rate_limit(request: Request) -> None:
    """Same fixed-window limiter for the genuinely unauthenticated public
    report/PDF routes -- there's no User to key on, so this keys on the
    caller's IP instead."""
    window = int(time.time() // 60)
    client_host = request.client.host if request.client else "unknown"
    await _check_fixed_window(f"ratelimit:public:{client_host}:{window}")
