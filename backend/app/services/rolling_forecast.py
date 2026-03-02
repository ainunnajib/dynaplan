"""
Service layer for rolling forecasts (F026).

Handles creating/updating forecast configurations and advancing forecast
periods by copying forecast cell values into an actuals version and
advancing the switchover_period on the forecast version.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cell import CellValue
from app.models.forecast_config import ForecastConfig
from app.models.version import Version
from app.schemas.rolling_forecast import ForecastStatus, RollResult
from app.services.cell_versioning import migrate_legacy_cell_versions


# ---------------------------------------------------------------------------
# Period helpers
# ---------------------------------------------------------------------------

def _parse_period(period_str: str) -> Optional[tuple]:
    """Parse a period string of the form YYYY-MM into (year, month) ints.

    Returns None if the string is not parseable.
    """
    if not period_str:
        return None
    parts = period_str.strip().split("-")
    if len(parts) != 2:
        return None
    try:
        year = int(parts[0])
        month = int(parts[1])
        if not (1 <= month <= 12):
            return None
        return (year, month)
    except ValueError:
        return None


def _advance_period(period_str: str, months: int) -> str:
    """Advance a YYYY-MM period string by `months` months."""
    parsed = _parse_period(period_str)
    if parsed is None:
        return period_str
    year, month = parsed
    total_months = year * 12 + (month - 1) + months
    new_year = total_months // 12
    new_month = (total_months % 12) + 1
    return f"{new_year:04d}-{new_month:02d}"


def _periods_between(from_period: str, to_period: str) -> int:
    """Return the number of months from from_period to to_period (can be negative)."""
    a = _parse_period(from_period)
    b = _parse_period(to_period)
    if a is None or b is None:
        return 0
    return (b[0] * 12 + b[1]) - (a[0] * 12 + a[1])


def _current_period() -> str:
    """Return the current calendar month as YYYY-MM."""
    now = datetime.now(tz=timezone.utc)
    return f"{now.year:04d}-{now.month:02d}"


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def create_forecast_config(
    db: AsyncSession,
    model_id: uuid.UUID,
    horizon_months: int = 12,
    auto_archive: bool = True,
    actuals_version_id: Optional[uuid.UUID] = None,
    forecast_version_id: Optional[uuid.UUID] = None,
) -> ForecastConfig:
    """Create a new forecast configuration for a model."""
    config = ForecastConfig(
        model_id=model_id,
        forecast_horizon_months=horizon_months,
        auto_archive=auto_archive,
        archive_actuals_version_id=actuals_version_id,
        forecast_version_id=forecast_version_id,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


async def get_forecast_config(
    db: AsyncSession,
    model_id: uuid.UUID,
) -> Optional[ForecastConfig]:
    """Retrieve the forecast configuration for a model."""
    result = await db.execute(
        select(ForecastConfig).where(ForecastConfig.model_id == model_id)
    )
    return result.scalar_one_or_none()


async def update_forecast_config(
    db: AsyncSession,
    model_id: uuid.UUID,
    **updates: Any,
) -> Optional[ForecastConfig]:
    """Update fields on the forecast config for a model.

    Accepted keyword arguments: forecast_horizon_months, auto_archive,
    actuals_version_id, forecast_version_id.
    """
    config = await get_forecast_config(db, model_id)
    if config is None:
        return None

    if "forecast_horizon_months" in updates and updates["forecast_horizon_months"] is not None:
        config.forecast_horizon_months = updates["forecast_horizon_months"]
    if "auto_archive" in updates and updates["auto_archive"] is not None:
        config.auto_archive = updates["auto_archive"]
    if "actuals_version_id" in updates:
        config.archive_actuals_version_id = updates["actuals_version_id"]
    if "forecast_version_id" in updates:
        config.forecast_version_id = updates["forecast_version_id"]

    await db.commit()
    await db.refresh(config)
    return config


# ---------------------------------------------------------------------------
# Rolling logic
# ---------------------------------------------------------------------------

async def roll_forecast(
    db: AsyncSession,
    model_id: uuid.UUID,
    periods_to_roll: int = 1,
) -> RollResult:
    """Advance the forecast by rolling forward `periods_to_roll` periods.

    Steps:
    1. Load config and verify it exists.
    2. Get the forecast version and its current switchover_period.
    3. If auto_archive is True and an actuals version is configured, copy
       cell values from forecast version into actuals version for each
       period being rolled.
    4. Advance the switchover_period on the forecast version.
    5. Update last_rolled_at on the config.
    6. Return a RollResult summary.
    """
    config = await get_forecast_config(db, model_id)
    if config is None:
        raise ValueError("No forecast config found for this model")

    if config.forecast_version_id is None:
        raise ValueError("No forecast version configured")

    # Load the forecast version
    forecast_version_result = await db.execute(
        select(Version).where(Version.id == config.forecast_version_id)
    )
    forecast_version = forecast_version_result.scalar_one_or_none()
    if forecast_version is None:
        raise ValueError("Forecast version not found")

    current_switchover = forecast_version.switchover_period
    cells_archived = 0

    if config.auto_archive and config.archive_actuals_version_id is not None:
        await migrate_legacy_cell_versions(db, model_id=model_id)

        # Load the actuals version
        actuals_version_result = await db.execute(
            select(Version).where(Version.id == config.archive_actuals_version_id)
        )
        actuals_version = actuals_version_result.scalar_one_or_none()

        if actuals_version is not None:
            for period_offset in range(periods_to_roll):
                period_to_archive: Optional[str] = None
                if current_switchover is not None:
                    period_to_archive = _advance_period(current_switchover, period_offset)

                # Find all cell values that belong to the forecast version
                # Cell dimension_key contains the version UUID as one segment
                forecast_version_str = str(config.forecast_version_id)
                actuals_version_str = str(config.archive_actuals_version_id)

                cells_result = await db.execute(
                    select(CellValue).where(
                        CellValue.version_id == config.forecast_version_id
                    )
                )
                forecast_cells = list(cells_result.scalars().all())

                # Filter by period if we have period info in the dimension key
                if period_to_archive is not None:
                    forecast_cells = [
                        c for c in forecast_cells
                        if period_to_archive in c.dimension_key
                    ]

                for fc in forecast_cells:
                    # Replace forecast version id with actuals version id in key
                    new_key = fc.dimension_key.replace(
                        forecast_version_str, actuals_version_str
                    )
                    if actuals_version_str not in new_key:
                        if new_key:
                            new_key = f"{new_key}|{actuals_version_str}"
                        else:
                            new_key = actuals_version_str
                    new_key = "|".join(sorted(part for part in new_key.split("|") if part))

                    # Upsert: check if actuals cell already exists
                    existing_result = await db.execute(
                        select(CellValue).where(
                            CellValue.line_item_id == fc.line_item_id,
                            CellValue.dimension_key == new_key,
                        )
                    )
                    existing = existing_result.scalar_one_or_none()
                    if existing is not None:
                        existing.value_number = fc.value_number
                        existing.value_text = fc.value_text
                        existing.value_boolean = fc.value_boolean
                    else:
                        new_cell = CellValue(
                            line_item_id=fc.line_item_id,
                            version_id=config.archive_actuals_version_id,
                            dimension_key=new_key,
                            value_number=fc.value_number,
                            value_text=fc.value_text,
                            value_boolean=fc.value_boolean,
                        )
                        db.add(new_cell)
                    if existing is not None and existing.version_id is None:
                        existing.version_id = config.archive_actuals_version_id
                    cells_archived += 1

                await db.flush()

    # Advance switchover period
    new_switchover: Optional[str] = None
    if current_switchover is not None:
        new_switchover = _advance_period(current_switchover, periods_to_roll)
    else:
        # Default to current month advanced by periods_to_roll
        new_switchover = _advance_period(_current_period(), periods_to_roll)

    forecast_version.switchover_period = new_switchover

    # Update last_rolled_at
    config.last_rolled_at = datetime.now(tz=timezone.utc)

    await db.commit()
    await db.refresh(config)
    await db.refresh(forecast_version)

    return RollResult(
        periods_rolled=periods_to_roll,
        cells_archived=cells_archived,
        new_switchover_period=new_switchover,
    )


async def get_forecast_status(
    db: AsyncSession,
    model_id: uuid.UUID,
) -> Optional[ForecastStatus]:
    """Return the current forecast status for a model.

    Calculates:
    - horizon_months: configured horizon
    - periods_elapsed: months from switchover to now
    - periods_remaining: horizon - elapsed
    - last_rolled_at: when last rolled
    - next_roll_suggestion: next YYYY-MM period to roll to
    """
    config = await get_forecast_config(db, model_id)
    if config is None:
        return None

    horizon_months = config.forecast_horizon_months
    current_period = _current_period()

    periods_elapsed = 0
    next_roll_suggestion: Optional[str] = None

    if config.forecast_version_id is not None:
        version_result = await db.execute(
            select(Version).where(Version.id == config.forecast_version_id)
        )
        version = version_result.scalar_one_or_none()
        if version is not None and version.switchover_period is not None:
            # Elapsed = current month - switchover month
            elapsed = _periods_between(version.switchover_period, current_period)
            periods_elapsed = max(0, elapsed)
            next_roll_suggestion = _advance_period(version.switchover_period, 1)

    periods_remaining = max(0, horizon_months - periods_elapsed)

    return ForecastStatus(
        horizon_months=horizon_months,
        periods_elapsed=periods_elapsed,
        periods_remaining=periods_remaining,
        last_rolled_at=config.last_rolled_at,
        next_roll_suggestion=next_roll_suggestion,
    )


async def auto_roll_if_due(
    db: AsyncSession,
    model_id: uuid.UUID,
) -> Optional[RollResult]:
    """Check if a roll is due and auto-roll if needed.

    A roll is considered due if the current calendar month has passed the
    configured switchover_period on the forecast version. Returns None if
    no roll is needed or if config is missing.
    """
    config = await get_forecast_config(db, model_id)
    if config is None:
        return None

    if not config.auto_archive:
        return None

    if config.forecast_version_id is None:
        return None

    version_result = await db.execute(
        select(Version).where(Version.id == config.forecast_version_id)
    )
    version = version_result.scalar_one_or_none()
    if version is None or version.switchover_period is None:
        return None

    current_period = _current_period()
    elapsed = _periods_between(version.switchover_period, current_period)

    if elapsed <= 0:
        # No roll needed — switchover is still in the future
        return None

    # Roll by the number of elapsed periods (catch up)
    return await roll_forecast(db, model_id, periods_to_roll=elapsed)
