import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.model_encryption import (
    ModelEncryptionEnableRequest,
    ModelEncryptionKeyResponse,
    ModelEncryptionRotateRequest,
    ModelEncryptionStatusResponse,
)
from app.services.model_encryption import (
    ModelEncryptionNotEnabledError,
    ModelEncryptionProviderError,
    ModelEncryptionValidationError,
    enable_model_encryption,
    get_model_encryption_status,
    list_model_encryption_keys,
    rotate_model_encryption_key,
)
from app.services.planning_model import get_model_by_id

router = APIRouter(tags=["model-encryption"])


async def _require_model_exists(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    del current_user
    model = await get_model_by_id(db, model_id)
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )
    return model


@router.get(
    "/models/{model_id}/encryption",
    response_model=ModelEncryptionStatusResponse,
)
async def get_model_encryption_status_endpoint(
    model_id: uuid.UUID,
    model=Depends(_require_model_exists),
    db: AsyncSession = Depends(get_db),
):
    del model
    status_data = await get_model_encryption_status(db, model_id)
    return ModelEncryptionStatusResponse(**status_data)


@router.get(
    "/models/{model_id}/encryption/keys",
    response_model=List[ModelEncryptionKeyResponse],
)
async def list_model_encryption_keys_endpoint(
    model_id: uuid.UUID,
    model=Depends(_require_model_exists),
    db: AsyncSession = Depends(get_db),
):
    del model
    return await list_model_encryption_keys(db, model_id)


@router.post(
    "/models/{model_id}/encryption/enable",
    response_model=ModelEncryptionStatusResponse,
)
async def enable_model_encryption_endpoint(
    model_id: uuid.UUID,
    data: ModelEncryptionEnableRequest,
    model=Depends(_require_model_exists),
    db: AsyncSession = Depends(get_db),
):
    del model
    try:
        await enable_model_encryption(
            db,
            model_id=model_id,
            kms_provider=data.kms_provider,
            kms_key_id=data.kms_key_id,
        )
    except ModelEncryptionValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ModelEncryptionProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    status_data = await get_model_encryption_status(db, model_id)
    return ModelEncryptionStatusResponse(**status_data)


@router.post(
    "/models/{model_id}/encryption/rotate",
    response_model=ModelEncryptionStatusResponse,
)
async def rotate_model_encryption_key_endpoint(
    model_id: uuid.UUID,
    data: ModelEncryptionRotateRequest,
    model=Depends(_require_model_exists),
    db: AsyncSession = Depends(get_db),
):
    del model
    try:
        await rotate_model_encryption_key(
            db,
            model_id=model_id,
            kms_provider=data.kms_provider,
            kms_key_id=data.kms_key_id,
        )
    except ModelEncryptionNotEnabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ModelEncryptionValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ModelEncryptionProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    status_data = await get_model_encryption_status(db, model_id)
    return ModelEncryptionStatusResponse(**status_data)
