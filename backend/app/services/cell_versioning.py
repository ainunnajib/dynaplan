import uuid
from typing import Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cell import CellValue
from app.models.module import LineItem, Module
from app.models.version import Version


def _split_dimension_key(dimension_key: str) -> List[str]:
    if not dimension_key:
        return []
    return [part for part in dimension_key.split("|") if part]


def remove_versions_from_dimension_key(
    dimension_key: str,
    version_ids: Sequence[uuid.UUID],
) -> str:
    version_parts = {str(version_id) for version_id in version_ids}
    if not version_parts:
        return dimension_key
    base_parts = [
        part for part in _split_dimension_key(dimension_key)
        if part not in version_parts
    ]
    return "|".join(sorted(base_parts))


def ensure_dimension_members_include_version(
    dimension_members: List[uuid.UUID],
    version_id: Optional[uuid.UUID],
) -> List[uuid.UUID]:
    if version_id is None:
        return list(dimension_members)

    combined = list(dimension_members)
    if version_id not in combined:
        combined.append(version_id)
    return combined


async def _get_model_id_for_line_item(
    db: AsyncSession,
    line_item_id: uuid.UUID,
) -> Optional[uuid.UUID]:
    result = await db.execute(
        select(Module.model_id)
        .join(LineItem, LineItem.module_id == Module.id)
        .where(LineItem.id == line_item_id)
    )
    row = result.first()
    if row is None:
        return None
    return row[0]


async def _get_version_ids_for_model(
    db: AsyncSession,
    model_id: uuid.UUID,
) -> Set[uuid.UUID]:
    result = await db.execute(
        select(Version.id).where(Version.model_id == model_id)
    )
    return set(result.scalars().all())


async def resolve_cell_version_context(
    db: AsyncSession,
    line_item_id: uuid.UUID,
    dimension_members: List[uuid.UUID],
    explicit_version_id: Optional[uuid.UUID] = None,
) -> Tuple[Optional[uuid.UUID], List[uuid.UUID], List[uuid.UUID]]:
    """Resolve version context for a cell write.

    Returns:
    - resolved version_id
    - key_dimension_members (always includes version member if version is resolved)
    - validation_dimension_members (version member excluded)
    """
    members = list(dict.fromkeys(dimension_members))

    model_id = await _get_model_id_for_line_item(db, line_item_id)
    if model_id is None:
        key_members = ensure_dimension_members_include_version(members, explicit_version_id)
        validation_members = [member for member in members if member != explicit_version_id]
        return explicit_version_id, key_members, validation_members

    model_version_ids = await _get_version_ids_for_model(db, model_id)
    member_version_ids = [
        member for member in members
        if member in model_version_ids
    ]

    resolved_version_id = explicit_version_id
    if explicit_version_id is not None:
        if explicit_version_id not in model_version_ids:
            raise ValueError("version_id does not belong to the line item's model")
        conflicting = [
            version_id for version_id in member_version_ids
            if version_id != explicit_version_id
        ]
        if conflicting:
            raise ValueError("dimension_members contains a conflicting version member")
    else:
        if len(member_version_ids) > 1:
            raise ValueError("dimension_members contains multiple version members")
        if len(member_version_ids) == 1:
            resolved_version_id = member_version_ids[0]

    validation_members = [
        member for member in members
        if member not in model_version_ids
    ]
    key_members = ensure_dimension_members_include_version(validation_members, resolved_version_id)
    return resolved_version_id, key_members, validation_members


async def migrate_legacy_cell_versions(
    db: AsyncSession,
    model_id: Optional[uuid.UUID] = None,
    line_item_ids: Optional[List[uuid.UUID]] = None,
) -> int:
    """Backfill CellValue.version_id from legacy dimension_key-embedded UUIDs."""
    stmt = (
        select(CellValue, Module.model_id)
        .join(LineItem, LineItem.id == CellValue.line_item_id)
        .join(Module, Module.id == LineItem.module_id)
        .where(CellValue.version_id.is_(None))
    )
    if model_id is not None:
        stmt = stmt.where(Module.model_id == model_id)
    if line_item_ids:
        stmt = stmt.where(CellValue.line_item_id.in_(line_item_ids))

    result = await db.execute(stmt)
    rows = result.all()
    if not rows:
        return 0

    model_ids = {row[1] for row in rows}
    versions_result = await db.execute(
        select(Version.id, Version.model_id).where(Version.model_id.in_(model_ids))
    )
    version_rows = versions_result.all()

    versions_by_model: Dict[uuid.UUID, Set[str]] = {}
    for version_id, version_model_id in version_rows:
        versions_by_model.setdefault(version_model_id, set()).add(str(version_id))

    updated = 0
    for cell, cell_model_id in rows:
        model_versions = versions_by_model.get(cell_model_id, set())
        if not model_versions:
            continue

        key_parts = set(_split_dimension_key(cell.dimension_key))
        matched = [
            version_part for version_part in model_versions
            if version_part in key_parts
        ]
        if len(matched) != 1:
            continue

        cell.version_id = uuid.UUID(matched[0])
        updated += 1

    if updated:
        await db.flush()

    return updated
