import re
import uuid
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.time_range import ModuleTimeRange, TimeGranularity, TimeRange
from app.schemas.time_range import TimeRangeCreate, TimeRangeUpdate


# ── Period validation ─────────────────────────────────────────────────────────

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")  # 2024-01
_QUARTER_RE = re.compile(r"^\d{4}-Q[1-4]$", flags=re.IGNORECASE)  # 2024-Q1
_WEEK_RE = re.compile(r"^\d{4}-W(0[1-9]|[1-4][0-9]|5[0-3])$", flags=re.IGNORECASE)
_HALF_YEAR_RE = re.compile(r"^(?:FY)?\d{4}-H[12]$", flags=re.IGNORECASE)
_YEAR_RE = re.compile(r"^\d{4}$")  # 2024

_PERIOD_PATTERNS = {
    TimeGranularity.week: _WEEK_RE,
    TimeGranularity.month: _MONTH_RE,
    TimeGranularity.quarter: _QUARTER_RE,
    TimeGranularity.half_year: _HALF_YEAR_RE,
    TimeGranularity.year: _YEAR_RE,
}


def _period_sort_key(period: str, granularity: TimeGranularity) -> str:
    """Return a comparable string key for a period."""
    if granularity == TimeGranularity.month:
        # Already in YYYY-MM format, lexicographic comparison works
        return period
    if granularity == TimeGranularity.quarter:
        # 2024-Q1 -> 2024-1, etc.
        return period.upper().replace("-Q", "-")
    if granularity == TimeGranularity.half_year:
        normalized = period.upper()
        if normalized.startswith("FY"):
            normalized = normalized[2:]
        return normalized.replace("-H", "-")
    return period.upper()


def validate_period_format(period: str, granularity: TimeGranularity) -> None:
    """Raise HTTPException if period doesn't match granularity format."""
    pattern = _PERIOD_PATTERNS[granularity]
    if not pattern.match(period):
        expected = {
            TimeGranularity.week: "YYYY-WNN (e.g. 2024-W05)",
            TimeGranularity.month: "YYYY-MM (e.g. 2024-01)",
            TimeGranularity.quarter: "YYYY-QN (e.g. 2024-Q1)",
            TimeGranularity.half_year: "YYYY-HN or FYYYYY-HN (e.g. 2024-H1, FY2024-H2)",
            TimeGranularity.year: "YYYY (e.g. 2024)",
        }
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid period format '{period}'. Expected {expected[granularity]}",
        )


def validate_period_order(
    start_period: str, end_period: str, granularity: TimeGranularity
) -> None:
    """Raise HTTPException if start > end."""
    start_key = _period_sort_key(start_period, granularity)
    end_key = _period_sort_key(end_period, granularity)
    if start_key > end_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"start_period '{start_period}' must be <= end_period '{end_period}'",
        )


def validate_calendar_config(
    fiscal_year_start_month: int,
    week_start_day: int,
) -> None:
    if fiscal_year_start_month < 1 or fiscal_year_start_month > 12:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="fiscal_year_start_month must be between 1 and 12",
        )
    if week_start_day < 0 or week_start_day > 6:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="week_start_day must be between 0 and 6",
        )


# ── TimeRange CRUD ────────────────────────────────────────────────────────────

async def create_time_range(
    db: AsyncSession, model_id: uuid.UUID, data: TimeRangeCreate
) -> TimeRange:
    validate_period_format(data.start_period, data.granularity)
    validate_period_format(data.end_period, data.granularity)
    validate_period_order(data.start_period, data.end_period, data.granularity)
    validate_calendar_config(data.fiscal_year_start_month, data.week_start_day)

    # If marking as default, unset any existing default for this model
    if data.is_model_default:
        await _unset_model_default(db, model_id)

    time_range = TimeRange(
        model_id=model_id,
        name=data.name,
        start_period=data.start_period,
        end_period=data.end_period,
        granularity=data.granularity,
        fiscal_year_start_month=data.fiscal_year_start_month,
        week_start_day=data.week_start_day,
        week_pattern=data.week_pattern,
        retail_pattern=data.retail_pattern,
        calendar_periods=data.calendar_periods,
        is_model_default=data.is_model_default,
    )
    db.add(time_range)
    await db.commit()
    await db.refresh(time_range)
    return time_range


async def get_time_range_by_id(
    db: AsyncSession, time_range_id: uuid.UUID
) -> Optional[TimeRange]:
    result = await db.execute(
        select(TimeRange).where(TimeRange.id == time_range_id)
    )
    return result.scalar_one_or_none()


