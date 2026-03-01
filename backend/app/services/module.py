import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.module import LineItem, LineItemDimension, Module
from app.schemas.module import (
    LineItemCreate,
    LineItemUpdate,
    ModuleCreate,
    ModuleUpdate,
)


# ── Module CRUD ─────────────────────────────────────────────────────────────────

async def create_module(
    db: AsyncSession, model_id: uuid.UUID, data: ModuleCreate
) -> Module:
    module = Module(
        name=data.name,
        description=data.description,
        model_id=model_id,
    )
    db.add(module)
    await db.commit()
    await db.refresh(module)
    return module


async def get_module_by_id(
    db: AsyncSession, module_id: uuid.UUID
) -> Optional[Module]:
    result = await db.execute(
        select(Module)
        .where(Module.id == module_id)
        .options(
            selectinload(Module.line_items).selectinload(
                LineItem.line_item_dimensions
            )
        )
    )
    return result.scalar_one_or_none()


async def list_modules_for_model(
    db: AsyncSession, model_id: uuid.UUID
) -> List[Module]:
    result = await db.execute(
        select(Module).where(Module.model_id == model_id)
    )
    return list(result.scalars().all())


async def update_module(
    db: AsyncSession, module: Module, data: ModuleUpdate
) -> Module:
    if data.name is not None:
        module.name = data.name
    if "description" in data.model_fields_set:
        module.description = data.description
    await db.commit()
    await db.refresh(module)
    return module


async def delete_module(db: AsyncSession, module: Module) -> None:
    await db.delete(module)
    await db.commit()


# ── LineItem CRUD ──────────────────────────────────────────────────────────────

def _dedupe_dimension_ids(dimension_ids: List[uuid.UUID]) -> List[uuid.UUID]:
    seen = set()
    deduped: List[uuid.UUID] = []
    for dimension_id in dimension_ids:
        if dimension_id in seen:
            continue
        seen.add(dimension_id)
        deduped.append(dimension_id)
    return deduped


async def _replace_line_item_dimensions(
    db: AsyncSession,
    line_item: LineItem,
    dimension_ids: List[uuid.UUID],
) -> None:
    dimension_ids = _dedupe_dimension_ids(dimension_ids)
    dimension_position = {
        dimension_id: index for index, dimension_id in enumerate(dimension_ids)
    }
    target_ids = set(dimension_position.keys())

    existing_result = await db.execute(
        select(LineItemDimension).where(
            LineItemDimension.line_item_id == line_item.id
        )
    )
    existing_links = list(existing_result.scalars().all())
    existing_map = {link.dimension_id: link for link in existing_links}

    for link in existing_links:
        if link.dimension_id not in target_ids:
            await db.delete(link)

    for dimension_id, position in dimension_position.items():
        existing = existing_map.get(dimension_id)
        if existing is not None:
            existing.sort_order = position
            continue
        db.add(
            LineItemDimension(
                line_item_id=line_item.id,
                dimension_id=dimension_id,
                sort_order=position,
            )
        )

    await db.flush()


async def create_line_item(
    db: AsyncSession, module_id: uuid.UUID, data: LineItemCreate
) -> LineItem:
    line_item = LineItem(
        name=data.name,
        module_id=module_id,
        format=data.format,
        formula=data.formula,
        summary_method=data.summary_method,
        sort_order=data.sort_order,
    )
    db.add(line_item)
    await db.flush()

    await _replace_line_item_dimensions(
        db,
        line_item=line_item,
        dimension_ids=(
            data.applies_to_dimensions
            if data.applies_to_dimensions is not None
            else []
        ),
    )

    await db.commit()
    created = await get_line_item_by_id(db, line_item.id)
    return created if created is not None else line_item


async def get_line_item_by_id(
    db: AsyncSession, line_item_id: uuid.UUID
) -> Optional[LineItem]:
    result = await db.execute(
        select(LineItem)
        .where(LineItem.id == line_item_id)
        .execution_options(populate_existing=True)
        .options(selectinload(LineItem.line_item_dimensions))
    )
    return result.scalar_one_or_none()


async def get_line_item_dimension_ids(
    db: AsyncSession,
    line_item_id: uuid.UUID,
) -> List[uuid.UUID]:
    result = await db.execute(
        select(LineItemDimension.dimension_id)
        .where(LineItemDimension.line_item_id == line_item_id)
        .order_by(LineItemDimension.sort_order)
    )
    return list(result.scalars().all())


async def list_line_items_for_module(
    db: AsyncSession, module_id: uuid.UUID
) -> List[LineItem]:
    result = await db.execute(
        select(LineItem)
        .where(LineItem.module_id == module_id)
        .options(selectinload(LineItem.line_item_dimensions))
        .order_by(LineItem.sort_order, LineItem.name)
    )
    return list(result.scalars().all())


async def list_line_items_for_dimension(
    db: AsyncSession,
    dimension_id: uuid.UUID,
) -> List[LineItem]:
    result = await db.execute(
        select(LineItem)
        .join(LineItemDimension, LineItemDimension.line_item_id == LineItem.id)
        .where(LineItemDimension.dimension_id == dimension_id)
        .options(selectinload(LineItem.line_item_dimensions))
        .order_by(LineItem.sort_order, LineItem.name)
    )
    return list(result.scalars().unique().all())


async def update_line_item(
    db: AsyncSession, line_item: LineItem, data: LineItemUpdate
) -> LineItem:
    if data.name is not None:
        line_item.name = data.name
    if data.format is not None:
        line_item.format = data.format
    if "formula" in data.model_fields_set:
        line_item.formula = data.formula
    if data.summary_method is not None:
        line_item.summary_method = data.summary_method
    if "applies_to_dimensions" in data.model_fields_set:
        await _replace_line_item_dimensions(
            db,
            line_item=line_item,
            dimension_ids=(
                data.applies_to_dimensions
                if data.applies_to_dimensions is not None
                else []
            ),
        )
    if data.sort_order is not None:
        line_item.sort_order = data.sort_order
    await db.commit()
    updated = await get_line_item_by_id(db, line_item.id)
    return updated if updated is not None else line_item


async def delete_line_item(db: AsyncSession, line_item: LineItem) -> None:
    await db.delete(line_item)
    await db.commit()


# ── Reorder line items ─────────────────────────────────────────────────────────

async def reorder_line_items(
    db: AsyncSession,
    module_id: uuid.UUID,
    ordered_ids: List[uuid.UUID],
) -> List[LineItem]:
    """Set sort_order of line items by their position in ordered_ids."""
    for position, line_item_id in enumerate(ordered_ids):
        line_item = await get_line_item_by_id(db, line_item_id)
        if line_item and line_item.module_id == module_id:
            line_item.sort_order = position
    await db.commit()
    return await list_line_items_for_module(db, module_id)
