import asyncio
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.engine import rust_bridge
from app.models.cell import CellValue
from app.models.composite_dimension import CompositeDimensionMember
from app.models.dimension import DimensionItem
from app.models.module import LineItem, Module
from app.schemas.cell import CellRead, CellWrite
from app.services.cell_versioning import (
    ensure_dimension_members_include_version,
    resolve_cell_version_context,
)
from app.services.composite_dimension import (
    ensure_composite_intersection_member,
    get_composite_dimensions_by_dimension_ids,
)
from app.services.model_encryption import (
    encrypt_cell_components_with_key,
    get_active_model_encryption_key,
    get_cell_scalar_value,
)
from app.services.workspace_quota import enforce_cell_write_quota


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


async def _cell_to_read(
    db: AsyncSession,
    cell: CellValue,
    key_record_cache: Optional[Dict[uuid.UUID, Any]] = None,
    data_key_cache: Optional[Dict[uuid.UUID, str]] = None,
) -> CellRead:
    """Convert a CellValue ORM object to a CellRead schema."""
    value, value_type = await get_cell_scalar_value(
        db,
        cell,
        key_record_cache=key_record_cache,
        data_key_cache=data_key_cache,
    )

    dimension_members: List[uuid.UUID] = []
    if cell.dimension_key:
        for part in cell.dimension_key.split("|"):
            if not part:
                continue
            try:
                dimension_members.append(uuid.UUID(part))
            except ValueError:
                continue

    return CellRead(
        line_item_id=cell.line_item_id,
        dimension_members=dimension_members,
        version_id=cell.version_id,
        dimension_key=cell.dimension_key,
        value=value,
        value_type=value_type,
    )


async def _cell_to_engine_value(
    db: AsyncSession,
    cell: CellValue,
    key_record_cache: Optional[Dict[uuid.UUID, Any]] = None,
    data_key_cache: Optional[Dict[uuid.UUID, str]] = None,
) -> Any:
    """Convert CellValue row data to a Python scalar for the engine bridge."""
    value, _value_type = await get_cell_scalar_value(
        db,
        cell,
        key_record_cache=key_record_cache,
        data_key_cache=data_key_cache,
    )
    return value


async def _get_model_ids_for_line_items(
    db: AsyncSession,
    line_item_ids: List[uuid.UUID],
) -> Dict[uuid.UUID, uuid.UUID]:
    """Map line_item_id -> model_id for a set of line items."""
    if not line_item_ids:
        return {}

    result = await db.execute(
        select(LineItem.id, Module.model_id)
        .join(Module, Module.id == LineItem.module_id)
        .where(LineItem.id.in_(line_item_ids))
    )
    return {row[0]: row[1] for row in result.all()}


async def _sync_engine_after_commit(
    db: AsyncSession,
    cells: List[CellValue],
) -> None:
    """Best-effort mirror of committed writes into the selected calc engine."""
    if not cells:
        return

    unique_line_items = list(dict.fromkeys(cell.line_item_id for cell in cells))
    model_ids_by_line_item = await _get_model_ids_for_line_items(db, unique_line_items)
    key_record_cache: Dict[uuid.UUID, Any] = {}
    data_key_cache: Dict[uuid.UUID, str] = {}

    writes_by_model: Dict[uuid.UUID, List[Dict[str, Any]]] = {}
    for cell in cells:
        model_id = model_ids_by_line_item.get(cell.line_item_id)
        if model_id is None:
            continue
        scalar_value = await _cell_to_engine_value(
            db,
            cell,
            key_record_cache=key_record_cache,
            data_key_cache=data_key_cache,
        )
        writes_by_model.setdefault(model_id, []).append(
            {
                "line_item_id": str(cell.line_item_id),
                "dimension_key": cell.dimension_key,
                "value": scalar_value,
            }
        )

    for model_id, writes in writes_by_model.items():
        handle = rust_bridge.get_or_create_model_handle(model_id)
        rust_bridge.write_cells_bulk(handle, writes)


async def _get_line_item_with_dimensions(
    db: AsyncSession,
    line_item_id: uuid.UUID,
) -> Optional[LineItem]:
    result = await db.execute(
        select(LineItem)
        .where(LineItem.id == line_item_id)
        .options(
            selectinload(LineItem.line_item_dimensions),
            selectinload(LineItem.module),
        )
    )
    return result.scalar_one_or_none()


