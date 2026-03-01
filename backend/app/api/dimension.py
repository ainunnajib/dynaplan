import uuid
from typing import List, Literal, Union

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.dimension import (
    DimensionCreate,
    DimensionItemCreate,
    DimensionItemNode,
    DimensionItemResponse,
    DimensionItemUpdate,
    DimensionResponse,
    DimensionUpdate,
)
from app.services.dimension import (
    DimensionValidationError,
    create_dimension,
    create_dimension_item,
    delete_dimension,
    delete_dimension_item,
    get_dimension_by_id,
    get_dimension_item_by_id,
    get_items_as_tree,
    list_dimensions_for_model,
    list_items_flat,
    update_dimension,
    update_dimension_item,
)
from app.services.workspace_quota import WorkspaceQuotaExceededError

router = APIRouter(tags=["dimensions"])


class LegacyDimensionCreate(DimensionCreate):
    """Backward-compatible payload for POST /dimensions."""
    model_id: uuid.UUID


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _get_dimension_or_404(
    dimension_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> object:
    dimension = await get_dimension_by_id(db, dimension_id)
    if dimension is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dimension not found",
        )
    return dimension


async def _get_item_or_404(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> object:
    item = await get_dimension_item_by_id(db, item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dimension item not found",
        )
    return item


# ── Dimension endpoints ────────────────────────────────────────────────────────

@router.post(
    "/models/{model_id}/dimensions",
    response_model=DimensionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dimension_endpoint(
    model_id: uuid.UUID,
    data: DimensionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await create_dimension(db, model_id=model_id, data=data)
    except WorkspaceQuotaExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except DimensionValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/dimensions",
    response_model=DimensionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dimension_legacy_endpoint(
    data: LegacyDimensionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Legacy endpoint: model_id in body instead of path."""
    create_data = DimensionCreate(
        name=data.name,
        dimension_type=data.dimension_type,
        max_items=data.max_items,
    )
    try:
        return await create_dimension(db, model_id=data.model_id, data=create_data)
    except WorkspaceQuotaExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except DimensionValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/models/{model_id}/dimensions",
    response_model=List[DimensionResponse],
)
async def list_dimensions_endpoint(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_dimensions_for_model(db, model_id=model_id)


@router.patch(
    "/dimensions/{dimension_id}",
    response_model=DimensionResponse,
)
async def update_dimension_endpoint(
    data: DimensionUpdate,
    dimension=Depends(_get_dimension_or_404),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await update_dimension(db, dimension, data)
    except DimensionValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.delete(
    "/dimensions/{dimension_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_dimension_endpoint(
    dimension=Depends(_get_dimension_or_404),
    db: AsyncSession = Depends(get_db),
):
    await delete_dimension(db, dimension)


# ── DimensionItem endpoints ────────────────────────────────────────────────────

@router.post(
    "/dimensions/{dimension_id}/items",
    response_model=DimensionItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_item_endpoint(
    dimension_id: uuid.UUID,
    data: DimensionItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify dimension exists
    dimension = await get_dimension_by_id(db, dimension_id)
    if dimension is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dimension not found",
        )
    # Verify parent exists in same dimension (if supplied)
    if data.parent_id is not None:
        parent = await get_dimension_item_by_id(db, data.parent_id)
        if parent is None or parent.dimension_id != dimension_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent item not found in this dimension",
            )
    try:
        return await create_dimension_item(db, dimension_id=dimension_id, data=data)
    except DimensionValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/dimensions/{dimension_id}/items",
    response_model=Union[List[DimensionItemResponse], List[DimensionItemNode]],
)
async def list_items_endpoint(
    dimension_id: uuid.UUID,
    format: Literal["flat", "tree"] = Query(default="flat"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dimension = await get_dimension_by_id(db, dimension_id)
    if dimension is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dimension not found",
        )
    if format == "tree":
        return await get_items_as_tree(db, dimension_id)
    return await list_items_flat(db, dimension_id)


@router.patch(
    "/dimensions/{dimension_id}/items/{item_id}",
    response_model=DimensionItemResponse,
)
async def update_item_endpoint(
    dimension_id: uuid.UUID,
    item_id: uuid.UUID,
    data: DimensionItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = await get_dimension_item_by_id(db, item_id)
    if item is None or item.dimension_id != dimension_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dimension item not found",
        )
    # Validate new parent if provided
    if "parent_id" in data.model_fields_set and data.parent_id is not None:
        if data.parent_id == item_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An item cannot be its own parent",
            )
        parent = await get_dimension_item_by_id(db, data.parent_id)
        if parent is None or parent.dimension_id != dimension_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent item not found in this dimension",
            )
    try:
        return await update_dimension_item(db, item, data)
    except DimensionValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.delete(
    "/dimensions/{dimension_id}/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_item_endpoint(
    dimension_id: uuid.UUID,
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = await get_dimension_item_by_id(db, item_id)
    if item is None or item.dimension_id != dimension_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dimension item not found",
        )
    await delete_dimension_item(db, item)
