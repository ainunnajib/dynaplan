"""
API routes for time dimension (F009).

Routes:
    POST /models/{model_id}/time-dimensions   — create a time dimension
    GET  /dimensions/{dimension_id}/time-periods — list time periods
"""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.engine.time_calendar import FiscalCalendar
from app.models.user import User
from app.schemas.dimension import DimensionResponse
from app.schemas.time_dimension import TimeDimensionCreate, TimePeriodResponse
from app.services.dimension import get_dimension_by_id
from app.services.time_dimension import create_time_dimension, get_time_periods
from app.services.workspace_quota import WorkspaceQuotaExceededError

router = APIRouter(tags=["time-dimensions"])


@router.post(
    "/models/{model_id}/time-dimensions",
    response_model=DimensionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_time_dimension_endpoint(
    model_id: uuid.UUID,
    data: TimeDimensionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a time dimension with auto-generated calendar periods."""
    fiscal_calendar = FiscalCalendar(
        fiscal_year_start_month=data.fiscal_calendar.fiscal_year_start_month,
        week_start_day=data.fiscal_calendar.week_start_day,
        week_pattern=data.fiscal_calendar.week_pattern,
        retail_pattern=data.fiscal_calendar.retail_pattern,
    )
    try:
        dimension = await create_time_dimension(
            db=db,
            model_id=model_id,
            name=data.name,
            start_year=data.start_year,
            end_year=data.end_year,
            granularity=data.granularity,
            fiscal_calendar=fiscal_calendar,
        )
        return dimension
    except WorkspaceQuotaExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get(
    "/dimensions/{dimension_id}/time-periods",
    response_model=List[TimePeriodResponse],
)
async def list_time_periods_endpoint(
    dimension_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return time periods (with date ranges) for a time dimension."""
    dimension = await get_dimension_by_id(db, dimension_id)
    if dimension is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dimension not found",
        )
    periods = await get_time_periods(db, dimension_id)
    return [TimePeriodResponse(**p) for p in periods]
