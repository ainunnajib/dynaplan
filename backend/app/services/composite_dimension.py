import uuid
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.composite_dimension import (
    CompositeDimension,
    CompositeDimensionMember,
    CompositeDimensionSource,
)
from app.models.dimension import Dimension, DimensionItem, DimensionType
from app.schemas.composite_dimension import CompositeDimensionCreate
from app.services.workspace_quota import enforce_dimension_creation_quota


class CompositeDimensionValidationError(ValueError):
    """Raised when composite-dimension payloads fail validation."""


def _dedupe_ids(ids: List[uuid.UUID]) -> List[uuid.UUID]:
    seen = set()
    deduped: List[uuid.UUID] = []
    for value in ids:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def parse_source_member_key(source_member_key: str) -> List[uuid.UUID]:
    member_ids: List[uuid.UUID] = []
    for part in source_member_key.split("|"):
        if not part:
            continue
        try:
            member_ids.append(uuid.UUID(part))
        except ValueError:
            continue
    return member_ids


async def create_composite_dimension(
    db: AsyncSession,
    model_id: uuid.UUID,
    data: CompositeDimensionCreate,
) -> CompositeDimension:
    source_dimension_ids = _dedupe_ids(data.source_dimension_ids)
    if len(source_dimension_ids) < 2:
        raise CompositeDimensionValidationError(
            "Composite dimensions require at least 2 distinct source dimensions"
        )

    source_result = await db.execute(
        select(Dimension).where(Dimension.id.in_(source_dimension_ids))
    )
    source_dimensions = list(source_result.scalars().all())
    if len(source_dimensions) != len(source_dimension_ids):
        raise CompositeDimensionValidationError(
            "One or more source dimensions do not exist"
        )

    source_by_id = {dimension.id: dimension for dimension in source_dimensions}
    for source_dimension_id in source_dimension_ids:
        source_dimension = source_by_id[source_dimension_id]
        if source_dimension.model_id != model_id:
            raise CompositeDimensionValidationError(
                "All source dimensions must belong to the same model"
            )
        if source_dimension.dimension_type == DimensionType.composite:
            raise CompositeDimensionValidationError(
                "Composite dimensions cannot use other composite dimensions as sources"
            )

    await enforce_dimension_creation_quota(db, model_id)

    dimension = Dimension(
        name=data.name,
        dimension_type=DimensionType.composite,
        max_items=None,
        model_id=model_id,
    )
    db.add(dimension)
    await db.flush()

    composite_dimension = CompositeDimension(
        dimension_id=dimension.id,
        model_id=model_id,
    )
    db.add(composite_dimension)
    await db.flush()

    for sort_order, source_dimension_id in enumerate(source_dimension_ids):
        db.add(
            CompositeDimensionSource(
                composite_dimension_id=composite_dimension.id,
                source_dimension_id=source_dimension_id,
                sort_order=sort_order,
            )
        )

    await db.commit()
    created = await get_composite_dimension_by_id(db, composite_dimension.id)
    if created is None:
        raise CompositeDimensionValidationError("Failed to create composite dimension")
    return created


async def get_composite_dimension_by_id(
    db: AsyncSession,
    composite_dimension_id: uuid.UUID,
) -> Optional[CompositeDimension]:
    result = await db.execute(
        select(CompositeDimension)
        .where(CompositeDimension.id == composite_dimension_id)
        .options(
            selectinload(CompositeDimension.dimension),
            selectinload(CompositeDimension.source_dimensions),
        )
    )
    return result.scalar_one_or_none()


async def get_composite_dimension_by_dimension_id(
    db: AsyncSession,
    dimension_id: uuid.UUID,
) -> Optional[CompositeDimension]:
    result = await db.execute(
        select(CompositeDimension)
        .where(CompositeDimension.dimension_id == dimension_id)
        .options(selectinload(CompositeDimension.source_dimensions))
    )
    return result.scalar_one_or_none()


async def get_composite_dimensions_by_dimension_ids(
    db: AsyncSession,
    dimension_ids: List[uuid.UUID],
) -> Dict[uuid.UUID, CompositeDimension]:
    if not dimension_ids:
        return {}

    result = await db.execute(
        select(CompositeDimension)
        .where(CompositeDimension.dimension_id.in_(dimension_ids))
        .options(selectinload(CompositeDimension.source_dimensions))
    )
    rows = list(result.scalars().all())
    return {row.dimension_id: row for row in rows}


