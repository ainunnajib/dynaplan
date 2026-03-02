import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey


def generate_api_key() -> Tuple[str, str]:
    """Generate a new API key.

    Returns a tuple of (raw_key, key_hash).
    The raw key is in the format "dyp_<32 hex chars>".
    The hash is a SHA-256 hex digest — only the hash is stored.
    """
    raw_key = "dyp_" + secrets.token_hex(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash


async def create_api_key(
    db: AsyncSession,
    user_id: uuid.UUID,
    name: str,
    scopes: List[str],
    rate_limit_per_minute: Optional[int] = 120,
) -> Tuple[ApiKey, str]:
    """Create a new API key for a user.

    Returns (ApiKey model, raw_key). The raw key is only returned once and
    is NOT stored in the database — only the SHA-256 hash is persisted.
    """
    raw_key, key_hash = generate_api_key()
    api_key = ApiKey(
        key_hash=key_hash,
        name=name,
        user_id=user_id,
        scopes=scopes,
        is_active=True,
        rate_limit_per_minute=rate_limit_per_minute or 120,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    return api_key, raw_key


async def validate_api_key(
    db: AsyncSession, raw_key: str
) -> Optional[ApiKey]:
    """Validate a raw API key.

    Hashes the raw key, looks it up in the database, and updates
    last_used_at if found and active. Returns None if invalid or inactive.
    """
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash)
    )
    api_key = result.scalar_one_or_none()
    if api_key is None or not api_key.is_active:
        return None
    api_key.last_used_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(api_key)
    return api_key


async def revoke_api_key(
    db: AsyncSession, key_id: uuid.UUID
) -> Optional[ApiKey]:
    """Revoke an API key by setting is_active=False.

    Returns the updated ApiKey, or None if not found.
    """
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id)
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        return None
    api_key.is_active = False
    await db.commit()
    await db.refresh(api_key)
    return api_key


async def list_api_keys(
    db: AsyncSession, user_id: uuid.UUID
) -> List[ApiKey]:
    """List all API keys for a user (hashes are never returned via the API schema)."""
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.user_id == user_id)
        .order_by(ApiKey.created_at.asc())
    )
    return list(result.scalars().all())


def check_scope(api_key: ApiKey, required_scope: str) -> bool:
    """Return True if the API key has the required scope or has 'admin' scope."""
    scopes = api_key.scopes or []
    return required_scope in scopes or "admin" in scopes
