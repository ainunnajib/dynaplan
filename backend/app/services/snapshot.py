import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.cell import CellValue
from app.models.dimension import Dimension, DimensionItem
from app.models.module import LineItem, LineItemDimension, Module
from app.models.snapshot import ModelSnapshot
from app.models.version import Version
from app.schemas.snapshot import (
    EntityDiff,
    RestoreResult,
    SnapshotComparison,
)


# ── Internal helpers ────────────────────────────────────────────────────────────

async def _serialize_model(db: AsyncSession, model_id: uuid.UUID) -> Dict[str, Any]:
    """Read all model entities and serialize to a plain dict with string UUIDs."""

    # Dimensions
    dim_result = await db.execute(
        select(Dimension).where(Dimension.model_id == model_id)
    )
    dimensions = dim_result.scalars().all()

    dim_dicts = []
    for d in dimensions:
        dim_dicts.append({
            "id": str(d.id),
            "name": d.name,
            "dimension_type": d.dimension_type.value,
            "max_items": d.max_items,
            "model_id": str(d.model_id),
        })

    # Dimension items — fetch for all dimensions in the model
    dim_ids = [d.id for d in dimensions]
    dim_item_dicts = []
    if dim_ids:
        item_result = await db.execute(
            select(DimensionItem).where(DimensionItem.dimension_id.in_(dim_ids))
        )
        items = item_result.scalars().all()
        for i in items:
            dim_item_dicts.append({
                "id": str(i.id),
                "name": i.name,
                "code": i.code,
                "dimension_id": str(i.dimension_id),
                "parent_id": str(i.parent_id) if i.parent_id else None,
                "sort_order": i.sort_order,
            })

    # Modules
    mod_result = await db.execute(
        select(Module).where(Module.model_id == model_id)
    )
    modules = mod_result.scalars().all()

    mod_dicts = []
    for m in modules:
        mod_dicts.append({
            "id": str(m.id),
            "name": m.name,
            "description": m.description,
            "model_id": str(m.model_id),
        })

    # Line items — fetch for all modules in the model
    mod_ids = [m.id for m in modules]
    li_dicts = []
    line_item_ids = []
    if mod_ids:
        li_result = await db.execute(
            select(LineItem)
            .where(LineItem.module_id.in_(mod_ids))
            .options(selectinload(LineItem.line_item_dimensions))
        )
        line_items = li_result.scalars().all()
        for li in line_items:
            line_item_ids.append(li.id)
            li_dicts.append({
                "id": str(li.id),
                "name": li.name,
                "module_id": str(li.module_id),
                "format": li.format.value,
                "formula": li.formula,
                "summary_method": li.summary_method.value,
                "applies_to_dimensions": [
                    str(dimension_id)
                    for dimension_id in li.applies_to_dimensions
                ],
                "sort_order": li.sort_order,
            })

    # Cell values — fetch for all line items in the model
    cell_dicts = []
    if line_item_ids:
        cell_result = await db.execute(
            select(CellValue).where(CellValue.line_item_id.in_(line_item_ids))
        )
        cells = cell_result.scalars().all()
        for c in cells:
            cell_dicts.append({
                "id": str(c.id),
                "line_item_id": str(c.line_item_id),
                "dimension_key": c.dimension_key,
                "value_number": c.value_number,
                "value_text": c.value_text,
                "value_boolean": c.value_boolean,
            })

    # Versions
    ver_result = await db.execute(
        select(Version).where(Version.model_id == model_id)
    )
    versions = ver_result.scalars().all()

    ver_dicts = []
    for v in versions:
        ver_dicts.append({
            "id": str(v.id),
            "name": v.name,
            "model_id": str(v.model_id),
            "version_type": v.version_type.value,
            "is_default": v.is_default,
            "switchover_period": v.switchover_period,
        })

    return {
        "dimensions": dim_dicts,
        "dimension_items": dim_item_dicts,
        "modules": mod_dicts,
        "line_items": li_dicts,
        "cell_values": cell_dicts,
        "versions": ver_dicts,
    }


def _get_snapshot_metadata(snapshot: ModelSnapshot) -> dict:
    """Return snapshot metadata dict without the large data field."""
    return {
        "id": snapshot.id,
        "model_id": snapshot.model_id,
        "name": snapshot.name,
        "description": snapshot.description,
        "created_by": snapshot.created_by,
        "created_at": snapshot.created_at,
    }


