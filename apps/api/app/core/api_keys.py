import hashlib
import secrets
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey
from app.models.user import User

# Identifies both the product and that this is a live (vs. test) key, the
# same way Stripe/GitHub prefix their tokens -- makes a leaked key
# grep-able in logs and unambiguous at a glance.
KEY_PREFIX = "srk_live_"

# Shown in the dashboard's key list so a user can tell keys apart without
# ever seeing the full secret again after creation.
_DISPLAY_PREFIX_LEN = len(KEY_PREFIX) + 8


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """Returns (raw_key, key_prefix, key_hash). raw_key is shown to the
    caller exactly once, at creation -- only key_hash is ever persisted."""
    raw_key = KEY_PREFIX + secrets.token_urlsafe(32)
    return raw_key, raw_key[:_DISPLAY_PREFIX_LEN], hash_api_key(raw_key)


async def resolve_api_key(db: AsyncSession, raw_key: str) -> User | None:
    """Looks up a non-revoked key by hash and returns its owning User, or
    None if the key doesn't exist or has been revoked. Updates
    last_used_at on every successful lookup."""
    key_hash = hash_api_key(raw_key)
    api_key = await db.scalar(select(ApiKey).where(ApiKey.key_hash == key_hash))
    if api_key is None or api_key.revoked_at is not None:
        return None

    api_key.last_used_at = datetime.now(UTC)
    user = await db.get(User, api_key.user_id)
    await db.commit()
    return user
