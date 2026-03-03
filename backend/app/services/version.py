import uuid
from typing import Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cell import CellValue
from app.models.version import Version
from app.schemas.version import (
    CellVariance,
    VersionCompareResponse,
    VersionCreate,
    VersionUpdate,
)
from app.services.cell_versioning import (
    migrate_legacy_cell_versions,
    remove_versions_from_dimension_key,
)


def _parse_period_from_dimension_key(dimension_key: str) -> Optional[str]:
    """Extract the first YYYY-MM segment found in a dimension key."""
    if not dimension_key:
        return None
    for part in dimension_key.split("|"):
        if len(part) != 7:
            continue
        if part[4] != "-":
            continue
        year = part[:4]
        month = part[5:]
        if not year.isdigit() or not month.isdigit():
            continue
        month_int = int(month)
        if 1 <= month_int <= 12:
            return part
    return None


def _period_is_before(period_a: str, period_b: str) -> bool:
    return period_a < period_b


async def get_cells_with_switchover(
    db: AsyncSession,
    line_item_id: uuid.UUID,
    actuals_version_id: uuid.UUID,
    forecast_version_id: uuid.UUID,
    switchover_period: str,
) -> List[CellValue]:
    """Resolve effective cells using actuals before and forecast from switchover."""
    await migrate_legacy_cell_versions(db, line_item_ids=[line_item_id])

    result = await db.execute(
        select(CellValue).where(
            CellValue.line_item_id == line_item_id,
            CellValue.version_id.in_([actuals_version_id, forecast_version_id]),
        )
    )
    cells = list(result.scalars().all())

    effective: Dict[str, CellValue] = {}
    for cell in cells:
        base_key = remove_versions_from_dimension_key(
            dimension_key=cell.dimension_key,
            version_ids=[actuals_version_id, forecast_version_id],
        )
        period = _parse_period_from_dimension_key(cell.dimension_key)

        use_actuals = (
            cell.version_id == actuals_version_id
            and (
                period is None
                or _period_is_before(period, switchover_period)
            )
        )
        use_forecast = (
            cell.version_id == forecast_version_id
            and (
                period is None
                or not _period_is_before(period, switchover_period)
            )
        )
        if not use_actuals and not use_forecast:
            continue

        existing = effective.get(base_key)
        if existing is None:
            effective[base_key] = cell
            continue

        # Forecast wins at and after switchover for the same base key.
        if (
            existing.version_id == actuals_version_id
            and cell.version_id == forecast_version_id
            and period is not None
            and not _period_is_before(period, switchover_period)
        ):
            effective[base_key] = cell

    return list(effective.values())


# ── CRUD ───────────────────────────────────────────────────────────────────────

async def create_version(
    db: AsyncSession, model_id: uuid.UUID, data: VersionCreate
) -> Version:
    # If this version is being set as default, unset any existing default first
    if data.is_default:
        await db.execute(
            update(Version)
            .where(Version.model_id == model_id, Version.is_default.is_(True))
            .values(is_default=False)
        )

    version = Version(
        name=data.name,
        model_id=model_id,
        version_type=data.version_type,
        is_default=data.is_default,
        switchover_period=data.switchover_period,
    )
    db.add(version)
    await db.commit()
    await db.refresh(version)
    return version


async def get_version_by_id(
    db: AsyncSession, version_id: uuid.UUID
) -> Optional[Version]:
    result = await db.execute(
        select(Version).where(Version.id == version_id)
    )
    return result.scalar_one_or_none()


async def list_versions_for_model(
    db: AsyncSession, model_id: uuid.UUID
) -> List[Version]:
    result = await db.execute(
        select(Version)
        .where(Version.model_id == model_id)
        .order_by(Version.created_at)
    )
    return list(result.scalars().all())


async def update_version(
    db: AsyncSession, version: Version, data: VersionUpdate
) -> Version:
    if data.name is not None:
        version.name = data.name
    if data.version_type is not None:
        version.version_type = data.version_type
    if data.switchover_period is not None:
        version.switchover_period = data.switchover_period
    if "switchover_period" in data.model_fields_set and data.switchover_period is None:
        version.switchover_period = None
    if data.is_default is not None:
        version.is_default = data.is_default
    await db.commit()
    await db.refresh(version)
    return version


