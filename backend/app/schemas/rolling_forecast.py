import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ForecastConfigCreate(BaseModel):
    model_id: uuid.UUID
    forecast_horizon_months: int = 12
    auto_archive: bool = True
    actuals_version_id: Optional[uuid.UUID] = None
    forecast_version_id: Optional[uuid.UUID] = None


class ForecastConfigUpdate(BaseModel):
    forecast_horizon_months: Optional[int] = None
    auto_archive: Optional[bool] = None
    actuals_version_id: Optional[uuid.UUID] = None
    forecast_version_id: Optional[uuid.UUID] = None


class ForecastConfigResponse(BaseModel):
    id: uuid.UUID
    model_id: uuid.UUID
    forecast_horizon_months: int
    auto_archive: bool
    archive_actuals_version_id: Optional[uuid.UUID]
    forecast_version_id: Optional[uuid.UUID]
    last_rolled_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RollResult(BaseModel):
    periods_rolled: int
    cells_archived: int
    new_switchover_period: Optional[str]


class ForecastStatus(BaseModel):
    horizon_months: int
    periods_elapsed: int
    periods_remaining: int
    last_rolled_at: Optional[datetime]
    next_roll_suggestion: Optional[str]