async def _normalize_dimension_members_for_composites(
    db: AsyncSession,
    line_item: Optional[LineItem],
    dimension_members: List[uuid.UUID],
    create_missing_composites: bool = True,
) -> List[uuid.UUID]:
    unique_members = list(dict.fromkeys(dimension_members))
    if line_item is None:
        return unique_members
    if not line_item.line_item_dimensions:
        return unique_members

    applies_to_dimension_ids = [
        link.dimension_id for link in line_item.line_item_dimensions
    ]
    composites_by_dimension = await get_composite_dimensions_by_dimension_ids(
        db,
        applies_to_dimension_ids,
    )
    if not composites_by_dimension:
        return unique_members

    member_result = await db.execute(
        select(DimensionItem).where(DimensionItem.id.in_(unique_members))
    )
    dimension_members_rows = list(member_result.scalars().all())
    member_by_id = {member.id: member for member in dimension_members_rows}

    consumed_ids = set()
    normalized_members: List[uuid.UUID] = []

    for link in line_item.line_item_dimensions:
        composite = composites_by_dimension.get(link.dimension_id)
        if composite is None:
            continue

        direct_member_id = next(
            (
                member_id
                for member_id in unique_members
                if member_id in member_by_id
                and member_by_id[member_id].dimension_id == composite.dimension_id
            ),
            None,
        )
        if direct_member_id is not None:
            consumed_ids.add(direct_member_id)
            normalized_members.append(direct_member_id)
            continue

        ordered_source_dimension_ids = [
            source.source_dimension_id
            for source in sorted(
                composite.source_dimensions,
                key=lambda source: source.sort_order,
            )
        ]
        source_member_ids: List[uuid.UUID] = []
        is_complete_source_set = True
        for source_dimension_id in ordered_source_dimension_ids:
            matching_members = [
                member_id
                for member_id in unique_members
                if member_id not in consumed_ids
                and member_id in member_by_id
                and member_by_id[member_id].dimension_id == source_dimension_id
            ]
            if len(matching_members) != 1:
                is_complete_source_set = False
                break
            source_member_ids.append(matching_members[0])

        if not is_complete_source_set:
            continue

        if create_missing_composites:
            composite_member = await ensure_composite_intersection_member(
                db,
                composite_dimension=composite,
                source_member_ids=source_member_ids,
            )
            normalized_members.append(composite_member.dimension_item_id)
            consumed_ids.update(source_member_ids)
            continue

        source_member_key = "|".join(str(member_id) for member_id in source_member_ids)
        existing_result = await db.execute(
            select(CompositeDimensionMember.dimension_item_id).where(
                CompositeDimensionMember.composite_dimension_id == composite.id,
                CompositeDimensionMember.source_member_key == source_member_key,
            )
        )
        existing_dimension_item_id = existing_result.scalar_one_or_none()
        if existing_dimension_item_id is None:
            continue

        normalized_members.append(existing_dimension_item_id)
        consumed_ids.update(source_member_ids)

    for member_id in unique_members:
        if member_id in consumed_ids:
            continue
        normalized_members.append(member_id)

    return list(dict.fromkeys(normalized_members))


async def _resolve_cell_dimension_context(
    db: AsyncSession,
    line_item_id: uuid.UUID,
    dimension_members: List[uuid.UUID],
    explicit_version_id: Optional[uuid.UUID],
    line_item: Optional[LineItem] = None,
    create_missing_composites: bool = True,
) -> Tuple[Optional[uuid.UUID], List[uuid.UUID], List[uuid.UUID]]:
    resolved_version_id, _key_members, validation_members = await resolve_cell_version_context(
        db=db,
        line_item_id=line_item_id,
        dimension_members=dimension_members,
        explicit_version_id=explicit_version_id,
    )

    normalized_validation_members = await _normalize_dimension_members_for_composites(
        db=db,
        line_item=line_item,
        dimension_members=validation_members,
        create_missing_composites=create_missing_composites,
    )
    key_dimension_members = ensure_dimension_members_include_version(
        normalized_validation_members,
        resolved_version_id,
    )
    return resolved_version_id, key_dimension_members, normalized_validation_members


async def _validate_cell_dimensions(
    db: AsyncSession,
    line_item_id: uuid.UUID,
    dimension_members: List[uuid.UUID],
    line_item: Optional[LineItem] = None,
) -> None:
    """Validate dimension_members against the line item's applies-to dimensions."""
    if line_item is None:
        line_item = await _get_line_item_with_dimensions(db, line_item_id)
    if line_item is None:
        # Preserve historical behavior: writes to unknown line-item IDs are
        # still accepted by API key flows and scoped tooling.
        return

    applies_to_dimensions = [
        link.dimension_id for link in line_item.line_item_dimensions
    ]
    if not applies_to_dimensions:
        return

    unique_members = list(dict.fromkeys(dimension_members))
    if len(unique_members) != len(applies_to_dimensions):
        raise ValueError(
            "Dimension member count must match line item's applies-to dimensions"
        )

    member_result = await db.execute(
        select(DimensionItem.id, DimensionItem.dimension_id).where(
            DimensionItem.id.in_(unique_members)
        )
    )
    member_rows = member_result.all()
    if len(member_rows) != len(unique_members):
        raise ValueError("One or more dimension members do not exist")

    member_dimension_ids = [row[1] for row in member_rows]
    if len(set(member_dimension_ids)) != len(member_dimension_ids):
        raise ValueError("Dimension members must come from distinct dimensions")

    if set(member_dimension_ids) != set(applies_to_dimensions):
        raise ValueError(
            "Dimension members do not match the line item's applies-to dimensions"
        )