async def delete_version(db: AsyncSession, version: Version) -> None:
    await db.delete(version)
    await db.commit()


# ── Business logic ─────────────────────────────────────────────────────────────

async def set_default_version(
    db: AsyncSession, model_id: uuid.UUID, version_id: uuid.UUID
) -> Optional[Version]:
    """Unset the current default for a model and set the new one.

    Returns the updated Version, or None if version_id is not found.
    """
    version = await get_version_by_id(db, version_id)
    if version is None or version.model_id != model_id:
        return None

    # Clear previous default(s) for this model
    await db.execute(
        update(Version)
        .where(Version.model_id == model_id, Version.is_default.is_(True))
        .values(is_default=False)
    )

    # Set the new default
    version.is_default = True
    await db.commit()
    await db.refresh(version)
    return version


async def compare_versions(
    db: AsyncSession,
    version_id_a: uuid.UUID,
    version_id_b: uuid.UUID,
    line_item_id: uuid.UUID,
) -> Optional[VersionCompareResponse]:
    """Compare two versions for a given line item.

    Cells are matched by dimension_key. The version UUID is expected to appear
    as one of the pipe-separated segments in dimension_key. Returns absolute and
    percentage variance for each matched key.
    """
    version_a = await get_version_by_id(db, version_id_a)
    version_b = await get_version_by_id(db, version_id_b)
    if version_a is None or version_b is None:
        return None

    await migrate_legacy_cell_versions(db, line_item_ids=[line_item_id])

    result_a = await db.execute(
        select(CellValue).where(
            CellValue.line_item_id == line_item_id,
            CellValue.version_id == version_id_a,
        )
    )
    cells_a = list(result_a.scalars().all())

    result_b = await db.execute(
        select(CellValue).where(
            CellValue.line_item_id == line_item_id,
            CellValue.version_id == version_id_b,
        )
    )
    cells_b = list(result_b.scalars().all())

    # Cells with no explicit version context are treated as shared.
    result_shared = await db.execute(
        select(CellValue).where(
            CellValue.line_item_id == line_item_id,
            CellValue.version_id.is_(None),
        )
    )
    shared_cells = list(result_shared.scalars().all())

    # Build a union of all dimension keys, normalizing so we can match
    # A cell keyed with version_a's id needs to be compared against the
    # equivalent key with version_b's id. We strip out the version segment
    # and use the rest as a base key.
    # Build maps: base_key -> cell
    base_map_a: Dict[str, CellValue] = {}
    for cell in cells_a:
        bk = remove_versions_from_dimension_key(
            dimension_key=cell.dimension_key,
            version_ids=[version_id_a],
        )
        base_map_a[bk] = cell

    base_map_b: Dict[str, CellValue] = {}
    for cell in cells_b:
        bk = remove_versions_from_dimension_key(
            dimension_key=cell.dimension_key,
            version_ids=[version_id_b],
        )
        base_map_b[bk] = cell

    for cell in shared_cells:
        base_key = cell.dimension_key
        if base_key not in base_map_a:
            base_map_a[base_key] = cell
        if base_key not in base_map_b:
            base_map_b[base_key] = cell

    all_base_keys = set(base_map_a.keys()) | set(base_map_b.keys())

    variances: List[CellVariance] = []
    for bk in sorted(all_base_keys):
        cell_a = base_map_a.get(bk)
        cell_b = base_map_b.get(bk)

        val_a: Optional[float] = cell_a.value_number if cell_a else None
        val_b: Optional[float] = cell_b.value_number if cell_b else None

        if val_a is not None and val_b is not None:
            abs_var: Optional[float] = val_b - val_a
            if val_a != 0:
                pct_var: Optional[float] = (abs_var / abs(val_a)) * 100.0
            else:
                pct_var = None
        else:
            abs_var = None
            pct_var = None

        variances.append(
            CellVariance(
                dimension_key=bk,
                value_a=val_a,
                value_b=val_b,
                variance_absolute=abs_var,
                variance_percentage=pct_var,
            )
        )

    return VersionCompareResponse(
        version_id_a=version_id_a,
        version_id_b=version_id_b,
        version_name_a=version_a.name,
        version_name_b=version_b.name,
        line_item_id=line_item_id,
        cells=variances,
    )
