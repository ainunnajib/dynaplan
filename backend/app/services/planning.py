"""
Service layer for F025: Top-down & bottom-up planning.

Coordinates between the spread engine, dimension service, and cell storage.
"""
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.spread import SpreadMethod, aggregate_values, spread_value
from app.models.cell import CellValue
from app.models.dimension import Dimension, DimensionItem
from app.models.module import LineItem
from app.schemas.planning import (
    AggregateResponse,
    BulkSpreadResponse,
    HierarchyMemberValue,
    HierarchyValuesResponse,
    MemberValue,
    RecalculateHierarchyResponse,
    SpreadResponse,
)
from app.services.cell import make_dimension_key, write_cell


# ── Private helpers ────────────────────────────────────────────────────────────

async def _get_line_item(db: AsyncSession, line_item_id: uuid.UUID) -> Optional[LineItem]:
    result = await db.execute(
        select(LineItem).where(LineItem.id == line_item_id)
    )
    return result.scalar_one_or_none()


async def _get_dimension_item(db: AsyncSession, item_id: uuid.UUID) -> Optional[DimensionItem]:
    result = await db.execute(
        select(DimensionItem).where(DimensionItem.id == item_id)
    )
    return result.scalar_one_or_none()


async def _get_children(
    db: AsyncSession, parent_id: uuid.UUID
) -> List[DimensionItem]:
    result = await db.execute(
        select(DimensionItem)
        .where(DimensionItem.parent_id == parent_id)
        .order_by(DimensionItem.sort_order, DimensionItem.name)
    )
    return list(result.scalars().all())


async def _get_all_items_in_dimension(
    db: AsyncSession, dimension_id: uuid.UUID
) -> List[DimensionItem]:
    result = await db.execute(
        select(DimensionItem).where(DimensionItem.dimension_id == dimension_id)
    )
    return list(result.scalars().all())


async def _read_cell_value(
    db: AsyncSession,
    line_item_id: uuid.UUID,
    member_id: uuid.UUID,
) -> float:
    """Read the numeric value of a cell for a single dimension member. Returns 0.0 if not found."""
    dim_key = make_dimension_key([member_id])
    result = await db.execute(
        select(CellValue).where(
            CellValue.line_item_id == line_item_id,
            CellValue.dimension_key == dim_key,
        )
    )
    cell = result.scalar_one_or_none()
    if cell is None or cell.value_number is None:
        return 0.0
    return cell.value_number


# ── Public service functions ───────────────────────────────────────────────────

async def spread_top_down(
    db: AsyncSession,
    line_item_id: uuid.UUID,
    parent_dimension_member_id: uuid.UUID,
    target_value: float,
    method: SpreadMethod,
    weights: Optional[List[float]] = None,
) -> SpreadResponse:
    """Spread a target value from a parent dimension member to its children.

    Reads existing child values (for proportional/manual methods), applies the
    spread engine, and writes the resulting values back as cells.

    Args:
        db: Database session.
        line_item_id: The line item whose cells to update.
        parent_dimension_member_id: The parent dimension item UUID.
        target_value: The total value to spread across children.
        method: SpreadMethod enum value.
        weights: Optional list of weights for 'weighted' method.

    Returns:
        SpreadResponse with list of (member_id, value) pairs written.

    Raises:
        ValueError: If line item or parent member not found, or no children.
    """
    line_item = await _get_line_item(db, line_item_id)
    if line_item is None:
        raise ValueError(f"LineItem {line_item_id} not found")

    parent_item = await _get_dimension_item(db, parent_dimension_member_id)
    if parent_item is None:
        raise ValueError(f"DimensionItem {parent_dimension_member_id} not found")

    children = await _get_children(db, parent_dimension_member_id)
    if not children:
        raise ValueError(
            f"DimensionItem {parent_dimension_member_id} has no children to spread to"
        )

    member_count = len(children)

    # Gather existing values for proportional/manual methods
    existing_values: Optional[List[float]] = None
    if method in (SpreadMethod.proportional, SpreadMethod.manual):
        existing_values = []
        for child in children:
            val = await _read_cell_value(db, line_item_id, child.id)
            existing_values.append(val)

    distributed = spread_value(
        total=target_value,
        member_count=member_count,
        method=method,
        weights=weights,
        existing_values=existing_values,
    )

    cells_updated: List[MemberValue] = []
    for child, value in zip(children, distributed):
        await write_cell(
            db,
            line_item_id=line_item_id,
            dimension_members=[child.id],
            value=value,
        )
        cells_updated.append(MemberValue(member_id=child.id, value=value))

    return SpreadResponse(line_item_id=line_item_id, cells_updated=cells_updated)


