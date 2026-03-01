import re
import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dimension import DimensionItem
from app.models.module import LineItem
from app.models.subset import (
    LineItemSubset,
    LineItemSubsetMember,
    ListSubset,
    ListSubsetMember,
)
from app.schemas.subset import (
    LineItemSubsetCreate,
    LineItemSubsetUpdate,
    ListSubsetCreate,
    ListSubsetUpdate,
)


# ── ListSubset CRUD ───────────────────────────────────────────────────────────

async def create_list_subset(
    db: AsyncSession, dimension_id: uuid.UUID, data: ListSubsetCreate
) -> ListSubset:
    subset = ListSubset(
        dimension_id=dimension_id,
        name=data.name,
        description=data.description,
        is_dynamic=data.is_dynamic,
        filter_expression=data.filter_expression,
    )
    db.add(subset)
    await db.commit()
    await db.refresh(subset)
    return subset


async def get_list_subset_by_id(
    db: AsyncSession, subset_id: uuid.UUID
) -> Optional[ListSubset]:
    result = await db.execute(
        select(ListSubset).where(ListSubset.id == subset_id)
    )
    return result.scalar_one_or_none()


async def list_subsets_for_dimension(
    db: AsyncSession, dimension_id: uuid.UUID
) -> List[ListSubset]:
    result = await db.execute(
        select(ListSubset).where(ListSubset.dimension_id == dimension_id)
    )
    return list(result.scalars().all())


async def update_list_subset(
    db: AsyncSession, subset: ListSubset, data: ListSubsetUpdate
) -> ListSubset:
    if data.name is not None:
        subset.name = data.name
    if data.description is not None:
        subset.description = data.description
    if data.is_dynamic is not None:
        subset.is_dynamic = data.is_dynamic
    if data.filter_expression is not None:
        subset.filter_expression = data.filter_expression
    await db.commit()
    await db.refresh(subset)
    return subset


async def delete_list_subset(db: AsyncSession, subset: ListSubset) -> None:
    await db.delete(subset)
    await db.commit()


# ── ListSubsetMember management ───────────────────────────────────────────────

async def add_list_subset_members(
    db: AsyncSession,
    subset_id: uuid.UUID,
    dimension_item_ids: List[uuid.UUID],
) -> List[ListSubsetMember]:
    # Get existing member item IDs to avoid duplicates
    result = await db.execute(
        select(ListSubsetMember.dimension_item_id).where(
            ListSubsetMember.subset_id == subset_id
        )
    )
    existing_ids = set(result.scalars().all())

    new_members = []
    for item_id in dimension_item_ids:
        if item_id not in existing_ids:
            member = ListSubsetMember(
                subset_id=subset_id,
                dimension_item_id=item_id,
            )
            db.add(member)
            new_members.append(member)
    await db.commit()
    for m in new_members:
        await db.refresh(m)
    return new_members


async def get_list_subset_member_by_id(
    db: AsyncSession, member_id: uuid.UUID
) -> Optional[ListSubsetMember]:
    result = await db.execute(
        select(ListSubsetMember).where(ListSubsetMember.id == member_id)
    )
    return result.scalar_one_or_none()


async def remove_list_subset_member(
    db: AsyncSession, member: ListSubsetMember
) -> None:
    await db.delete(member)
    await db.commit()


# ── Dynamic subset resolution ────────────────────────────────────────────────

def _evaluate_filter(
    items: List[DimensionItem], filter_expression: str
) -> List[DimensionItem]:
    """Evaluate a simple filter expression against dimension items.

    Supported filter syntax:
    - name:contains:<value> — name contains value (case-insensitive)
    - code:startswith:<value> — code starts with value (case-insensitive)
    - code:eq:<value> — code equals value (case-insensitive)
    - name:matches:<regex> — name matches regex pattern
    """
    if not filter_expression or not filter_expression.strip():
        return list(items)

    parts = filter_expression.strip().split(":", 2)
    if len(parts) < 3:
        return list(items)

    field, op, value = parts[0].lower(), parts[1].lower(), parts[2]

    result = []
    for item in items:
        field_value = ""
        if field == "name":
            field_value = item.name
        elif field == "code":
            field_value = item.code
        else:
            continue

        if op == "contains":
            if value.lower() in field_value.lower():
                result.append(item)
        elif op == "startswith":
            if field_value.lower().startswith(value.lower()):
                result.append(item)
        elif op == "eq":
            if field_value.lower() == value.lower():
                result.append(item)
        elif op == "matches":
            try:
                if re.search(value, field_value, re.IGNORECASE):
                    result.append(item)
            except re.error:
                pass

    return result


