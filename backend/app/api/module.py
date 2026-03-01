import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.module import (
    LineItemCreate,
    LineItemResponse,
    LineItemUpdate,
    ModuleCreate,
    ModuleResponse,
    ModuleUpdate,
    ModuleWithLineItemsResponse,
)
from app.services.module import (
    create_line_item,
    create_module,
    delete_line_item,
    delete_module,
    get_line_item_by_id,
    get_module_by_id,
    list_line_items_for_dimension,
    list_line_items_for_module,
    list_modules_for_model,
    update_line_item,
    update_module,
)

router = APIRouter(tags=["modules"])


class LegacyModuleCreate(ModuleCreate):
    """Backward-compatible payload for POST /modules."""
    model_id: uuid.UUID


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _get_module_or_404(
    module_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> object:
    module = await get_module_by_id(db, module_id)
    if module is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Module not found",
        )
    return module


async def _get_line_item_or_404(
    line_item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> object:
    line_item = await get_line_item_by_id(db, line_item_id)
    if line_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Line item not found",
        )
    return line_item


# ── Module endpoints ───────────────────────────────────────────────────────────

@router.post(
    "/models/{model_id}/modules",
    response_model=ModuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_module_endpoint(
    model_id: uuid.UUID,
    data: ModuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await create_module(db, model_id=model_id, data=data)


@router.post(
    "/modules",
    response_model=ModuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_module_legacy_endpoint(
    data: LegacyModuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Legacy endpoint: model_id in body instead of path."""
    create_data = ModuleCreate(
        name=data.name,
        description=data.description,
    )
    return await create_module(db, model_id=data.model_id, data=create_data)


@router.get(
    "/models/{model_id}/modules",
    response_model=List[ModuleResponse],
)
async def list_modules_endpoint(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_modules_for_model(db, model_id=model_id)


@router.get(
    "/modules/{module_id}",
    response_model=ModuleWithLineItemsResponse,
)
async def get_module_endpoint(
    module=Depends(_get_module_or_404),
):
    return module


@router.patch(
    "/modules/{module_id}",
    response_model=ModuleResponse,
)
async def update_module_endpoint(
    data: ModuleUpdate,
    module=Depends(_get_module_or_404),
    db: AsyncSession = Depends(get_db),
):
    return await update_module(db, module, data)


@router.delete(
    "/modules/{module_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_module_endpoint(
    module=Depends(_get_module_or_404),
    db: AsyncSession = Depends(get_db),
):
    await delete_module(db, module)


# ── LineItem endpoints ─────────────────────────────────────────────────────────

@router.post(
    "/modules/{module_id}/line-items",
    response_model=LineItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_line_item_endpoint(
    module_id: uuid.UUID,
    data: LineItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    module = await get_module_by_id(db, module_id)
    if module is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Module not found",
        )
    return await create_line_item(db, module_id=module_id, data=data)


@router.get(
    "/modules/{module_id}/line-items",
    response_model=List[LineItemResponse],
)
async def list_line_items_endpoint(
    module_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    module = await get_module_by_id(db, module_id)
    if module is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Module not found",
        )
    return await list_line_items_for_module(db, module_id=module_id)


@router.get(
    "/dimensions/{dimension_id}/line-items",
    response_model=List[LineItemResponse],
)
async def list_line_items_for_dimension_endpoint(
    dimension_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_line_items_for_dimension(db, dimension_id=dimension_id)


@router.patch(
    "/line-items/{line_item_id}",
    response_model=LineItemResponse,
)
async def update_line_item_endpoint(
    data: LineItemUpdate,
    line_item=Depends(_get_line_item_or_404),
    db: AsyncSession = Depends(get_db),
):
    return await update_line_item(db, line_item, data)


@router.delete(
    "/line-items/{line_item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_line_item_endpoint(
    line_item=Depends(_get_line_item_or_404),
    db: AsyncSession = Depends(get_db),
):
    await delete_line_item(db, line_item)
