"""
DB-backed service for time dimensions (F009).

Wraps the pure engine (app.engine.time_calendar) and persists generated
time periods as DimensionItems linked to a Dimension of type="time".
"""

import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.time_calendar import (
    FiscalCalendar,
    TimePeriodType,
    generate_time_periods,
)
from app.models.dimension import Dimension, DimensionItem, DimensionType


async def create_time_dimension(
    db: AsyncSession,
    model_id: uuid.UUID,
    name: str,
    start_year: int,
    end_year: int,
    granularity: TimePeriodType,
    fiscal_calendar: Optional[FiscalCalendar] = None,
) -> Dimension:
    """Create a Dimension of type=time and populate it with generated periods.

    The hierarchy is encoded via parent_id on DimensionItems.  Metadata
    (start_date, end_date, period_type) is stored in a JSON-compatible way
    inside the item's *name* field — we embed the dates in the name as a
    suffix is NOT desirable; instead we store them in the ``code`` field
    as a structured string and keep ``name`` human-readable.

    Because DimensionItem has no generic metadata column we store the date
    range as part of the code in the format:

        <code>|<start_date>|<end_date>|<period_type>

    The ``get_time_periods`` service unpacks this automatically.
    """
    if fiscal_calendar is None:
        fiscal_calendar = FiscalCalendar()

    # 1. Create the Dimension row
    dimension = Dimension(
        name=name,
        dimension_type=DimensionType.time,
        model_id=model_id,
    )
    db.add(dimension)
    await db.flush()  # get dimension.id without committing

    # 2. Generate period dicts (flat list, hierarchically ordered)
    raw_periods = generate_time_periods(
        start_year=start_year,
        end_year=end_year,
        granularity=granularity,
        fiscal_calendar=fiscal_calendar,
    )

    # 3. Insert items in order, tracking code → UUID for parent resolution
    code_to_id: Dict[str, uuid.UUID] = {}

    for sort_order, period in enumerate(raw_periods):
        parent_code = period.get("parent_code")
        parent_id: Optional[uuid.UUID] = None
        if parent_code is not None:
            parent_id = code_to_id.get(parent_code)

        # Encode metadata into code field using pipe-separated format
        encoded_code = _encode_code(
            code=period["code"],
            start_date=period["start_date"],
            end_date=period["end_date"],
            period_type=period["period_type"].value if hasattr(period["period_type"], "value") else str(period["period_type"]),
        )

        item = DimensionItem(
            name=period["name"],
            code=encoded_code,
            dimension_id=dimension.id,
            parent_id=parent_id,
            sort_order=sort_order,
        )
        db.add(item)
        await db.flush()
        code_to_id[period["code"]] = item.id

    await db.commit()
    await db.refresh(dimension)
    return dimension


async def get_time_periods(
    db: AsyncSession,
    dimension_id: uuid.UUID,
) -> List[Dict[str, Any]]:
    """Return time items for a time dimension with decoded date metadata.

    Each dict contains:
        id, name, code, dimension_id, parent_id, sort_order,
        start_date, end_date, period_type
    """
    result = await db.execute(
        select(DimensionItem)
        .where(DimensionItem.dimension_id == dimension_id)
        .order_by(DimensionItem.sort_order, DimensionItem.name)
    )
    items = list(result.scalars().all())

    output: List[Dict[str, Any]] = []
    for item in items:
        decoded = _decode_code(item.code)
        output.append(
            {
                "id": str(item.id),
                "name": item.name,
                "code": decoded["code"],
                "dimension_id": str(item.dimension_id),
                "parent_id": str(item.parent_id) if item.parent_id else None,
                "sort_order": item.sort_order,
                "start_date": decoded.get("start_date"),
                "end_date": decoded.get("end_date"),
                "period_type": decoded.get("period_type"),
            }
        )
    return output


# ---------------------------------------------------------------------------
# Encoding helpers — keep metadata inside the code column
# ---------------------------------------------------------------------------

_SEP = "|"


def _encode_code(code: str, start_date: str, end_date: str, period_type: str) -> str:
    return f"{code}{_SEP}{start_date}{_SEP}{end_date}{_SEP}{period_type}"


def _decode_code(raw_code: str) -> Dict[str, Optional[str]]:
    parts = raw_code.split(_SEP, 3)
    if len(parts) == 4:
        return {
            "code": parts[0],
            "start_date": parts[1],
            "end_date": parts[2],
            "period_type": parts[3],
        }
    # Fallback for non-time items or malformed codes
    return {"code": raw_code, "start_date": None, "end_date": None, "period_type": None}