# ── CRUD ────────────────────────────────────────────────────────────────────────

async def create_snapshot(
    db: AsyncSession,
    model_id: uuid.UUID,
    name: str,
    description: Optional[str],
    user_id: uuid.UUID,
) -> ModelSnapshot:
    """Serialize entire model state into JSON and store as a snapshot."""
    data = await _serialize_model(db, model_id)
    snapshot = ModelSnapshot(
        model_id=model_id,
        name=name,
        description=description,
        snapshot_data=data,
        created_by=user_id,
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return snapshot


async def list_snapshots(
    db: AsyncSession, model_id: uuid.UUID
) -> List[ModelSnapshot]:
    """List all snapshots for a model (metadata only — no data blob in ORM response)."""
    result = await db.execute(
        select(ModelSnapshot)
        .where(ModelSnapshot.model_id == model_id)
        .order_by(ModelSnapshot.created_at.desc())
    )
    return list(result.scalars().all())


async def get_snapshot(
    db: AsyncSession, snapshot_id: uuid.UUID
) -> Optional[ModelSnapshot]:
    """Get a snapshot with full data."""
    result = await db.execute(
        select(ModelSnapshot).where(ModelSnapshot.id == snapshot_id)
    )
    return result.scalar_one_or_none()


async def delete_snapshot(db: AsyncSession, snapshot: ModelSnapshot) -> None:
    """Delete a snapshot."""
    await db.delete(snapshot)
    await db.commit()


async def restore_snapshot(
    db: AsyncSession, snapshot_id: uuid.UUID
) -> Optional[RestoreResult]:
    """Restore a model to a snapshot state.

    1. Delete current dimensions, modules, line_items, cells, versions.
    2. Recreate from snapshot_data with new UUIDs.
    3. Return summary of what was restored.
    """
    snapshot = await get_snapshot(db, snapshot_id)
    if snapshot is None:
        return None

    model_id = snapshot.model_id
    data = snapshot.snapshot_data or {}

    # --- Step 1: Delete existing data for the model ---
    # First get existing module IDs to cascade delete cells
    mod_result = await db.execute(
        select(Module.id).where(Module.model_id == model_id)
    )
    existing_module_ids = [row[0] for row in mod_result.all()]

    if existing_module_ids:
        li_result = await db.execute(
            select(LineItem.id).where(LineItem.module_id.in_(existing_module_ids))
        )
        existing_li_ids = [row[0] for row in li_result.all()]
        if existing_li_ids:
            await db.execute(
                delete(CellValue).where(CellValue.line_item_id.in_(existing_li_ids))
            )
        await db.execute(
            delete(LineItem).where(LineItem.module_id.in_(existing_module_ids))
        )
    await db.execute(delete(Module).where(Module.model_id == model_id))
    await db.execute(delete(Dimension).where(Dimension.model_id == model_id))
    await db.execute(delete(Version).where(Version.model_id == model_id))
    await db.flush()

    # --- Step 2: Recreate from snapshot_data with new UUIDs ---
    # Build old→new ID mapping so foreign keys remain consistent
    id_map: Dict[str, uuid.UUID] = {}

    # Restore versions
    restored_versions = 0
    for v in data.get("versions", []):
        new_id = uuid.uuid4()
        id_map[v["id"]] = new_id
        new_version = Version(
            id=new_id,
            name=v["name"],
            model_id=model_id,
            version_type=v["version_type"],
            is_default=v.get("is_default", False),
            switchover_period=v.get("switchover_period"),
        )
        db.add(new_version)
        restored_versions += 1

    # Restore dimensions
    restored_dims = 0
    for d in data.get("dimensions", []):
        new_id = uuid.uuid4()
        id_map[d["id"]] = new_id
        new_dim = Dimension(
            id=new_id,
            name=d["name"],
            dimension_type=d["dimension_type"],
            max_items=d.get("max_items"),
            model_id=model_id,
        )
        db.add(new_dim)
        restored_dims += 1

    await db.flush()

    # Restore dimension items — must handle parent_id remapping
    # Two passes: first create all items without parents, then set parents
    restored_items = 0
    old_item_data = data.get("dimension_items", [])

    for item in old_item_data:
        new_id = uuid.uuid4()
        id_map[item["id"]] = new_id
        old_dim_id = item["dimension_id"]
        new_dim_id = id_map.get(old_dim_id)
        if new_dim_id is None:
            continue
        new_item = DimensionItem(
            id=new_id,
            name=item["name"],
            code=item["code"],
            dimension_id=new_dim_id,
            parent_id=None,  # set in second pass
            sort_order=item.get("sort_order", 0),
        )
        db.add(new_item)
        restored_items += 1

    await db.flush()

    # Second pass: set parent_id
    for item in old_item_data:
        old_parent_id = item.get("parent_id")
        if old_parent_id and old_parent_id in id_map:
            new_item_id = id_map.get(item["id"])
            new_parent_id = id_map.get(old_parent_id)
            if new_item_id and new_parent_id:
                result = await db.execute(
                    select(DimensionItem).where(DimensionItem.id == new_item_id)
                )
                di = result.scalar_one_or_none()
                if di:
                    di.parent_id = new_parent_id

    await db.flush()

    # Restore modules
    restored_modules = 0
    for m in data.get("modules", []):
        new_id = uuid.uuid4()
        id_map[m["id"]] = new_id
        new_mod = Module(
            id=new_id,
            name=m["name"],
            description=m.get("description"),
            model_id=model_id,
        )
        db.add(new_mod)
        restored_modules += 1

    await db.flush()

    # Restore line items
    restored_lis = 0
    restored_li_dimensions = 0
    for li in data.get("line_items", []):
        new_id = uuid.uuid4()
        id_map[li["id"]] = new_id
        old_mod_id = li["module_id"]
        new_mod_id = id_map.get(old_mod_id)
        if new_mod_id is None:
            continue
        new_li = LineItem(
            id=new_id,
            name=li["name"],
            module_id=new_mod_id,
            format=li.get("format", "number"),
            formula=li.get("formula"),
            summary_method=li.get("summary_method", "sum"),
            sort_order=li.get("sort_order", 0),
        )
        db.add(new_li)

        for sort_order, old_dimension_id in enumerate(
            li.get("applies_to_dimensions", [])
        ):
            new_dimension_id = id_map.get(str(old_dimension_id))
            if new_dimension_id is None:
                continue
            db.add(
                LineItemDimension(
                    id=uuid.uuid4(),
                    line_item_id=new_id,
                    dimension_id=new_dimension_id,
                    sort_order=sort_order,
                )
            )
            restored_li_dimensions += 1
        restored_lis += 1

    await db.flush()

    # Restore cell values — remap line_item_id and dimension_key segments
    restored_cells = 0
    for c in data.get("cell_values", []):
        old_li_id = c["line_item_id"]
        new_li_id = id_map.get(old_li_id)
        if new_li_id is None:
            continue

        # Remap any UUID segments in dimension_key
        dimension_key = c["dimension_key"]
        parts = dimension_key.split("|")
        new_parts = []
        for part in parts:
            if part in id_map:
                new_parts.append(str(id_map[part]))
            else:
                new_parts.append(part)
        new_dimension_key = "|".join(new_parts)

        new_cell = CellValue(
            id=uuid.uuid4(),
            line_item_id=new_li_id,
            dimension_key=new_dimension_key,
            value_number=c.get("value_number"),
            value_text=c.get("value_text"),
            value_boolean=c.get("value_boolean"),
        )
        db.add(new_cell)
        restored_cells += 1

    await db.commit()

    return RestoreResult(
        snapshot_id=snapshot_id,
        model_id=model_id,
        entities_restored={
            "dimensions": restored_dims,
            "dimension_items": restored_items,
            "modules": restored_modules,
            "line_items": restored_lis,
            "line_item_dimensions": restored_li_dimensions,
            "cell_values": restored_cells,
            "versions": restored_versions,
        },
    )


def _diff_entity_lists(
    list_a: List[Dict[str, Any]],
    list_b: List[Dict[str, Any]],
    key_field: str = "id",
) -> EntityDiff:
    """Compute added/removed/changed counts between two entity lists.

    Items are keyed by key_field. "Changed" means the id exists in both but
    at least one other field differs.
    """
    map_a: Dict[str, Dict[str, Any]] = {item[key_field]: item for item in list_a}
    map_b: Dict[str, Dict[str, Any]] = {item[key_field]: item for item in list_b}

    ids_a = set(map_a.keys())
    ids_b = set(map_b.keys())

    added = len(ids_b - ids_a)
    removed = len(ids_a - ids_b)

    changed = 0
    for shared_id in ids_a & ids_b:
        item_a = {k: v for k, v in map_a[shared_id].items() if k != key_field}
        item_b = {k: v for k, v in map_b[shared_id].items() if k != key_field}
        if item_a != item_b:
            changed += 1

    return EntityDiff(added=added, removed=removed, changed=changed)


async def compare_snapshots(
    db: AsyncSession,
    snapshot_id_a: uuid.UUID,
    snapshot_id_b: uuid.UUID,
) -> Optional[SnapshotComparison]:
    """Compare two snapshots and return diff counts by entity type."""
    snapshot_a = await get_snapshot(db, snapshot_id_a)
    snapshot_b = await get_snapshot(db, snapshot_id_b)

    if snapshot_a is None or snapshot_b is None:
        return None

    data_a = snapshot_a.snapshot_data or {}
    data_b = snapshot_b.snapshot_data or {}

    dims_diff = _diff_entity_lists(
        data_a.get("dimensions", []),
        data_b.get("dimensions", []),
    )
    items_diff = _diff_entity_lists(
        data_a.get("dimension_items", []),
        data_b.get("dimension_items", []),
    )
    modules_diff = _diff_entity_lists(
        data_a.get("modules", []),
        data_b.get("modules", []),
    )
    li_diff = _diff_entity_lists(
        data_a.get("line_items", []),
        data_b.get("line_items", []),
    )
    cells_diff = _diff_entity_lists(
        data_a.get("cell_values", []),
        data_b.get("cell_values", []),
    )
    versions_diff = _diff_entity_lists(
        data_a.get("versions", []),
        data_b.get("versions", []),
    )

    total_changes = sum([
        dims_diff.added + dims_diff.removed + dims_diff.changed,
        items_diff.added + items_diff.removed + items_diff.changed,
        modules_diff.added + modules_diff.removed + modules_diff.changed,
        li_diff.added + li_diff.removed + li_diff.changed,
        cells_diff.added + cells_diff.removed + cells_diff.changed,
        versions_diff.added + versions_diff.removed + versions_diff.changed,
    ])

    if total_changes == 0:
        summary = "No differences found between snapshots."
    else:
        parts = []
        if dims_diff.added + dims_diff.removed + dims_diff.changed > 0:
            parts.append(f"dimensions: +{dims_diff.added}/-{dims_diff.removed}/~{dims_diff.changed}")
        if items_diff.added + items_diff.removed + items_diff.changed > 0:
            parts.append(f"dimension_items: +{items_diff.added}/-{items_diff.removed}/~{items_diff.changed}")
        if modules_diff.added + modules_diff.removed + modules_diff.changed > 0:
            parts.append(f"modules: +{modules_diff.added}/-{modules_diff.removed}/~{modules_diff.changed}")
        if li_diff.added + li_diff.removed + li_diff.changed > 0:
            parts.append(f"line_items: +{li_diff.added}/-{li_diff.removed}/~{li_diff.changed}")
        if cells_diff.added + cells_diff.removed + cells_diff.changed > 0:
            parts.append(f"cell_values: +{cells_diff.added}/-{cells_diff.removed}/~{cells_diff.changed}")
        if versions_diff.added + versions_diff.removed + versions_diff.changed > 0:
            parts.append(f"versions: +{versions_diff.added}/-{versions_diff.removed}/~{versions_diff.changed}")
        summary = f"{total_changes} total changes — " + ", ".join(parts)

    return SnapshotComparison(
        snapshot_id_a=snapshot_id_a,
        snapshot_id_b=snapshot_id_b,
        snapshot_name_a=snapshot_a.name,
        snapshot_name_b=snapshot_b.name,
        dimensions=dims_diff,
        dimension_items=items_diff,
        modules=modules_diff,
        line_items=li_diff,
        cell_values=cells_diff,
        versions=versions_diff,
        summary=summary,
    )
