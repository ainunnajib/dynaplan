import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.api_key import VALID_SCOPES, ApiKey
from app.models.user import User
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreatedResponse, ApiKeyResponse
from app.services.api_key import (
    create_api_key,
    list_api_keys,
    revoke_api_key,
)

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.post(
    "",
    response_model=ApiKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_key(
    data: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new API key. The raw key is returned only once."""
    for scope in data.scopes:
        if scope not in VALID_SCOPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid scope: '{scope}'. Valid scopes are: {VALID_SCOPES}",
            )
    api_key, raw_key = await create_api_key(
        db,
        user_id=current_user.id,
        name=data.name,
        scopes=data.scopes,
        rate_limit_per_minute=data.rate_limit_per_minute,
    )
    return ApiKeyCreatedResponse(
        id=api_key.id,
        name=api_key.name,
        user_id=api_key.user_id,
        scopes=api_key.scopes,
        is_active=api_key.is_active,
        rate_limit_per_minute=api_key.rate_limit_per_minute,
        last_used_at=api_key.last_used_at,
        created_at=api_key.created_at,
        updated_at=api_key.updated_at,
        raw_key=raw_key,
    )


@router.get(
    "",
    response_model=List[ApiKeyResponse],
)
async def list_keys(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all API keys for the current user. Raw keys are never returned."""
    keys = await list_api_keys(db, user_id=current_user.id)
    return keys


@router.delete(
    "/{key_id}",
    status_code=status.HTTP_200_OK,
)
async def revoke_key(
    key_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke an API key. Only the key owner can revoke it."""
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id)
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
    if api_key.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to revoke this API key",
        )
    await revoke_api_key(db, key_id=key_id)
    return {"message": "API key revoked successfully"}