async def resolve_list_subset_members(
    db: AsyncSession, subset: ListSubset
) -> List[DimensionItem]:
    """Get resolved members for a list subset.

    For static subsets, returns the explicitly added members.
    For dynamic subsets, evaluates the filter expression against all dimension items.
    """
    if subset.is_dynamic and subset.filter_expression:
        # Get all items in the dimension
        result = await db.execute(
            select(DimensionItem).where(
                DimensionItem.dimension_id == subset.dimension_id
            )
        )
        all_items = list(result.scalars().all())
        return _evaluate_filter(all_items, subset.filter_expression)
    else:
        # Static: return the explicitly added members
        result = await db.execute(
            select(DimensionItem)
            .join(
                ListSubsetMember,
                ListSubsetMember.dimension_item_id == DimensionItem.id,
            )
            .where(ListSubsetMember.subset_id == subset.id)
        )
        return list(result.scalars().all())


# ── LineItemSubset CRUD ───────────────────────────────────────────────────────

async def create_line_item_subset(
    db: AsyncSession, module_id: uuid.UUID, data: LineItemSubsetCreate
) -> LineItemSubset:
    subset = LineItemSubset(
        module_id=module_id,
        name=data.name,
        description=data.description,
    )
    db.add(subset)
    await db.commit()
    await db.refresh(subset)
    return subset


async def get_line_item_subset_by_id(
    db: AsyncSession, subset_id: uuid.UUID
) -> Optional[LineItemSubset]:
    result = await db.execute(
        select(LineItemSubset).where(LineItemSubset.id == subset_id)
    )
    return result.scalar_one_or_none()


async def list_line_item_subsets_for_module(
    db: AsyncSession, module_id: uuid.UUID
) -> List[LineItemSubset]:
    result = await db.execute(
        select(LineItemSubset).where(LineItemSubset.module_id == module_id)
    )
    return list(result.scalars().all())


async def update_line_item_subset(
    db: AsyncSession, subset: LineItemSubset, data: LineItemSubsetUpdate
) -> LineItemSubset:
    if data.name is not None:
        subset.name = data.name
    if data.description is not None:
        subset.description = data.description
    await db.commit()
    await db.refresh(subset)
    return subset


async def delete_line_item_subset(
    db: AsyncSession, subset: LineItemSubset
) -> None:
    await db.delete(subset)
    await db.commit()


# ── LineItemSubsetMember management ───────────────────────────────────────────

async def add_line_item_subset_members(
    db: AsyncSession,
    subset_id: uuid.UUID,
    line_item_ids: List[uuid.UUID],
) -> List[LineItemSubsetMember]:
    # Get existing member item IDs to avoid duplicates
    result = await db.execute(
        select(LineItemSubsetMember.line_item_id).where(
            LineItemSubsetMember.subset_id == subset_id
        )
    )
    existing_ids = set(result.scalars().all())

    new_members = []
    for item_id in line_item_ids:
        if item_id not in existing_ids:
            member = LineItemSubsetMember(
                subset_id=subset_id,
                line_item_id=item_id,
            )
            db.add(member)
            new_members.append(member)
    await db.commit()
    for m in new_members:
        await db.refresh(m)
    return new_members


async def get_line_item_subset_member_by_id(
    db: AsyncSession, member_id: uuid.UUID
) -> Optional[LineItemSubsetMember]:
    result = await db.execute(
        select(LineItemSubsetMember).where(LineItemSubsetMember.id == member_id)
    )
    return result.scalar_one_or_none()


async def remove_line_item_subset_member(
    db: AsyncSession, member: LineItemSubsetMember
) -> None:
    await db.delete(member)
    await db.commit()


async def resolve_line_item_subset_members(
    db: AsyncSession, subset: LineItemSubset
) -> List[LineItem]:
    """Get resolved line items for a line item subset."""
    result = await db.execute(
        select(LineItem)
        .join(
            LineItemSubsetMember,
            LineItemSubsetMember.line_item_id == LineItem.id,
        )
        .where(LineItemSubsetMember.subset_id == subset.id)
    )
    return list(result.scalars().all())
