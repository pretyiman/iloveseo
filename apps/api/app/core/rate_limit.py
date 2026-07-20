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


async def _check_fixed_window(key_prefix: str, window_seconds: int, limit: int) -> None:
    client = _get_redis_client()
    window = int(time.time() // window_seconds)
    key = f"{key_prefix}:{window}"

    count = await client.incr(key)
    if count == 1:
        await client.expire(key, window_seconds)

    if count > limit:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Rate limit exceeded ({limit} requests per {window_seconds}s).",
        )


async def enforce_rate_limit(user: User = Depends(get_current_user_or_api_key)) -> None:
    """Fixed-window limiter, keyed per user (not per key, so rotating keys
    doesn't reset it) at settings.rate_limit_per_minute requests/minute.
    Covers both dashboard and API-key traffic on routes that depend on it,
    closing the "no API-level rate limiting" gap now that this API is
    reachable by external callers."""
    await _check_fixed_window(f"ratelimit:{user.id}", 60, settings.rate_limit_per_minute)


async def enforce_public_rate_limit(request: Request) -> None:
    """Same fixed-window limiter for the genuinely unauthenticated public
    report/PDF routes -- there's no User to key on, so this keys on the
    caller's IP instead."""
    client_host = request.client.host if request.client else "unknown"
    await _check_fixed_window(f"ratelimit:public:{client_host}", 60, settings.rate_limit_per_minute)


async def enforce_anonymous_scan_rate_limit(request: Request) -> None:
    """5/hour per IP by default -- this endpoint runs real tool calls
    (including a live PageSpeed Insights request) against an arbitrary
    caller-supplied domain with no account behind it at all, so it's
    throttled much harder than the existing per-minute limiters."""
    client_host = request.client.host if request.client else "unknown"
    await _check_fixed_window(f"ratelimit:scan:{client_host}", 3600, settings.anonymous_scan_limit_per_hour)
