"""
Calculation Cache API — F031

REST endpoints for cache statistics, invalidation, clearing, and
background recalculation of stale entries.
"""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.calc_cache import (
    CacheEntryResponse,
    CacheStats,
    InvalidateRequest,
    RecalcResult,
)
from app.services.calc_cache import (
    clear_cache,
    get_cache_stats,
    get_stale_entries,
    invalidate_cache,
    recalculate_stale,
)
from app.services.planning_model import get_model_by_id

router = APIRouter(prefix="/models", tags=["cache"])


async def _get_model_or_404(db: AsyncSession, model_id: uuid.UUID):
    model = await get_model_by_id(db, model_id)
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )
    return model


@router.get(
    "/{model_id}/cache/stats",
    response_model=CacheStats,
)
async def get_model_cache_stats(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return cache statistics for the given model."""
    await _get_model_or_404(db, model_id)
    stats = await get_cache_stats(db, model_id)
    return CacheStats(**stats)


@router.post(
    "/{model_id}/cache/invalidate",
    response_model=dict,
)
async def invalidate_model_cache(
    model_id: uuid.UUID,
    request: InvalidateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Invalidate cache entries.

    If cascade=True and a dependency graph is available, downstream entries
    are also invalidated. In this implementation, cascade without an
    injected dependency graph invalidates all entries for the line item.
    """
    await _get_model_or_404(db, model_id)
    count = await invalidate_cache(
        db,
        line_item_id=request.line_item_id,
        dimension_key=request.dimension_key,
    )
    return {"invalidated": count}


@router.delete(
    "/{model_id}/cache",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def clear_model_cache(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete all cache entries for the given model."""
    await _get_model_or_404(db, model_id)
    await clear_cache(db, model_id)


@router.post(
    "/{model_id}/cache/recalculate",
    response_model=RecalcResult,
)
async def trigger_recalculation(
    model_id: uuid.UUID,
    batch_size: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger recalculation of stale (invalid) cache entries."""
    await _get_model_or_404(db, model_id)
    result = await recalculate_stale(db, model_id, batch_size=batch_size)
    return RecalcResult(**result)


@router.get(
    "/{model_id}/cache/stale",
    response_model=List[CacheEntryResponse],
)
async def list_stale_entries(
    model_id: uuid.UUID,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List stale (invalid) cache entries that need recalculation."""
    await _get_model_or_404(db, model_id)
    entries = await get_stale_entries(db, model_id, limit=limit)
    return entries