async def list_time_ranges_for_model(
    db: AsyncSession, model_id: uuid.UUID
) -> List[TimeRange]:
    result = await db.execute(
        select(TimeRange).where(TimeRange.model_id == model_id)
    )
    return list(result.scalars().all())


async def update_time_range(
    db: AsyncSession, time_range: TimeRange, data: TimeRangeUpdate
) -> TimeRange:
    # Determine effective values for validation
    granularity = data.granularity if data.granularity is not None else time_range.granularity
    start_period = data.start_period if data.start_period is not None else time_range.start_period
    end_period = data.end_period if data.end_period is not None else time_range.end_period
    fiscal_year_start_month = (
        data.fiscal_year_start_month
        if data.fiscal_year_start_month is not None
        else time_range.fiscal_year_start_month
    )
    week_start_day = (
        data.week_start_day
        if data.week_start_day is not None
        else time_range.week_start_day
    )

    # Validate if any period-related field changed
    if data.start_period is not None or data.end_period is not None or data.granularity is not None:
        validate_period_format(start_period, granularity)
        validate_period_format(end_period, granularity)
        validate_period_order(start_period, end_period, granularity)
    if data.fiscal_year_start_month is not None or data.week_start_day is not None:
        validate_calendar_config(fiscal_year_start_month, week_start_day)

    if data.name is not None:
        time_range.name = data.name
    if data.start_period is not None:
        time_range.start_period = data.start_period
    if data.end_period is not None:
        time_range.end_period = data.end_period
    if data.granularity is not None:
        time_range.granularity = data.granularity
    if data.fiscal_year_start_month is not None:
        time_range.fiscal_year_start_month = data.fiscal_year_start_month
    if data.week_start_day is not None:
        time_range.week_start_day = data.week_start_day
    if data.week_pattern is not None:
        time_range.week_pattern = data.week_pattern
    if data.retail_pattern is not None:
        time_range.retail_pattern = data.retail_pattern
    if data.calendar_periods is not None:
        time_range.calendar_periods = data.calendar_periods
    if data.is_model_default is not None:
        if data.is_model_default and not time_range.is_model_default:
            await _unset_model_default(db, time_range.model_id)
        time_range.is_model_default = data.is_model_default

    await db.commit()
    await db.refresh(time_range)
    return time_range


async def delete_time_range(db: AsyncSession, time_range: TimeRange) -> None:
    await db.delete(time_range)
    await db.commit()


# ── Module time range assignment ──────────────────────────────────────────────

async def assign_time_range_to_module(
    db: AsyncSession, module_id: uuid.UUID, time_range_id: uuid.UUID
) -> ModuleTimeRange:
    # Remove existing assignment if any
    result = await db.execute(
        select(ModuleTimeRange).where(ModuleTimeRange.module_id == module_id)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        await db.delete(existing)
        await db.flush()

    assignment = ModuleTimeRange(
        module_id=module_id,
        time_range_id=time_range_id,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    return assignment


async def unassign_time_range_from_module(
    db: AsyncSession, module_id: uuid.UUID
) -> bool:
    """Remove the module-level time range assignment. Returns True if removed."""
    result = await db.execute(
        select(ModuleTimeRange).where(ModuleTimeRange.module_id == module_id)
    )
    existing = result.scalar_one_or_none()
    if existing is None:
        return False
    await db.delete(existing)
    await db.commit()
    return True


async def get_effective_time_range(
    db: AsyncSession, module_id: uuid.UUID, model_id: uuid.UUID
) -> Optional[TimeRange]:
    """Get the effective time range for a module.

    Module-level assignment overrides the model default.
    """
    # Check module-level assignment first
    result = await db.execute(
        select(ModuleTimeRange).where(ModuleTimeRange.module_id == module_id)
    )
    assignment = result.scalar_one_or_none()
    if assignment is not None:
        return await get_time_range_by_id(db, assignment.time_range_id)

    # Fall back to model default
    result = await db.execute(
        select(TimeRange).where(
            TimeRange.model_id == model_id,
            TimeRange.is_model_default == True,  # noqa: E712
        )
    )
    return result.scalar_one_or_none()


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _unset_model_default(db: AsyncSession, model_id: uuid.UUID) -> None:
    """Unset is_model_default for all time ranges in the model."""
    result = await db.execute(
        select(TimeRange).where(
            TimeRange.model_id == model_id,
            TimeRange.is_model_default == True,  # noqa: E712
        )
    )
    for tr in result.scalars().all():
        tr.is_model_default = False
