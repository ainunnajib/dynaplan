import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.rolling_forecast import (
    ForecastConfigCreate,
    ForecastConfigResponse,
    ForecastConfigUpdate,
    ForecastStatus,
    RollResult,
)
from app.services.rolling_forecast import (
    create_forecast_config,
    get_forecast_config,
    get_forecast_status,
    roll_forecast,
    update_forecast_config,
)

router = APIRouter(tags=["rolling-forecast"])


# ---------------------------------------------------------------------------
# Forecast config endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/models/{model_id}/forecast-config",
    response_model=ForecastConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_forecast_config_endpoint(
    model_id: uuid.UUID,
    data: ForecastConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new forecast configuration for a model."""
    try:
        config = await create_forecast_config(
            db,
            model_id=model_id,
            horizon_months=data.forecast_horizon_months,
            auto_archive=data.auto_archive,
            actuals_version_id=data.actuals_version_id,
            forecast_version_id=data.forecast_version_id,
        )
        return config
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A forecast configuration already exists for this model",
        )


@router.get(
    "/models/{model_id}/forecast-config",
    response_model=ForecastConfigResponse,
)
async def get_forecast_config_endpoint(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve the forecast configuration for a model."""
    config = await get_forecast_config(db, model_id)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Forecast configuration not found for this model",
        )
    return config


@router.patch(
    "/models/{model_id}/forecast-config",
    response_model=ForecastConfigResponse,
)
async def update_forecast_config_endpoint(
    model_id: uuid.UUID,
    data: ForecastConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the forecast configuration for a model."""
    config = await update_forecast_config(
        db,
        model_id=model_id,
        forecast_horizon_months=data.forecast_horizon_months,
        auto_archive=data.auto_archive,
        actuals_version_id=data.actuals_version_id,
        forecast_version_id=data.forecast_version_id,
    )
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Forecast configuration not found for this model",
        )
    return config


# ---------------------------------------------------------------------------
# Roll and status endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/models/{model_id}/forecast/roll",
    response_model=RollResult,
)
async def roll_forecast_endpoint(
    model_id: uuid.UUID,
    periods_to_roll: int = Query(default=1, ge=1, description="Number of periods to roll forward"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger rolling the forecast forward by the specified number of periods."""
    # Verify the config exists first
    config = await get_forecast_config(db, model_id)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Forecast configuration not found for this model",
        )

    try:
        result = await roll_forecast(db, model_id, periods_to_roll=periods_to_roll)
        return result
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.get(
    "/models/{model_id}/forecast/status",
    response_model=ForecastStatus,
)
async def get_forecast_status_endpoint(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current forecast status for a model."""
    status_result = await get_forecast_status(db, model_id)
    if status_result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Forecast configuration not found for this model",
        )
    return status_result
