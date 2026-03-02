"""Service layer for F024: Scenario comparison.

Uses existing Version and CellValue models — no new ORM models are needed.
"""
import uuid
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cell import CellValue
from app.models.module import LineItem, Module
from app.models.planning_model import PlanningModel
from app.models.version import Version
from app.schemas.scenario_compare import (
    ComparisonMatrix,
    ComparisonResponse,
    ComparisonRow,
    VarianceSummary,
)
from app.services.cell_versioning import migrate_legacy_cell_versions


# ── Internal helpers ───────────────────────────────────────────────────────────

async def _get_model(db: AsyncSession, model_id: uuid.UUID) -> Optional[PlanningModel]:
    result = await db.execute(
        select(PlanningModel).where(PlanningModel.id == model_id)
    )
    return result.scalar_one_or_none()


async def _get_versions(
    db: AsyncSession, model_id: uuid.UUID, version_ids: List[uuid.UUID]
) -> Dict[uuid.UUID, Version]:
    """Return a dict of {version_id: Version} for the given IDs that belong to model_id."""
    result = await db.execute(
        select(Version).where(
            Version.model_id == model_id,
            Version.id.in_(version_ids),
        )
    )
    versions = result.scalars().all()
    return {v.id: v for v in versions}


async def _get_line_items(
    db: AsyncSession, model_id: uuid.UUID, line_item_ids: Optional[List[uuid.UUID]] = None
) -> Dict[uuid.UUID, LineItem]:
    """Return line items that belong to modules of the given model."""
    stmt = (
        select(LineItem)
        .join(Module, LineItem.module_id == Module.id)
        .where(Module.model_id == model_id)
    )
    if line_item_ids:
        stmt = stmt.where(LineItem.id.in_(line_item_ids))

    result = await db.execute(stmt)
    items = result.scalars().all()
    return {li.id: li for li in items}


async def _fetch_cells_for_line_items(
    db: AsyncSession,
    line_item_ids: List[uuid.UUID],
    dimension_filters: Optional[Dict[str, List[str]]] = None,
) -> List[CellValue]:
    """Fetch all CellValue rows for the given line items, with optional dimension filters."""
    if not line_item_ids:
        return []

    result = await db.execute(
        select(CellValue).where(CellValue.line_item_id.in_(line_item_ids))
    )
    cells = list(result.scalars().all())

    if dimension_filters:
        filtered = []
        for cell in cells:
            key_parts = set(cell.dimension_key.split("|")) if cell.dimension_key else set()
            matches = True
            for _dim_id, allowed_members in dimension_filters.items():
                allowed_strs = set(allowed_members)
                if not key_parts.intersection(allowed_strs):
                    matches = False
                    break
            if matches:
                filtered.append(cell)
        cells = filtered

    return cells


# ── Public service functions ───────────────────────────────────────────────────

async def compare_versions(
    db: AsyncSession,
    model_id: uuid.UUID,
    version_ids: List[uuid.UUID],
    line_item_ids: Optional[List[uuid.UUID]] = None,
    dimension_filters: Optional[Dict[str, List[str]]] = None,
) -> Optional[ComparisonResponse]:
    """Fetch cell values for each version, align by dimension_key, and compute differences.

    Returns list of comparison rows with:
    - line_item_id, line_item_name, dimension_key
    - values per version (dict: version_id -> float or None)
    - absolute_diff and percentage_diff (only set when exactly 2 versions)

    Returns None if model or any requested version is not found.
    """
    # Validate model exists
    model = await _get_model(db, model_id)
    if model is None:
        return None

    # Validate versions
    versions_map = await _get_versions(db, model_id, version_ids)
    if len(versions_map) != len(version_ids):
        return None

    await migrate_legacy_cell_versions(db, model_id=model_id)

    # Get line items for this model (or subset)
    line_items_map = await _get_line_items(db, model_id, line_item_ids)
    if not line_items_map:
        # Return empty comparison
        version_names = {str(vid): versions_map[vid].name for vid in version_ids}
        return ComparisonResponse(rows=[], version_names=version_names)

    # Fetch all cells for those line items
    all_cells = await _fetch_cells_for_line_items(
        db, list(line_items_map.keys()), dimension_filters
    )

    # Build index: (line_item_id, dimension_key) -> {version_id_str: float or None}
    # The dimension_key for a versioned cell contains the version UUID as one segment.
    # We normalize by removing the version segment to get a "base key" for alignment.
    str_version_ids = {str(vid) for vid in version_ids}

    # For each cell, figure out which version it belongs to and what its base key is.
    # Structure: (line_item_id, base_key) -> {version_id_str: value}
    alignment: Dict[tuple, Dict[str, Optional[float]]] = {}

    for cell in all_cells:
        key_parts = cell.dimension_key.split("|") if cell.dimension_key else []
        cell_version: Optional[str] = None
        if cell.version_id is not None and str(cell.version_id) in str_version_ids:
            cell_version = str(cell.version_id)
        # Legacy fallback: detect version context in dimension_key.
        if cell_version is None:
            for part in key_parts:
                if part in str_version_ids:
                    cell_version = part
                    break

        if cell_version is None:
            # Cell doesn't contain a version dimension — treat as shared across all versions.
            # Use the full dimension_key as the base key.
            base_key = cell.dimension_key
            # Record value for each version (same value)
            entry_key = (str(cell.line_item_id), base_key)
            if entry_key not in alignment:
                alignment[entry_key] = {}
            for vid_str in [str(v) for v in version_ids]:
                if vid_str not in alignment[entry_key]:
                    alignment[entry_key][vid_str] = cell.value_number
        else:
            # Remove the version segment to get the base key
            base_parts = sorted(p for p in key_parts if p != cell_version)
            base_key = "|".join(base_parts)
            entry_key = (str(cell.line_item_id), base_key)
            if entry_key not in alignment:
                alignment[entry_key] = {}
            alignment[entry_key][cell_version] = cell.value_number

    # Build ComparisonRow list
    version_id_strs = [str(vid) for vid in version_ids]
    version_names = {str(vid): versions_map[vid].name for vid in version_ids}

    rows: List[ComparisonRow] = []
    for (li_id_str, base_key), version_values in sorted(alignment.items()):
        li_id = uuid.UUID(li_id_str)
        line_item = line_items_map.get(li_id)
        if line_item is None:
            continue

        # Fill in None for missing versions
        values: Dict[str, Optional[float]] = {}
        for vid_str in version_id_strs:
            values[vid_str] = version_values.get(vid_str)

        # Compute diff only for 2-version comparisons
        absolute_diff: Optional[float] = None
        percentage_diff: Optional[float] = None
        if len(version_id_strs) == 2:
            val_base = values.get(version_id_strs[0])
            val_compare = values.get(version_id_strs[1])
            if val_base is not None and val_compare is not None:
                absolute_diff = val_compare - val_base
                if val_base != 0:
                    percentage_diff = (absolute_diff / abs(val_base)) * 100.0
                else:
                    percentage_diff = None

        rows.append(
            ComparisonRow(
                line_item_id=li_id_str,
                line_item_name=line_item.name,
                dimension_key=base_key,
                values=values,
                absolute_diff=absolute_diff,
                percentage_diff=percentage_diff,
            )
        )

    return ComparisonResponse(rows=rows, version_names=version_names)