# ── Write operations ───────────────────────────────────────────────────────────

async def _assign_cell_storage_values(
    db: AsyncSession,
    cell: CellValue,
    model_id: Optional[uuid.UUID],
    value_number: Optional[float],
    value_text: Optional[str],
    value_boolean: Optional[bool],
) -> None:
    if model_id is None:
        cell.value_number = value_number
        cell.value_text = value_text
        cell.value_boolean = value_boolean
        cell.value_encrypted = None
        cell.encryption_key_id = None
        return

    model_key = await get_active_model_encryption_key(db, model_id)
    if model_key is None:
        cell.value_number = value_number
        cell.value_text = value_text
        cell.value_boolean = value_boolean
        cell.value_encrypted = None
        cell.encryption_key_id = None
        return

    encrypted_payload = await encrypt_cell_components_with_key(
        db,
        model_key=model_key,
        value_number=value_number,
        value_text=value_text,
        value_boolean=value_boolean,
    )
    cell.value_number = None
    cell.value_text = None
    cell.value_boolean = None
    cell.value_encrypted = encrypted_payload
    cell.encryption_key_id = model_key.id

async def _upsert_cell_no_commit(
    db: AsyncSession,
    line_item_id: uuid.UUID,
    dimension_members: List[uuid.UUID],
    version_id: Optional[uuid.UUID],
    value: Any,
) -> CellValue:
    """Upsert a single cell without committing the current transaction."""
    line_item = await _get_line_item_with_dimensions(db, line_item_id)
    line_item_model_id: Optional[uuid.UUID] = None
    if line_item is not None and line_item.module is not None:
        line_item_model_id = line_item.module.model_id
    resolved_version_id, key_dimension_members, validation_dimension_members = await _resolve_cell_dimension_context(
        db=db,
        line_item_id=line_item_id,
        dimension_members=dimension_members,
        explicit_version_id=version_id,
        line_item=line_item,
    )

    await _validate_cell_dimensions(
        db,
        line_item_id,
        validation_dimension_members,
        line_item=line_item,
    )

    dimension_key = make_dimension_key(key_dimension_members)
    value_number, value_text, value_boolean, _value_type = _extract_value_and_type(value)

    result = await db.execute(
        select(CellValue).where(
            CellValue.line_item_id == line_item_id,
            CellValue.dimension_key == dimension_key,
        )
    )
    existing = result.scalar_one_or_none()

    await enforce_cell_write_quota(
        db=db,
        line_item_id=line_item_id,
        dimension_key=dimension_key,
        value_number=value_number,
        value_text=value_text,
        value_boolean=value_boolean,
        existing_cell=existing,
    )

    if existing is not None:
        await _assign_cell_storage_values(
            db=db,
            cell=existing,
            model_id=line_item_model_id,
            value_number=value_number,
            value_text=value_text,
            value_boolean=value_boolean,
        )
        if resolved_version_id is not None and existing.version_id is None:
            existing.version_id = resolved_version_id
        return existing

    cell = CellValue(
        line_item_id=line_item_id,
        version_id=resolved_version_id,
        dimension_key=dimension_key,
    )
    await _assign_cell_storage_values(
        db=db,
        cell=cell,
        model_id=line_item_model_id,
        value_number=value_number,
        value_text=value_text,
        value_boolean=value_boolean,
    )
    db.add(cell)
    return cell


