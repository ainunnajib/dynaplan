import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dimension import Dimension, DimensionItem
from app.schemas.dimension import (
    DimensionCreate,
    DimensionItemCreate,
    DimensionItemNode,
    DimensionItemUpdate,
    DimensionUpdate,
)


# ── Dimension CRUD ─────────────────────────────────────────────────────────────

async def create_dimension(
    db: AsyncSession, model_id: uuid.UUID, data: DimensionCreate
) -> Dimension:
    dimension = Dimension(
        name=data.name,
        dimension_type=data.dimension_type,
        model_id=model_id,
    )
    db.add(dimension)
    await db.commit()
    await db.refresh(dimension)
    return dimension


async def get_dimension_by_id(
    db: AsyncSession, dimension_id: uuid.UUID
) -> Optional[Dimension]:
    result = await db.execute(
        select(Dimension).where(Dimension.id == dimension_id)
    )
    return result.scalar_one_or_none()


async def list_dimensions_for_model(
    db: AsyncSession, model_id: uuid.UUID
) -> List[Dimension]:
    result = await db.execute(
        select(Dimension).where(Dimension.model_id == model_id)
    )
    return list(result.scalars().all())


async def update_dimension(
    db: AsyncSession, dimension: Dimension, data: DimensionUpdate
) -> Dimension:
    if data.name is not None:
        dimension.name = data.name
    if data.dimension_type is not None:
        dimension.dimension_type = data.dimension_type
    await db.commit()
    await db.refresh(dimension)
    return dimension


async def delete_dimension(db: AsyncSession, dimension: Dimension) -> None:
    await db.delete(dimension)
    await db.commit()


# ── DimensionItem CRUD ─────────────────────────────────────────────────────────

async def create_dimension_item(
    db: AsyncSession, dimension_id: uuid.UUID, data: DimensionItemCreate
) -> DimensionItem:
    item = DimensionItem(
        name=data.name,
        code=data.code,
        dimension_id=dimension_id,
        parent_id=data.parent_id,
        sort_order=data.sort_order,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def get_dimension_item_by_id(
    db: AsyncSession, item_id: uuid.UUID
) -> Optional[DimensionItem]:
    result = await db.execute(
        select(DimensionItem).where(DimensionItem.id == item_id)
    )
    return result.scalar_one_or_none()


async def list_items_flat(
    db: AsyncSession, dimension_id: uuid.UUID
) -> List[DimensionItem]:
    result = await db.execute(
        select(DimensionItem)
        .where(DimensionItem.dimension_id == dimension_id)
        .order_by(DimensionItem.sort_order, DimensionItem.name)
    )
    return list(result.scalars().all())


async def update_dimension_item(
    db: AsyncSession, item: DimensionItem, data: DimensionItemUpdate
) -> DimensionItem:
    if data.name is not None:
        item.name = data.name
    if data.code is not None:
        item.code = data.code
    if data.sort_order is not None:
        item.sort_order = data.sort_order
    # parent_id can be explicitly set to None (to un-parent) or to a new UUID
    if "parent_id" in data.model_fields_set:
        item.parent_id = data.parent_id
    await db.commit()
    await db.refresh(item)
    return item


async def delete_dimension_item(db: AsyncSession, item: DimensionItem) -> None:
    await db.delete(item)
    await db.commit()


# ── Tree builder ───────────────────────────────────────────────────────────────

def _build_tree(
    items: List[DimensionItem],
    parent_id: Optional[uuid.UUID] = None,
) -> List[DimensionItemNode]:
    """Recursively build a tree from a flat list of items."""
    nodes: List[DimensionItemNode] = []
    children = [i for i in items if i.parent_id == parent_id]
    children.sort(key=lambda i: (i.sort_order, i.name))
    for child in children:
        node = DimensionItemNode(
            id=child.id,
            name=child.name,
            code=child.code,
            dimension_id=child.dimension_id,
            parent_id=child.parent_id,
            sort_order=child.sort_order,
            created_at=child.created_at,
            updated_at=child.updated_at,
            children=_build_tree(items, parent_id=child.id),
        )
        nodes.append(node)
    return nodes


async def get_items_as_tree(
    db: AsyncSession, dimension_id: uuid.UUID
) -> List[DimensionItemNode]:
    items = await list_items_flat(db, dimension_id)
    return _build_tree(items, parent_id=None)


# ── Reorder items ──────────────────────────────────────────────────────────────

async def reorder_items(
    db: AsyncSession,
    dimension_id: uuid.UUID,
    ordered_ids: List[uuid.UUID],
) -> List[DimensionItem]:
    """Set sort_order of items by their position in ordered_ids."""
    for position, item_id in enumerate(ordered_ids):
        item = await get_dimension_item_by_id(db, item_id)
        if item and item.dimension_id == dimension_id:
            item.sort_order = position
    await db.commit()
    return await list_items_flat(db, dimension_id)
