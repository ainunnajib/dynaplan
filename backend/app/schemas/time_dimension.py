"""Pydantic schemas for time dimension API (F009)."""

from typing import Any, Optional

from pydantic import BaseModel, field_validator

from app.engine.time_calendar import TimePeriodType


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class FiscalCalendarConfig(BaseModel):
    """Fiscal calendar configuration embedded in the create request."""
    fiscal_year_start_month: int = 1
    week_start_day: int = 0

    @field_validator("fiscal_year_start_month")
    @classmethod
    def validate_fy_start(cls, v: int) -> int:
        if not 1 <= v <= 12:
            raise ValueError("fiscal_year_start_month must be between 1 and 12")
        return v

    @field_validator("week_start_day")
    @classmethod
    def validate_week_start(cls, v: int) -> int:
        if not 0 <= v <= 6:
            raise ValueError("week_start_day must be between 0 and 6")
        return v


class TimeDimensionCreate(BaseModel):
    """Payload for POST /models/{model_id}/time-dimensions."""
    name: str
    start_year: int
    end_year: int
    granularity: TimePeriodType = TimePeriodType.month
    fiscal_calendar: FiscalCalendarConfig = FiscalCalendarConfig()

    @field_validator("end_year")
    @classmethod
    def validate_year_range(cls, v: int, info: Any) -> int:
        start = info.data.get("start_year")
        if start is not None and v < start:
            raise ValueError("end_year must be >= start_year")
        return v


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class TimePeriodResponse(BaseModel):
    """A single time period item returned from GET /dimensions/{id}/time-periods."""
    id: str
    name: str
    code: str
    dimension_id: str
    parent_id: Optional[str]
    sort_order: int
    start_date: Optional[str]
    end_date: Optional[str]
    period_type: Optional[str]
