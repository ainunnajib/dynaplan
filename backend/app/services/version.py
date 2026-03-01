import uuid
from typing import Any, Dict, List, Optional

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

    # Fetch cells for the line item that contain the version dimension member IDs
    def _version_filter(version_id: uuid.UUID):
        return str(version_id)

    result_a = await db.execute(
        select(CellValue).where(
            CellValue.line_item_id == line_item_id,
            CellValue.dimension_key.contains(_version_filter(version_id_a)),
        )
    )
    cells_a = {cell.dimension_key: cell for cell in result_a.scalars().all()}

    result_b = await db.execute(
        select(CellValue).where(
            CellValue.line_item_id == line_item_id,
            CellValue.dimension_key.contains(_version_filter(version_id_b)),
        )
    )
    cells_b = {cell.dimension_key: cell for cell in result_b.scalars().all()}

    # Build a union of all dimension keys, normalizing so we can match
    # A cell keyed with version_a's id needs to be compared against the
    # equivalent key with version_b's id. We strip out the version segment
    # and use the rest as a base key.
    str_a = str(version_id_a)
    str_b = str(version_id_b)

    def _base_key(dimension_key: str, version_str: str) -> str:
        """Remove the version segment from a dimension key to get a comparable base."""
        parts = [p for p in dimension_key.split("|") if p != version_str]
        return "|".join(sorted(parts))

    # Build maps: base_key -> cell
    base_map_a: Dict[str, CellValue] = {}
    for dk, cell in cells_a.items():
        bk = _base_key(dk, str_a)
        base_map_a[bk] = cell

    base_map_b: Dict[str, CellValue] = {}
    for dk, cell in cells_b.items():
        bk = _base_key(dk, str_b)
        base_map_b[bk] = cell

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