async def write_cell(
    db: AsyncSession,
    line_item_id: uuid.UUID,
    dimension_members: List[uuid.UUID],
    version_id: Optional[uuid.UUID],
    value: Any,
) -> CellRead:
    """Upsert a single cell value."""
    value_number, value_text, value_boolean, _value_type = _extract_value_and_type(value)
    line_item = await _get_line_item_with_dimensions(db, line_item_id)
    line_item_model_id: Optional[uuid.UUID] = None
    if line_item is not None and line_item.module is not None:
        line_item_model_id = line_item.module.model_id

    cell = await _upsert_cell_no_commit(
        db=db,
        line_item_id=line_item_id,
        dimension_members=dimension_members,
        version_id=version_id,
        value=value,
    )
    dimension_key = cell.dimension_key
    resolved_version_id = cell.version_id

    try:
        await db.commit()
    except IntegrityError:
        # Concurrent insert race on (line_item_id, dimension_key):
        # reload the row and apply this write as an update.
        await db.rollback()
        for _ in range(3):
            result = await db.execute(
                select(CellValue).where(
                    CellValue.line_item_id == line_item_id,
                    CellValue.dimension_key == dimension_key,
                )
            )
            existing = result.scalar_one_or_none()
            if existing is not None:
                await _assign_cell_storage_values(
                    db=db,
                    cell=existing,
                    model_id=line_item_model_id,
                    value_number=value_number,
                    value_text=value_text,
                    value_boolean=value_boolean,
                )
                if resolved_version_id is not None and existing.version_id is None:
                    existing.version_id = resolved_version_id
                try:
                    await db.commit()
                except Exception:
                    await db.rollback()
                    raise
                await db.refresh(existing)
                try:
                    await _sync_engine_after_commit(db, [existing])
                except Exception:
                    pass
                return await _cell_to_read(db, existing)
            await asyncio.sleep(0)

        # If the winner row is still not visible, retry once from scratch.
        cell = await _upsert_cell_no_commit(
            db=db,
            line_item_id=line_item_id,
            dimension_members=dimension_members,
            version_id=version_id,
            value=value,
        )
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        await db.refresh(cell)
        try:
            await _sync_engine_after_commit(db, [cell])
        except Exception:
            pass
        return await _cell_to_read(db, cell)
    except Exception:
        await db.rollback()
        raise

    await db.refresh(cell)
    try:
        await _sync_engine_after_commit(db, [cell])
    except Exception:
        pass
    return await _cell_to_read(db, cell)


async def write_cells_bulk(
    db: AsyncSession,
    cells: List[CellWrite],
) -> List[CellRead]:
    """Bulk upsert multiple cells in a single transaction."""
    upserted_cells: List[CellValue] = []

    try:
        for cell_write in cells:
            cell = await _upsert_cell_no_commit(
                db=db,
                line_item_id=cell_write.line_item_id,
                dimension_members=cell_write.dimension_members,
                version_id=cell_write.version_id,
                value=cell_write.value,
            )
            upserted_cells.append(cell)
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    results: List[CellRead] = []
    key_record_cache: Dict[uuid.UUID, Any] = {}
    data_key_cache: Dict[uuid.UUID, str] = {}
    for cell in upserted_cells:
        await db.refresh(cell)
        results.append(
            await _cell_to_read(
                db,
                cell,
                key_record_cache=key_record_cache,
                data_key_cache=data_key_cache,
            )
        )

    try:
        await _sync_engine_after_commit(db, upserted_cells)
    except Exception:
        pass

    return results


# ── Read operations ────────────────────────────────────────────────────────────

async def read_cell(
    db: AsyncSession,
    line_item_id: uuid.UUID,
    dimension_members: List[uuid.UUID],
    version_id: Optional[uuid.UUID] = None,
) -> Optional[CellRead]:
    """Read a single cell value."""
    line_item = await _get_line_item_with_dimensions(db, line_item_id)
    _resolved_version_id, key_dimension_members, _validation_dimension_members = await _resolve_cell_dimension_context(
        db=db,
        line_item_id=line_item_id,
        dimension_members=dimension_members,
        explicit_version_id=version_id,
        line_item=line_item,
        create_missing_composites=False,
    )
    dimension_key = make_dimension_key(key_dimension_members)
    result = await db.execute(
        select(CellValue).where(
            CellValue.line_item_id == line_item_id,
            CellValue.dimension_key == dimension_key,
        )
    )
    cell = result.scalar_one_or_none()
    if cell is None:
        return None
    return await _cell_to_read(db, cell)


async def read_cells_for_line_item(
    db: AsyncSession,
    line_item_id: uuid.UUID,
    version_id: Optional[uuid.UUID] = None,
    dimension_filters: Optional[Dict[str, List[uuid.UUID]]] = None,
) -> List[CellRead]:
    """Read all cells for a line item, optionally filtered by dimension members.

    dimension_filters maps dimension_item_id (as string) to a list of acceptable
    dimension_item UUIDs. A cell is included only if its dimension_key contains
    at least one member from each filter entry.
    """
    stmt = select(CellValue).where(CellValue.line_item_id == line_item_id)
    if version_id is not None:
        version_key = str(version_id)
        stmt = stmt.where(
            or_(
                CellValue.version_id == version_id,
                CellValue.dimension_key.contains(version_key),
            )
        )

    result = await db.execute(stmt)
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

    key_record_cache: Dict[uuid.UUID, Any] = {}
    data_key_cache: Dict[uuid.UUID, str] = {}
    results: List[CellRead] = []
    for cell in cells:
        results.append(
            await _cell_to_read(
                db,
                cell,
                key_record_cache=key_record_cache,
                data_key_cache=data_key_cache,
            )
        )
    return results


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
