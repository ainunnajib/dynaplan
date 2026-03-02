import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.saved_view import SavedView
from app.models.user import User
from app.schemas.saved_view import SavedViewCreate, SavedViewResponse, SavedViewUpdate
from app.services.module import get_module_by_id
from app.services.saved_view import (
    create_saved_view,
    delete_saved_view,
    get_saved_view_by_id,
    list_saved_views_for_module,
    set_saved_view_as_default,
    update_saved_view,
)

router = APIRouter(tags=["saved-views"])


async def _get_module_or_404(
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
    return module


async def _get_owned_saved_view_or_404(
    saved_view_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavedView:
    saved_view = await get_saved_view_by_id(db, saved_view_id)
    if saved_view is None or saved_view.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved view not found",
        )
    return saved_view


@router.post(
    "/modules/{module_id}/saved-views",
    response_model=SavedViewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_saved_view_endpoint(
    module_id: uuid.UUID,
    data: SavedViewCreate,
    _module=Depends(_get_module_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await create_saved_view(
            db,
            module_id=module_id,
            user_id=current_user.id,
            data=data,
        )
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Saved view name already exists for this module",
        ) from exc


@router.get(
    "/modules/{module_id}/saved-views",
    response_model=List[SavedViewResponse],
)
async def list_saved_views_endpoint(
    module_id: uuid.UUID,
    _module=Depends(_get_module_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_saved_views_for_module(
        db,
        module_id=module_id,
        user_id=current_user.id,
    )


@router.get(
    "/saved-views/{saved_view_id}",
    response_model=SavedViewResponse,
)
async def get_saved_view_endpoint(
    saved_view=Depends(_get_owned_saved_view_or_404),
):
    return saved_view


@router.patch(
    "/saved-views/{saved_view_id}",
    response_model=SavedViewResponse,
)
async def update_saved_view_endpoint(
    data: SavedViewUpdate,
    saved_view=Depends(_get_owned_saved_view_or_404),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await update_saved_view(db, saved_view=saved_view, data=data)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Saved view name already exists for this module",
        ) from exc


@router.put(
    "/saved-views/{saved_view_id}/default",
    response_model=SavedViewResponse,
)
async def set_saved_view_default_endpoint(
    saved_view=Depends(_get_owned_saved_view_or_404),
    db: AsyncSession = Depends(get_db),
):
    return await set_saved_view_as_default(db, saved_view=saved_view)


@router.delete(
    "/saved-views/{saved_view_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_saved_view_endpoint(
    saved_view=Depends(_get_owned_saved_view_or_404),
    db: AsyncSession = Depends(get_db),
):
    await delete_saved_view(db, saved_view=saved_view)
