import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api_keys import generate_api_key
from app.core.auth import get_current_user
from app.core.db import get_db
from app.core.plan_limits import check_api_key_limit
from app.models.api_key import ApiKey
from app.models.user import User
from app.schemas import ApiKeyCreate, ApiKeyCreated, ApiKeyOut

# Deliberately Clerk-session-only (get_current_user, not
# get_current_user_or_api_key) -- an API key must never be usable to mint
# further keys.
router = APIRouter(prefix="/api-keys", tags=["api-keys"])


async def _get_owned_api_key(db: AsyncSession, user: User, key_id: uuid.UUID) -> ApiKey:
    api_key = await db.get(ApiKey, key_id)
    if api_key is None or api_key.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key not found")
    return api_key


@router.post("", response_model=ApiKeyCreated)
async def create_api_key(
    payload: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApiKeyCreated:
    await check_api_key_limit(db, user)

    raw_key, key_prefix, key_hash = generate_api_key()
    api_key = ApiKey(user_id=user.id, name=payload.name, key_prefix=key_prefix, key_hash=key_hash)
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return ApiKeyCreated(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        key=raw_key,
        created_at=api_key.created_at,
    )


@router.get("", response_model=list[ApiKeyOut])
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ApiKey]:
    result = await db.scalars(
        select(ApiKey)
        .where(ApiKey.user_id == user.id, ApiKey.revoked_at.is_(None))
        .order_by(ApiKey.created_at.desc())
    )
    return list(result)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    api_key = await _get_owned_api_key(db, user, key_id)
    api_key.revoked_at = datetime.now(UTC)
    await db.commit()