async def list_composite_dimensions_for_model(
    db: AsyncSession,
    model_id: uuid.UUID,
) -> List[CompositeDimension]:
    result = await db.execute(
        select(CompositeDimension)
        .where(CompositeDimension.model_id == model_id)
        .options(
            selectinload(CompositeDimension.dimension),
            selectinload(CompositeDimension.source_dimensions),
        )
        .order_by(CompositeDimension.created_at)
    )
    return list(result.scalars().all())


async def delete_composite_dimension(
    db: AsyncSession,
    composite_dimension: CompositeDimension,
) -> None:
    dimension = composite_dimension.dimension
    if dimension is not None:
        await db.delete(dimension)
    else:
        await db.delete(composite_dimension)
    await db.commit()


async def ensure_composite_intersection_member(
    db: AsyncSession,
    composite_dimension: CompositeDimension,
    source_member_ids: List[uuid.UUID],
) -> CompositeDimensionMember:
    source_dimension_ids = [
        source.source_dimension_id
        for source in sorted(
            composite_dimension.source_dimensions,
            key=lambda source: source.sort_order,
        )
    ]
    if len(source_dimension_ids) < 2:
        raise CompositeDimensionValidationError(
            "Composite dimension must reference at least 2 source dimensions"
        )

    unique_member_ids = _dedupe_ids(source_member_ids)
    if len(unique_member_ids) != len(source_dimension_ids):
        raise CompositeDimensionValidationError(
            "source_member_ids must provide exactly one member per source dimension"
        )

    member_result = await db.execute(
        select(DimensionItem).where(DimensionItem.id.in_(unique_member_ids))
    )
    member_rows = list(member_result.scalars().all())
    if len(member_rows) != len(unique_member_ids):
        raise CompositeDimensionValidationError(
            "One or more source members do not exist"
        )

    member_by_dimension: Dict[uuid.UUID, DimensionItem] = {}
    for member in member_rows:
        if member.dimension_id in member_by_dimension:
            raise CompositeDimensionValidationError(
                "source_member_ids must come from distinct source dimensions"
            )
        member_by_dimension[member.dimension_id] = member

    if set(member_by_dimension.keys()) != set(source_dimension_ids):
        raise CompositeDimensionValidationError(
            "source_member_ids do not match the composite dimension's source dimensions"
        )

    ordered_members = [
        member_by_dimension[dimension_id]
        for dimension_id in source_dimension_ids
    ]
    source_member_key = "|".join(str(member.id) for member in ordered_members)

    existing_result = await db.execute(
        select(CompositeDimensionMember)
        .where(
            CompositeDimensionMember.composite_dimension_id == composite_dimension.id,
            CompositeDimensionMember.source_member_key == source_member_key,
        )
        .options(selectinload(CompositeDimensionMember.dimension_item))
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        return existing

    item_count_result = await db.execute(
        select(func.count())
        .select_from(DimensionItem)
        .where(DimensionItem.dimension_id == composite_dimension.dimension_id)
    )
    next_sort_order = int(item_count_result.scalar_one() or 0)
    name = " × ".join(member.name for member in ordered_members)
    code = "|".join(member.code for member in ordered_members)

    dimension_item = DimensionItem(
        name=name,
        code=code,
        dimension_id=composite_dimension.dimension_id,
        parent_id=None,
        sort_order=next_sort_order,
    )
    db.add(dimension_item)
    await db.flush()

    composite_member = CompositeDimensionMember(
        composite_dimension_id=composite_dimension.id,
        dimension_item_id=dimension_item.id,
        source_member_key=source_member_key,
    )
    db.add(composite_member)
    await db.flush()
    await db.refresh(composite_member)
    return composite_member


async def list_composite_intersection_members(
    db: AsyncSession,
    composite_dimension_id: uuid.UUID,
) -> List[CompositeDimensionMember]:
    result = await db.execute(
        select(CompositeDimensionMember)
        .join(DimensionItem, DimensionItem.id == CompositeDimensionMember.dimension_item_id)
        .where(CompositeDimensionMember.composite_dimension_id == composite_dimension_id)
        .options(selectinload(CompositeDimensionMember.dimension_item))
        .order_by(DimensionItem.sort_order, DimensionItem.name)
    )
    return list(result.scalars().all())