async def get_variance_summary(
    db: AsyncSession,
    model_id: uuid.UUID,
    base_version_id: uuid.UUID,
    compare_version_id: uuid.UUID,
    line_item_ids: Optional[List[uuid.UUID]] = None,
) -> Optional[VarianceSummary]:
    """Aggregate variance stats between two versions.

    Returns VarianceSummary with:
    - total_absolute_diff: sum of |value_compare - value_base| for all changed cells
    - avg_percentage_diff: average percentage difference across changed cells
    - changed_cells: number of cells with different values
    - unchanged_cells: number of cells with identical values (present in both)
    - total_cells: total cells considered (union of both versions)

    Returns None if model or versions not found.
    """
    result = await compare_versions(
        db,
        model_id=model_id,
        version_ids=[base_version_id, compare_version_id],
        line_item_ids=line_item_ids,
    )
    if result is None:
        return None

    base_str = str(base_version_id)
    compare_str = str(compare_version_id)

    total_abs = 0.0
    pct_diffs: List[float] = []
    changed = 0
    unchanged = 0
    total = len(result.rows)

    for row in result.rows:
        val_base = row.values.get(base_str)
        val_compare = row.values.get(compare_str)

        if val_base is None and val_compare is None:
            unchanged += 1
            continue

        if val_base is None or val_compare is None:
            # One side is missing — counts as changed
            if val_compare is not None and val_base is not None:
                diff = abs(val_compare - val_base)
            else:
                diff = abs(val_compare or 0.0) + abs(val_base or 0.0)
            total_abs += diff
            changed += 1
            continue

        diff = abs(val_compare - val_base)
        total_abs += diff

        if diff == 0.0:
            unchanged += 1
        else:
            changed += 1
            if val_base != 0:
                pct_diffs.append((val_compare - val_base) / abs(val_base) * 100.0)

    avg_pct: Optional[float] = None
    if pct_diffs:
        avg_pct = sum(pct_diffs) / len(pct_diffs)

    return VarianceSummary(
        total_absolute_diff=total_abs,
        avg_percentage_diff=avg_pct,
        changed_cells=changed,
        unchanged_cells=unchanged,
        total_cells=total,
    )


async def get_comparison_matrix(
    db: AsyncSession,
    model_id: uuid.UUID,
    version_ids: List[uuid.UUID],
    line_item_id: uuid.UUID,
) -> Optional[ComparisonMatrix]:
    """For a single line item, get all cells across versions in a matrix format.

    Returns ComparisonMatrix with:
    - line_item_id
    - version_names: {version_id -> name}
    - dimension_keys: sorted list of all dimension keys (base keys)
    - matrix: {base_key -> {version_id -> value}}

    Returns None if model or any version is not found.
    """
    result = await compare_versions(
        db,
        model_id=model_id,
        version_ids=version_ids,
        line_item_ids=[line_item_id],
    )
    if result is None:
        return None

    li_id_str = str(line_item_id)
    matrix: Dict[str, Dict[str, Optional[float]]] = {}
    dimension_keys: List[str] = []

    for row in result.rows:
        if row.line_item_id != li_id_str:
            continue
        matrix[row.dimension_key] = row.values
        if row.dimension_key not in dimension_keys:
            dimension_keys.append(row.dimension_key)

    dimension_keys.sort()

    return ComparisonMatrix(
        line_item_id=li_id_str,
        version_names=result.version_names,
        matrix=matrix,
        dimension_keys=dimension_keys,
    )
