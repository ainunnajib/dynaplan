import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.version import (
    VersionCompareRequest,
    VersionCompareResponse,
    VersionCreate,
    VersionResponse,
    VersionUpdate,
)
from app.services.version import (
    compare_versions,
    create_version,
    delete_version,
    get_version_by_id,
    list_versions_for_model,
    set_default_version,
    update_version,
)

router = APIRouter(tags=["versions"])


# ── Helper ─────────────────────────────────────────────────────────────────────

async def _get_version_or_404(
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    version = await get_version_by_id(db, version_id)
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )
    return version


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post(
    "/models/{model_id}/versions",
    response_model=VersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_version_endpoint(
    model_id: uuid.UUID,
    data: VersionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await create_version(db, model_id=model_id, data=data)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A version with this name already exists in the model",
        )


@router.get(
    "/models/{model_id}/versions",
    response_model=List[VersionResponse],
)
async def list_versions_endpoint(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_versions_for_model(db, model_id=model_id)


@router.get(
    "/versions/{version_id}",
    response_model=VersionResponse,
)
async def get_version_endpoint(
    version=Depends(_get_version_or_404),
):
    return version


@router.patch(
    "/versions/{version_id}",
    response_model=VersionResponse,
)
async def update_version_endpoint(
    data: VersionUpdate,
    version=Depends(_get_version_or_404),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await update_version(db, version, data)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A version with this name already exists in the model",
        )


@router.delete(
    "/versions/{version_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_version_endpoint(
    version=Depends(_get_version_or_404),
    db: AsyncSession = Depends(get_db),
):
    await delete_version(db, version)


@router.post(
    "/versions/compare",
    response_model=VersionCompareResponse,
)
async def compare_versions_endpoint(
    data: VersionCompareRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await compare_versions(
        db,
        version_id_a=data.version_id_a,
        version_id_b=data.version_id_b,
        line_item_id=data.line_item_id,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both versions not found",
        )
    return result


@router.post(
    "/versions/{version_id}/set-default",
    response_model=VersionResponse,
)
async def set_default_version_endpoint(
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # First verify the version exists
    version = await get_version_by_id(db, version_id)
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )
    updated = await set_default_version(db, model_id=version.model_id, version_id=version_id)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )
    return updated
