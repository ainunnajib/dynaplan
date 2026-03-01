import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.time_range import (
    ModuleTimeRangeAssign,
    ModuleTimeRangeResponse,
    TimeRangeCreate,
    TimeRangeResponse,
    TimeRangeUpdate,
)
from app.services.module import get_module_by_id
from app.services.time_range import (
    assign_time_range_to_module,
    create_time_range,
    delete_time_range,
    get_effective_time_range,
    get_time_range_by_id,
    list_time_ranges_for_model,
    unassign_time_range_from_module,
    update_time_range,
)

router = APIRouter(tags=["time-ranges"])


# ── TimeRange CRUD ────────────────────────────────────────────────────────────

@router.post(
    "/models/{model_id}/time-ranges",
    response_model=TimeRangeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_time_range_endpoint(
    model_id: uuid.UUID,
    data: TimeRangeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await create_time_range(db, model_id=model_id, data=data)


@router.get(
    "/models/{model_id}/time-ranges",
    response_model=List[TimeRangeResponse],
)
async def list_time_ranges_endpoint(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_time_ranges_for_model(db, model_id=model_id)


@router.get(
    "/time-ranges/{time_range_id}",
    response_model=TimeRangeResponse,
)
async def get_time_range_endpoint(
    time_range_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tr = await get_time_range_by_id(db, time_range_id)
    if tr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Time range not found",
        )
    return tr


@router.put(
    "/time-ranges/{time_range_id}",
    response_model=TimeRangeResponse,
)
async def update_time_range_endpoint(
    time_range_id: uuid.UUID,
    data: TimeRangeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tr = await get_time_range_by_id(db, time_range_id)
    if tr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Time range not found",
        )
    return await update_time_range(db, tr, data)


@router.delete(
    "/time-ranges/{time_range_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_time_range_endpoint(
    time_range_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tr = await get_time_range_by_id(db, time_range_id)
    if tr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Time range not found",
        )
    await delete_time_range(db, tr)


# ── Module time range assignment ──────────────────────────────────────────────

@router.post(
    "/modules/{module_id}/time-range",
    response_model=ModuleTimeRangeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assign_module_time_range_endpoint(
    module_id: uuid.UUID,
    data: ModuleTimeRangeAssign,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    module = await get_module_by_id(db, module_id)
    if module is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Module not found",
        )
    tr = await get_time_range_by_id(db, data.time_range_id)
    if tr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Time range not found",
        )
    return await assign_time_range_to_module(db, module_id, data.time_range_id)


@router.delete(
    "/modules/{module_id}/time-range",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unassign_module_time_range_endpoint(
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
    removed = await unassign_time_range_from_module(db, module_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No time range assigned to this module",
        )


@router.get(
    "/modules/{module_id}/effective-time-range",
    response_model=Optional[TimeRangeResponse],
)
async def get_effective_time_range_endpoint(
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
    return await get_effective_time_range(db, module_id, module.model_id)