async def aggregate_bottom_up(
    db: AsyncSession,
    line_item_id: uuid.UUID,
    parent_dimension_member_id: uuid.UUID,
) -> AggregateResponse:
    """Read children cell values, aggregate using line item's summary_method,
    and write the aggregated value to the parent cell.

    Args:
        db: Database session.
        line_item_id: The line item whose cells to aggregate.
        parent_dimension_member_id: The parent dimension item UUID.

    Returns:
        AggregateResponse with parent_value and list of children values.

    Raises:
        ValueError: If line item or parent member not found.
    """
    line_item = await _get_line_item(db, line_item_id)
    if line_item is None:
        raise ValueError(f"LineItem {line_item_id} not found")

    parent_item = await _get_dimension_item(db, parent_dimension_member_id)
    if parent_item is None:
        raise ValueError(f"DimensionItem {parent_dimension_member_id} not found")

    children = await _get_children(db, parent_dimension_member_id)

    children_values: List[MemberValue] = []
    raw_values: List[float] = []
    for child in children:
        val = await _read_cell_value(db, line_item_id, child.id)
        raw_values.append(val)
        children_values.append(MemberValue(member_id=child.id, value=val))

    # Map SummaryMethod enum to string key used in aggregate_values engine
    # 'none' and 'formula' are not aggregation operations — fall back to 'sum'
    summary_str = line_item.summary_method.value if line_item.summary_method else "sum"
    if summary_str in ("none", "formula"):
        summary_str = "sum"

    parent_value = aggregate_values(raw_values, summary_str)

    # Write the aggregated value to the parent cell
    await write_cell(
        db,
        line_item_id=line_item_id,
        dimension_members=[parent_dimension_member_id],
        value=parent_value,
    )

    return AggregateResponse(
        parent_value=parent_value,
        children_values=children_values,
    )


async def get_hierarchy_values(
    db: AsyncSession,
    line_item_id: uuid.UUID,
    dimension_id: uuid.UUID,
    parent_member_id: Optional[uuid.UUID] = None,
) -> HierarchyValuesResponse:
    """Get values for a parent and all its children for a given line item.

    If parent_member_id is None, returns values for all top-level items
    (items with no parent in the dimension).

    Args:
        db: Database session.
        line_item_id: The line item to read values for.
        dimension_id: The dimension to look up members from.
        parent_member_id: Optional parent member UUID.

    Returns:
        HierarchyValuesResponse with parent value and list of child values.
    """
    line_item = await _get_line_item(db, line_item_id)
    if line_item is None:
        raise ValueError(f"LineItem {line_item_id} not found")

    # Verify dimension exists
    dim_result = await db.execute(
        select(Dimension).where(Dimension.id == dimension_id)
    )
    dimension = dim_result.scalar_one_or_none()
    if dimension is None:
        raise ValueError(f"Dimension {dimension_id} not found")

    parent_value: Optional[float] = None
    children_list: List[HierarchyMemberValue] = []

    if parent_member_id is not None:
        parent_item = await _get_dimension_item(db, parent_member_id)
        if parent_item is None:
            raise ValueError(f"DimensionItem {parent_member_id} not found")
        parent_value = await _read_cell_value(db, line_item_id, parent_member_id)
        children = await _get_children(db, parent_member_id)
        for child in children:
            val = await _read_cell_value(db, line_item_id, child.id)
            children_list.append(
                HierarchyMemberValue(
                    member_id=child.id,
                    member_name=child.name,
                    value=val,
                    is_parent=False,
                )
            )
    else:
        # No parent — return all top-level items in the dimension
        all_items = await _get_all_items_in_dimension(db, dimension_id)
        top_level = [i for i in all_items if i.parent_id is None]
        top_level.sort(key=lambda i: (i.sort_order, i.name))
        for item in top_level:
            val = await _read_cell_value(db, line_item_id, item.id)
            children_list.append(
                HierarchyMemberValue(
                    member_id=item.id,
                    member_name=item.name,
                    value=val,
                    is_parent=False,
                )
            )

    return HierarchyValuesResponse(
        line_item_id=line_item_id,
        parent_member_id=parent_member_id,
        parent_value=parent_value,
        children=children_list,
    )


