import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cell import CellValue
from app.schemas.cell import CellRead, CellWrite


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_dimension_key(dimension_member_ids: List[uuid.UUID]) -> str:
    """Sort UUIDs and join with pipe to form a deterministic dimension key."""
    sorted_ids = sorted(str(uid) for uid in dimension_member_ids)
    return "|".join(sorted_ids)


def _extract_value_and_type(value: Any):
    """Return (value_number, value_text, value_boolean, value_type) from a raw value."""
    if value is None:
        return None, None, None, "null"
    if isinstance(value, bool):
        return None, None, value, "boolean"
    if isinstance(value, (int, float)):
        return float(value), None, None, "number"
    if isinstance(value, str):
        return None, value, None, "text"
    # Fallback — store as text
    return None, str(value), None, "text"


def _cell_to_read(cell: CellValue) -> CellRead:
    """Convert a CellValue ORM object to a CellRead schema."""
    # Determine the canonical value and its type
    if cell.value_boolean is not None:
        value = cell.value_boolean
        value_type = "boolean"
    elif cell.value_number is not None:
        value = cell.value_number
        value_type = "number"
    elif cell.value_text is not None:
        value = cell.value_text
        value_type = "text"
    else:
        value = None
        value_type = "null"

    dimension_members = [
        uuid.UUID(part)
        for part in cell.dimension_key.split("|")
        if part
    ] if cell.dimension_key else []

    return CellRead(
        line_item_id=cell.line_item_id,
        dimension_members=dimension_members,
        dimension_key=cell.dimension_key,
        value=value,
        value_type=value_type,
    )


# ── Write operations ───────────────────────────────────────────────────────────

async def write_cell(
    db: AsyncSession,
    line_item_id: uuid.UUID,
    dimension_members: List[uuid.UUID],
    value: Any,
) -> CellRead:
    """Upsert a single cell value."""
    dimension_key = make_dimension_key(dimension_members)
    value_number, value_text, value_boolean, value_type = _extract_value_and_type(value)

    # Try to find an existing cell
    result = await db.execute(
        select(CellValue).where(
            CellValue.line_item_id == line_item_id,
            CellValue.dimension_key == dimension_key,
        )
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        existing.value_number = value_number
        existing.value_text = value_text
        existing.value_boolean = value_boolean
        await db.commit()
        await db.refresh(existing)
        return _cell_to_read(existing)
    else:
        cell = CellValue(
            line_item_id=line_item_id,
            dimension_key=dimension_key,
            value_number=value_number,
            value_text=value_text,
            value_boolean=value_boolean,
        )
        db.add(cell)
        await db.commit()
        await db.refresh(cell)
        return _cell_to_read(cell)


async def write_cells_bulk(
    db: AsyncSession,
    cells: List[CellWrite],
) -> List[CellRead]:
    """Bulk upsert multiple cell values."""
    results = []
    for cell_write in cells:
        cell_read = await write_cell(
            db,
            line_item_id=cell_write.line_item_id,
            dimension_members=cell_write.dimension_members,
            value=cell_write.value,
        )
        results.append(cell_read)
    return results


# ── Read operations ────────────────────────────────────────────────────────────

async def read_cell(
    db: AsyncSession,
    line_item_id: uuid.UUID,
    dimension_members: List[uuid.UUID],
) -> Optional[CellRead]:
    """Read a single cell value."""
    dimension_key = make_dimension_key(dimension_members)
    result = await db.execute(
        select(CellValue).where(
            CellValue.line_item_id == line_item_id,
            CellValue.dimension_key == dimension_key,
        )
    )
    cell = result.scalar_one_or_none()
    if cell is None:
        return None
    return _cell_to_read(cell)


async def read_cells_for_line_item(
    db: AsyncSession,
    line_item_id: uuid.UUID,
    dimension_filters: Optional[Dict[str, List[uuid.UUID]]] = None,
) -> List[CellRead]:
    """Read all cells for a line item, optionally filtered by dimension members.

    dimension_filters maps dimension_item_id (as string) to a list of acceptable
    dimension_item UUIDs. A cell is included only if its dimension_key contains
    at least one member from each filter entry.
    """
    result = await db.execute(
        select(CellValue).where(CellValue.line_item_id == line_item_id)
    )
    cells = list(result.scalars().all())

    if dimension_filters:
        filtered = []
        for cell in cells:
            key_parts = set(cell.dimension_key.split("|")) if cell.dimension_key else set()
            matches = True
            for _dim_id, allowed_members in dimension_filters.items():
                allowed_strs = {str(m) for m in allowed_members}
                if not key_parts.intersection(allowed_strs):
                    matches = False
                    break
            if matches:
                filtered.append(cell)
        cells = filtered

    return [_cell_to_read(cell) for cell in cells]


# ── Delete operations ──────────────────────────────────────────────────────────

async def delete_cells_for_line_item(
    db: AsyncSession,
    line_item_id: uuid.UUID,
) -> int:
    """Delete all cells for a line item. Returns the number of deleted rows."""
    result = await db.execute(
        delete(CellValue).where(CellValue.line_item_id == line_item_id)
    )
    await db.commit()
    return result.rowcount
