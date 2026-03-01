import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.time_range import TimeGranularity


# ── TimeRange schemas ─────────────────────────────────────────────────────────

class TimeRangeCreate(BaseModel):
    name: str
    start_period: str
    end_period: str
    granularity: TimeGranularity = TimeGranularity.month
    is_model_default: bool = False


class TimeRangeUpdate(BaseModel):
    name: Optional[str] = None
    start_period: Optional[str] = None
    end_period: Optional[str] = None
    granularity: Optional[TimeGranularity] = None
    is_model_default: Optional[bool] = None


class TimeRangeResponse(BaseModel):
    id: uuid.UUID
    model_id: uuid.UUID
    name: str
    start_period: str
    end_period: str
    granularity: TimeGranularity
    is_model_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── ModuleTimeRange schemas ──────────────────────────────────────────────────

class ModuleTimeRangeAssign(BaseModel):
    time_range_id: uuid.UUID


class ModuleTimeRangeResponse(BaseModel):
    id: uuid.UUID
    module_id: uuid.UUID
    time_range_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}