async def bulk_spread(
    db: AsyncSession,
    line_item_id: uuid.UUID,
    spreads: List[Dict[str, Any]],
) -> BulkSpreadResponse:
    """Apply multiple spread operations for the same line item.

    Args:
        db: Database session.
        line_item_id: The line item to spread values for.
        spreads: List of dicts, each with keys:
                 parent_member_id, target_value, method, weights (optional).

    Returns:
        BulkSpreadResponse with a list of SpreadResponse objects.
    """
    results: List[SpreadResponse] = []
    for spread in spreads:
        result = await spread_top_down(
            db=db,
            line_item_id=line_item_id,
            parent_dimension_member_id=spread["parent_member_id"],
            target_value=spread["target_value"],
            method=spread["method"],
            weights=spread.get("weights"),
        )
        results.append(result)
    return BulkSpreadResponse(results=results)


async def recalculate_hierarchy(
    db: AsyncSession,
    line_item_id: uuid.UUID,
    dimension_id: uuid.UUID,
) -> RecalculateHierarchyResponse:
    """Bottom-up recalculate the entire hierarchy for a dimension.

    Traverses all items in the dimension bottom-up and aggregates each parent
    from its children.

    Args:
        db: Database session.
        line_item_id: The line item to recalculate.
        dimension_id: The dimension whose hierarchy to recalculate.

    Returns:
        RecalculateHierarchyResponse with count of updated cells.
    """
    line_item = await _get_line_item(db, line_item_id)
    if line_item is None:
        raise ValueError(f"LineItem {line_item_id} not found")

    dim_result = await db.execute(
        select(Dimension).where(Dimension.id == dimension_id)
    )
    dimension = dim_result.scalar_one_or_none()
    if dimension is None:
        raise ValueError(f"Dimension {dimension_id} not found")

    all_items = await _get_all_items_in_dimension(db, dimension_id)

    # Build a mapping from id -> item and id -> children
    item_map: Dict[uuid.UUID, DimensionItem] = {item.id: item for item in all_items}
    children_map: Dict[uuid.UUID, List[DimensionItem]] = {}
    for item in all_items:
        if item.parent_id is not None:
            if item.parent_id not in children_map:
                children_map[item.parent_id] = []
            children_map[item.parent_id].append(item)

    # Find all parent nodes (items that have children)
    parent_ids = set(children_map.keys())

    # Topological order: process leaf-to-root
    # We do a post-order traversal — compute leaves first, then parents
    def _get_depth(item_id: uuid.UUID) -> int:
        item = item_map.get(item_id)
        if item is None:
            return 0
        if item.parent_id is None:
            return 0
        return 1 + _get_depth(item.parent_id)

    # Sort parents by depth descending (deepest first)
    sorted_parents = sorted(parent_ids, key=lambda pid: _get_depth(pid), reverse=True)

    summary_str = line_item.summary_method.value if line_item.summary_method else "sum"
    if summary_str in ("none", "formula"):
        summary_str = "sum"
    members_updated = 0

    for parent_id in sorted_parents:
        children = children_map.get(parent_id, [])
        raw_values: List[float] = []
        for child in children:
            val = await _read_cell_value(db, line_item_id, child.id)
            raw_values.append(val)

        parent_value = aggregate_values(raw_values, summary_str)
        await write_cell(
            db,
            line_item_id=line_item_id,
            dimension_members=[parent_id],
            value=parent_value,
        )
        members_updated += 1

    return RecalculateHierarchyResponse(
        line_item_id=line_item_id,
        dimension_id=dimension_id,
        members_updated=members_updated,
    )
