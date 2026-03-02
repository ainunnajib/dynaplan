import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.alm import (
    ALMEnvironment,
    EnvironmentType,
    PromotionRecord,
    PromotionStatus,
    RevisionTag,
)
from app.models.cell import CellValue
from app.models.dimension import Dimension, DimensionItem, DimensionType
from app.models.module import LineItem, LineItemDimension, LineItemFormat, Module, SummaryMethod
from app.schemas.alm import (
    EnvironmentCreate,
    EnvironmentUpdate,
    LockRequest,
    PromotionCreate,
    RevisionTagCreate,
    TagComparisonResponse,
)


SNAPSHOT_KEYS = [
    "dimensions",
    "dimension_items",
    "modules",
    "line_items",
    "cell_values",
]


# ---------------------------------------------------------------------------
# Snapshot helpers
# ---------------------------------------------------------------------------


def _coerce_snapshot_entries(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _ensure_snapshot_data(snapshot: Optional[dict]) -> Dict[str, List[Dict[str, Any]]]:
    data = snapshot if isinstance(snapshot, dict) else {}
    normalized: Dict[str, List[Dict[str, Any]]] = {}
    for key in SNAPSHOT_KEYS:
        normalized[key] = _coerce_snapshot_entries(data.get(key))
    return normalized


def _structural_snapshot(snapshot: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
    return {
        "dimensions": [dict(entry) for entry in snapshot.get("dimensions", [])],
        "dimension_items": [dict(entry) for entry in snapshot.get("dimension_items", [])],
        "modules": [dict(entry) for entry in snapshot.get("modules", [])],
        "line_items": [dict(entry) for entry in snapshot.get("line_items", [])],
    }


def _snapshot_signature(snapshot: Dict[str, Any]) -> str:
    payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def _serialize_model_state(
    db: AsyncSession,
    model_id: uuid.UUID,
) -> Dict[str, List[Dict[str, Any]]]:
    dim_result = await db.execute(
        select(Dimension)
        .where(Dimension.model_id == model_id)
        .options(selectinload(Dimension.items))
        .order_by(Dimension.name)
    )
    dimensions = list(dim_result.scalars().all())

    dim_dicts: List[Dict[str, Any]] = []
    item_dicts: List[Dict[str, Any]] = []

    for dim in dimensions:
        dim_dicts.append(
            {
                "id": str(dim.id),
                "name": dim.name,
                "dimension_type": dim.dimension_type.value,
                "max_items": dim.max_items,
                "model_id": str(dim.model_id),
            }
        )
        for item in sorted(dim.items, key=lambda i: (i.sort_order, i.name)):
            item_dicts.append(
                {
                    "id": str(item.id),
                    "name": item.name,
                    "code": item.code,
                    "dimension_id": str(item.dimension_id),
                    "parent_id": str(item.parent_id) if item.parent_id else None,
                    "sort_order": item.sort_order,
                }
            )

    mod_result = await db.execute(
        select(Module)
        .where(Module.model_id == model_id)
        .options(
            selectinload(Module.line_items).selectinload(LineItem.line_item_dimensions)
        )
        .order_by(Module.name)
    )
    modules = list(mod_result.scalars().all())

    module_dicts: List[Dict[str, Any]] = []
    line_item_dicts: List[Dict[str, Any]] = []
    line_item_ids: List[uuid.UUID] = []

    for module in modules:
        module_dicts.append(
            {
                "id": str(module.id),
                "name": module.name,
                "description": module.description,
                "model_id": str(module.model_id),
                "conditional_format_rules": module.conditional_format_rules or [],
            }
        )
        for line_item in sorted(module.line_items, key=lambda li: (li.sort_order, li.name)):
            line_item_ids.append(line_item.id)
            line_item_dicts.append(
                {
                    "id": str(line_item.id),
                    "name": line_item.name,
                    "module_id": str(line_item.module_id),
                    "format": line_item.format.value,
                    "formula": line_item.formula,
                    "summary_method": line_item.summary_method.value,
                    "conditional_format_rules": line_item.conditional_format_rules or [],
                    "sort_order": line_item.sort_order,
                    "applies_to_dimensions": [
                        str(link.dimension_id)
                        for link in sorted(
                            line_item.line_item_dimensions,
                            key=lambda link: link.sort_order,
                        )
                    ],
                }
            )

    cell_dicts: List[Dict[str, Any]] = []
    if line_item_ids:
        cell_result = await db.execute(
            select(CellValue)
            .where(CellValue.line_item_id.in_(line_item_ids))
            .order_by(CellValue.line_item_id, CellValue.dimension_key)
        )
        for cell in cell_result.scalars().all():
            cell_dicts.append(
                {
                    "id": str(cell.id),
                    "line_item_id": str(cell.line_item_id),
                    "dimension_key": cell.dimension_key,
                    "value_number": cell.value_number,
                    "value_text": cell.value_text,
                    "value_boolean": cell.value_boolean,
                }
            )

    return {
        "dimensions": dim_dicts,
        "dimension_items": item_dicts,
        "modules": module_dicts,
        "line_items": line_item_dicts,
        "cell_values": cell_dicts,
    }


def _group_snapshot_entries(
    entries: List[Dict[str, Any]],
    key: str,
) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for entry in entries:
        group_key = str(entry.get(key) or "")
        if not group_key:
            continue
        grouped.setdefault(group_key, []).append(entry)
    return grouped


def _index_dimensions(
    snapshot: Dict[str, List[Dict[str, Any]]],
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str]]:
    dimensions_by_name: Dict[str, Dict[str, Any]] = {}
    dimension_id_to_name: Dict[str, str] = {}

    items_by_dimension_id = _group_snapshot_entries(
        snapshot.get("dimension_items", []), "dimension_id"
    )

    for raw_dimension in snapshot.get("dimensions", []):
        name = raw_dimension.get("name")
        if not isinstance(name, str) or name == "":
            continue

        dimension_id = str(raw_dimension.get("id") or "")
        if dimension_id:
            dimension_id_to_name[dimension_id] = name

        dimension_items = items_by_dimension_id.get(dimension_id, [])
        item_id_to_code: Dict[str, str] = {}
        for item in dimension_items:
            item_id = str(item.get("id") or "")
            code = item.get("code")
            if item_id and isinstance(code, str) and code:
                item_id_to_code[item_id] = code

        indexed_items: Dict[str, Dict[str, Any]] = {}
        for item in dimension_items:
            code = item.get("code")
            if not isinstance(code, str) or code == "":
                continue
            parent_id = item.get("parent_id")
            parent_code = None
            if parent_id is not None:
                parent_code = item_id_to_code.get(str(parent_id))
            indexed_items[code] = {
                "name": item.get("name"),
                "sort_order": item.get("sort_order", 0),
                "parent_code": parent_code,
            }

        dimensions_by_name[name] = {
            "dimension_type": raw_dimension.get("dimension_type"),
            "max_items": raw_dimension.get("max_items"),
            "items": indexed_items,
        }

    return dimensions_by_name, dimension_id_to_name


def _index_modules(
    snapshot: Dict[str, List[Dict[str, Any]]],
    dimension_id_to_name: Dict[str, str],
) -> Dict[str, Dict[str, Any]]:
    modules_by_name: Dict[str, Dict[str, Any]] = {}
    line_items_by_module_id = _group_snapshot_entries(snapshot.get("line_items", []), "module_id")

    for raw_module in snapshot.get("modules", []):
        module_name = raw_module.get("name")
        if not isinstance(module_name, str) or module_name == "":
            continue

        module_id = str(raw_module.get("id") or "")
        raw_line_items = line_items_by_module_id.get(module_id, [])

        indexed_line_items: Dict[str, Dict[str, Any]] = {}
        for line_item in raw_line_items:
            line_item_name = line_item.get("name")
            if not isinstance(line_item_name, str) or line_item_name == "":
                continue

            applies_to_dimension_names: List[str] = []
            for raw_dimension_id in line_item.get("applies_to_dimensions") or []:
                dimension_name = dimension_id_to_name.get(str(raw_dimension_id))
                if dimension_name is not None:
                    applies_to_dimension_names.append(dimension_name)
                else:
                    applies_to_dimension_names.append(str(raw_dimension_id))

            indexed_line_items[line_item_name] = {
                "format": line_item.get("format"),
                "formula": line_item.get("formula"),
                "summary_method": line_item.get("summary_method"),
                "conditional_format_rules": line_item.get("conditional_format_rules")
                or [],
                "sort_order": line_item.get("sort_order", 0),
                "applies_to_dimensions": applies_to_dimension_names,
            }

        modules_by_name[module_name] = {
            "description": raw_module.get("description"),
            "conditional_format_rules": raw_module.get("conditional_format_rules")
            or [],
            "line_items": indexed_line_items,
        }

    return modules_by_name


def _has_structural_changes(diff: Dict[str, Any]) -> bool:
    for section in ["dimensions", "dimension_items", "modules", "line_items"]:
        payload = diff.get(section, {})
        if payload.get("added") or payload.get("removed") or payload.get("modified"):
            return True
    return False


def _with_counts(section: Dict[str, Any]) -> Dict[str, Any]:
    section["counts"] = {
        "added": len(section.get("added", [])),
        "removed": len(section.get("removed", [])),
        "modified": len(section.get("modified", [])),
    }
    return section


def _build_structural_diff(
    source_snapshot: Dict[str, List[Dict[str, Any]]],
    target_snapshot: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    source_dimensions, source_dim_id_to_name = _index_dimensions(source_snapshot)
    target_dimensions, target_dim_id_to_name = _index_dimensions(target_snapshot)

    source_modules = _index_modules(source_snapshot, source_dim_id_to_name)
    target_modules = _index_modules(target_snapshot, target_dim_id_to_name)

    dimension_added_names = sorted(
        [name for name in source_dimensions.keys() if name not in target_dimensions]
    )
    dimension_removed_names = sorted(
        [name for name in target_dimensions.keys() if name not in source_dimensions]
    )

    dimension_added = [
        {
            "name": name,
            "dimension_type": source_dimensions[name].get("dimension_type"),
            "max_items": source_dimensions[name].get("max_items"),
        }
        for name in dimension_added_names
    ]
    dimension_removed = [
        {
            "name": name,
            "dimension_type": target_dimensions[name].get("dimension_type"),
            "max_items": target_dimensions[name].get("max_items"),
        }
        for name in dimension_removed_names
    ]

    dimension_modified: List[Dict[str, Any]] = []
    for name in sorted(set(source_dimensions.keys()).intersection(target_dimensions.keys())):
        source_entry = source_dimensions[name]
        target_entry = target_dimensions[name]
        field_changes: Dict[str, Any] = {}
        for field_name in ["dimension_type", "max_items"]:
            if source_entry.get(field_name) != target_entry.get(field_name):
                field_changes[field_name] = {
                    "source": source_entry.get(field_name),
                    "target": target_entry.get(field_name),
                }
        if field_changes:
            dimension_modified.append({"name": name, "changes": field_changes})

    dimension_items_added: List[Dict[str, Any]] = []
    dimension_items_removed: List[Dict[str, Any]] = []
    dimension_items_modified: List[Dict[str, Any]] = []

    for dimension_name in sorted(set(source_dimensions.keys()).intersection(target_dimensions.keys())):
        source_items = source_dimensions[dimension_name].get("items", {})
        target_items = target_dimensions[dimension_name].get("items", {})

        for code in sorted([c for c in source_items.keys() if c not in target_items]):
            payload = source_items[code]
            dimension_items_added.append(
                {
                    "dimension": dimension_name,
                    "code": code,
                    "name": payload.get("name"),
                }
            )

        for code in sorted([c for c in target_items.keys() if c not in source_items]):
            payload = target_items[code]
            dimension_items_removed.append(
                {
                    "dimension": dimension_name,
                    "code": code,
                    "name": payload.get("name"),
                }
            )

        for code in sorted(set(source_items.keys()).intersection(target_items.keys())):
            source_item = source_items[code]
            target_item = target_items[code]
            field_changes = {}
            for field_name in ["name", "sort_order", "parent_code"]:
                if source_item.get(field_name) != target_item.get(field_name):
                    field_changes[field_name] = {
                        "source": source_item.get(field_name),
                        "target": target_item.get(field_name),
                    }
            if field_changes:
                dimension_items_modified.append(
                    {
                        "dimension": dimension_name,
                        "code": code,
                        "changes": field_changes,
                    }
                )

    module_added_names = sorted([name for name in source_modules.keys() if name not in target_modules])
    module_removed_names = sorted([name for name in target_modules.keys() if name not in source_modules])

    modules_added = [
        {
            "name": name,
            "description": source_modules[name].get("description"),
            "conditional_format_rules": source_modules[name].get(
                "conditional_format_rules"
            ),
        }
        for name in module_added_names
    ]
    modules_removed = [
        {
            "name": name,
            "description": target_modules[name].get("description"),
            "conditional_format_rules": target_modules[name].get(
                "conditional_format_rules"
            ),
        }
        for name in module_removed_names
    ]

    modules_modified: List[Dict[str, Any]] = []
    line_items_added: List[Dict[str, Any]] = []
    line_items_removed: List[Dict[str, Any]] = []
    line_items_modified: List[Dict[str, Any]] = []

    for module_name in module_added_names:
        source_line_items = source_modules[module_name].get("line_items", {})
        for line_item_name in sorted(source_line_items.keys()):
            payload = source_line_items[line_item_name]
            line_items_added.append(
                {
                    "module": module_name,
                    "name": line_item_name,
                    "format": payload.get("format"),
                    "formula": payload.get("formula"),
                    "summary_method": payload.get("summary_method"),
                    "conditional_format_rules": payload.get(
                        "conditional_format_rules"
                    ),
                }
            )

    for module_name in module_removed_names:
        target_line_items = target_modules[module_name].get("line_items", {})
        for line_item_name in sorted(target_line_items.keys()):
            payload = target_line_items[line_item_name]
            line_items_removed.append(
                {
                    "module": module_name,
                    "name": line_item_name,
                    "format": payload.get("format"),
                    "formula": payload.get("formula"),
                    "summary_method": payload.get("summary_method"),
                    "conditional_format_rules": payload.get(
                        "conditional_format_rules"
                    ),
                }
            )

    for module_name in sorted(set(source_modules.keys()).intersection(target_modules.keys())):
        source_module = source_modules[module_name]
        target_module = target_modules[module_name]

        module_changes = {}
        if source_module.get("description") != target_module.get("description"):
            module_changes["description"] = {
                "source": source_module.get("description"),
                "target": target_module.get("description"),
            }
        if (
            source_module.get("conditional_format_rules")
            != target_module.get("conditional_format_rules")
        ):
            module_changes["conditional_format_rules"] = {
                "source": source_module.get("conditional_format_rules"),
                "target": target_module.get("conditional_format_rules"),
            }
        if module_changes:
            modules_modified.append({"name": module_name, "changes": module_changes})

        source_line_items = source_module.get("line_items", {})
        target_line_items = target_module.get("line_items", {})

        for line_item_name in sorted([name for name in source_line_items.keys() if name not in target_line_items]):
            payload = source_line_items[line_item_name]
            line_items_added.append(
                {
                    "module": module_name,
                    "name": line_item_name,
                    "format": payload.get("format"),
                    "formula": payload.get("formula"),
                    "summary_method": payload.get("summary_method"),
                    "conditional_format_rules": payload.get(
                        "conditional_format_rules"
                    ),
                }
            )

        for line_item_name in sorted([name for name in target_line_items.keys() if name not in source_line_items]):
            payload = target_line_items[line_item_name]
            line_items_removed.append(
                {
                    "module": module_name,
                    "name": line_item_name,
                    "format": payload.get("format"),
                    "formula": payload.get("formula"),
                    "summary_method": payload.get("summary_method"),
                    "conditional_format_rules": payload.get(
                        "conditional_format_rules"
                    ),
                }
            )

        for line_item_name in sorted(set(source_line_items.keys()).intersection(target_line_items.keys())):
            source_line_item = source_line_items[line_item_name]
            target_line_item = target_line_items[line_item_name]
            field_changes = {}
            for field_name in [
                "format",
                "formula",
                "summary_method",
                "conditional_format_rules",
                "sort_order",
                "applies_to_dimensions",
            ]:
                if source_line_item.get(field_name) != target_line_item.get(field_name):
                    field_changes[field_name] = {
                        "source": source_line_item.get(field_name),
                        "target": target_line_item.get(field_name),
                    }
            if field_changes:
                line_items_modified.append(
                    {
                        "module": module_name,
                        "name": line_item_name,
                        "changes": field_changes,
                    }
                )

    diff = {
        "dimensions": _with_counts(
            {
                "added": dimension_added,
                "removed": dimension_removed,
                "modified": dimension_modified,
            }
        ),
        "dimension_items": _with_counts(
            {
                "added": dimension_items_added,
                "removed": dimension_items_removed,
                "modified": dimension_items_modified,
            }
        ),
        "modules": _with_counts(
            {
                "added": modules_added,
                "removed": modules_removed,
                "modified": modules_modified,
            }
        ),
        "line_items": _with_counts(
            {
                "added": line_items_added,
                "removed": line_items_removed,
                "modified": line_items_modified,
            }
        ),
    }
    diff["has_changes"] = _has_structural_changes(diff)
    return diff


def _validate_merge_strategy(raw_strategy: Any) -> str:
    strategy = str(raw_strategy or "additive").strip().lower()
    if strategy not in {"additive", "replace", "manual"}:
        raise ValueError(
            "merge_strategy must be one of: additive, replace, manual"
        )
    return strategy


def _resolve_dimension_type(value: Any) -> DimensionType:
    if isinstance(value, DimensionType):
        return value
    if isinstance(value, str):
        try:
            return DimensionType(value)
        except ValueError as exc:
            raise ValueError(
                "Invalid dimension_type in snapshot: " + value
            ) from exc
    return DimensionType.custom


def _resolve_line_item_format(value: Any) -> LineItemFormat:
    if isinstance(value, LineItemFormat):
        return value
    if isinstance(value, str):
        try:
            return LineItemFormat(value)
        except ValueError as exc:
            raise ValueError("Invalid line item format in snapshot: " + value) from exc
    return LineItemFormat.number


def _resolve_summary_method(value: Any) -> SummaryMethod:
    if isinstance(value, SummaryMethod):
        return value
    if isinstance(value, str):
        try:
            return SummaryMethod(value)
        except ValueError as exc:
            raise ValueError("Invalid summary_method in snapshot: " + value) from exc
    return SummaryMethod.sum


def _remap_dimension_key(
    source_key: str,
    source_item_to_target_item: Dict[str, uuid.UUID],
) -> Optional[str]:
    if source_key == "":
        return ""

    parts = [part for part in source_key.split("|") if part]
    remapped_parts: List[str] = []
    for part in parts:
        mapped = source_item_to_target_item.get(str(part))
        if mapped is None:
            return None
        remapped_parts.append(str(mapped))

    remapped_parts.sort()
    return "|".join(remapped_parts)


async def _clear_model_structure(db: AsyncSession, model_id: uuid.UUID) -> None:
    module_ids_result = await db.execute(
        select(Module.id).where(Module.model_id == model_id)
    )
    module_ids = [row[0] for row in module_ids_result.all()]

    line_item_ids: List[uuid.UUID] = []
    if module_ids:
        line_item_ids_result = await db.execute(
            select(LineItem.id).where(LineItem.module_id.in_(module_ids))
        )
        line_item_ids = [row[0] for row in line_item_ids_result.all()]

    if line_item_ids:
        await db.execute(
            delete(CellValue).where(CellValue.line_item_id.in_(line_item_ids))
        )
        await db.execute(
            delete(LineItemDimension).where(LineItemDimension.line_item_id.in_(line_item_ids))
        )
        await db.execute(delete(LineItem).where(LineItem.id.in_(line_item_ids)))

    if module_ids:
        await db.execute(delete(Module).where(Module.id.in_(module_ids)))

    dimension_ids_result = await db.execute(
        select(Dimension.id).where(Dimension.model_id == model_id)
    )
    dimension_ids = [row[0] for row in dimension_ids_result.all()]

    if dimension_ids:
        await db.execute(
            delete(LineItemDimension).where(LineItemDimension.dimension_id.in_(dimension_ids))
        )
        await db.execute(
            delete(DimensionItem).where(DimensionItem.dimension_id.in_(dimension_ids))
        )
        await db.execute(delete(Dimension).where(Dimension.id.in_(dimension_ids)))

    await db.flush()


async def _apply_replace_promotion(
    db: AsyncSession,
    target_model_id: uuid.UUID,
    source_snapshot: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, int]:
    await _clear_model_structure(db, target_model_id)

    source_dimensions = source_snapshot.get("dimensions", [])
    source_dimension_items = source_snapshot.get("dimension_items", [])
    source_modules = source_snapshot.get("modules", [])
    source_line_items = source_snapshot.get("line_items", [])
    source_cells = source_snapshot.get("cell_values", [])

    source_dimension_id_to_target_id: Dict[str, uuid.UUID] = {}
    source_item_id_to_target_id: Dict[str, uuid.UUID] = {}
    source_module_id_to_target_id: Dict[str, uuid.UUID] = {}
    source_line_item_id_to_target_id: Dict[str, uuid.UUID] = {}

    dimensions_added = 0
    dimension_items_added = 0
    modules_added = 0
    line_items_added = 0
    cells_copied = 0
    cells_skipped = 0

    for raw_dimension in source_dimensions:
        source_dimension_id = str(raw_dimension.get("id") or "")
        name = raw_dimension.get("name")
        if source_dimension_id == "" or not isinstance(name, str) or name == "":
            continue

        target_dimension = Dimension(
            id=uuid.uuid4(),
            name=name,
            dimension_type=_resolve_dimension_type(raw_dimension.get("dimension_type")),
            max_items=raw_dimension.get("max_items"),
            model_id=target_model_id,
        )
        db.add(target_dimension)
        source_dimension_id_to_target_id[source_dimension_id] = target_dimension.id
        dimensions_added += 1

    await db.flush()

    items_by_dimension = _group_snapshot_entries(source_dimension_items, "dimension_id")
    source_item_id_to_object: Dict[str, DimensionItem] = {}

    for source_dimension_id, raw_items in items_by_dimension.items():
        target_dimension_id = source_dimension_id_to_target_id.get(source_dimension_id)
        if target_dimension_id is None:
            continue

        for raw_item in sorted(raw_items, key=lambda item: (item.get("sort_order", 0), item.get("name") or "")):
            source_item_id = str(raw_item.get("id") or "")
            code = raw_item.get("code")
            name = raw_item.get("name")
            if source_item_id == "" or not isinstance(code, str) or code == "":
                continue
            if not isinstance(name, str) or name == "":
                name = code

            target_item = DimensionItem(
                id=uuid.uuid4(),
                name=name,
                code=code,
                dimension_id=target_dimension_id,
                parent_id=None,
                sort_order=int(raw_item.get("sort_order") or 0),
            )
            db.add(target_item)
            source_item_id_to_target_id[source_item_id] = target_item.id
            source_item_id_to_object[source_item_id] = target_item
            dimension_items_added += 1

    await db.flush()

    for raw_item in source_dimension_items:
        source_item_id = str(raw_item.get("id") or "")
        parent_source_id = raw_item.get("parent_id")
        if source_item_id == "" or parent_source_id is None:
            continue

        target_item = source_item_id_to_object.get(source_item_id)
        if target_item is None:
            continue

        parent_target_id = source_item_id_to_target_id.get(str(parent_source_id))
        if parent_target_id is not None:
            target_item.parent_id = parent_target_id

    await db.flush()

    for raw_module in source_modules:
        source_module_id = str(raw_module.get("id") or "")
        module_name = raw_module.get("name")
        if source_module_id == "" or not isinstance(module_name, str) or module_name == "":
            continue

        target_module = Module(
            id=uuid.uuid4(),
            name=module_name,
            description=raw_module.get("description"),
            conditional_format_rules=raw_module.get("conditional_format_rules")
            or [],
            model_id=target_model_id,
        )
        db.add(target_module)
        source_module_id_to_target_id[source_module_id] = target_module.id
        modules_added += 1

    await db.flush()

    line_items_by_module = _group_snapshot_entries(source_line_items, "module_id")

    for source_module_id, raw_line_items in line_items_by_module.items():
        target_module_id = source_module_id_to_target_id.get(source_module_id)
        if target_module_id is None:
            continue

        for raw_line_item in sorted(raw_line_items, key=lambda li: (li.get("sort_order", 0), li.get("name") or "")):
            source_line_item_id = str(raw_line_item.get("id") or "")
            line_item_name = raw_line_item.get("name")
            if source_line_item_id == "" or not isinstance(line_item_name, str) or line_item_name == "":
                continue

            target_line_item = LineItem(
                id=uuid.uuid4(),
                name=line_item_name,
                module_id=target_module_id,
                format=_resolve_line_item_format(raw_line_item.get("format")),
                formula=raw_line_item.get("formula"),
                summary_method=_resolve_summary_method(raw_line_item.get("summary_method")),
                sort_order=int(raw_line_item.get("sort_order") or 0),
                conditional_format_rules=raw_line_item.get(
                    "conditional_format_rules"
                )
                or [],
            )
            db.add(target_line_item)
            source_line_item_id_to_target_id[source_line_item_id] = target_line_item.id

            raw_applies_to_dimensions = raw_line_item.get("applies_to_dimensions") or []
            for sort_order, source_dimension_id in enumerate(raw_applies_to_dimensions):
                target_dimension_id = source_dimension_id_to_target_id.get(str(source_dimension_id))
                if target_dimension_id is None:
                    continue
                db.add(
                    LineItemDimension(
                        id=uuid.uuid4(),
                        line_item_id=target_line_item.id,
                        dimension_id=target_dimension_id,
                        sort_order=sort_order,
                    )
                )

            line_items_added += 1

    await db.flush()

    deduped_cells: Dict[Tuple[uuid.UUID, str], Dict[str, Any]] = {}

    for raw_cell in source_cells:
        source_line_item_id = str(raw_cell.get("line_item_id") or "")
        target_line_item_id = source_line_item_id_to_target_id.get(source_line_item_id)
        if target_line_item_id is None:
            continue

        source_dimension_key = str(raw_cell.get("dimension_key") or "")
        target_dimension_key = _remap_dimension_key(
            source_dimension_key,
            source_item_id_to_target_id,
        )
        if source_dimension_key != "" and target_dimension_key is None:
            cells_skipped += 1
            continue
        if target_dimension_key is None:
            target_dimension_key = ""

        deduped_cells[(target_line_item_id, target_dimension_key)] = raw_cell

    for (target_line_item_id, target_dimension_key), raw_cell in deduped_cells.items():
        db.add(
            CellValue(
                id=uuid.uuid4(),
                line_item_id=target_line_item_id,
                dimension_key=target_dimension_key,
                value_number=raw_cell.get("value_number"),
                value_text=raw_cell.get("value_text"),
                value_boolean=raw_cell.get("value_boolean"),
            )
        )
        cells_copied += 1

    await db.flush()

    return {
        "dimensions_added": dimensions_added,
        "dimension_items_added": dimension_items_added,
        "modules_added": modules_added,
        "line_items_added": line_items_added,
        "cells_copied": cells_copied,
        "cells_skipped": cells_skipped,
    }


async def _apply_additive_promotion(
    db: AsyncSession,
    target_model_id: uuid.UUID,
    source_snapshot: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, int]:
    dim_result = await db.execute(
        select(Dimension)
        .where(Dimension.model_id == target_model_id)
        .options(selectinload(Dimension.items))
    )
    target_dimensions = list(dim_result.scalars().all())

    module_result = await db.execute(
        select(Module)
        .where(Module.model_id == target_model_id)
        .options(
            selectinload(Module.line_items).selectinload(LineItem.line_item_dimensions)
        )
    )
    target_modules = list(module_result.scalars().all())

    target_dimensions_by_name: Dict[str, Dimension] = {
        dimension.name: dimension for dimension in target_dimensions
    }
    target_modules_by_name: Dict[str, Module] = {module.name: module for module in target_modules}

    source_dimensions = source_snapshot.get("dimensions", [])
    source_dimension_items = source_snapshot.get("dimension_items", [])
    source_modules = source_snapshot.get("modules", [])
    source_line_items = source_snapshot.get("line_items", [])
    source_cells = source_snapshot.get("cell_values", [])

    source_dimension_id_to_target_id: Dict[str, uuid.UUID] = {}
    source_item_id_to_target_id: Dict[str, uuid.UUID] = {}
    source_module_id_to_target_module: Dict[str, Module] = {}
    new_source_line_item_id_to_target_id: Dict[str, uuid.UUID] = {}

    dimensions_added = 0
    dimension_items_added = 0
    modules_added = 0
    line_items_added = 0
    cells_copied = 0
    cells_skipped = 0

    for raw_dimension in source_dimensions:
        source_dimension_id = str(raw_dimension.get("id") or "")
        name = raw_dimension.get("name")
        if source_dimension_id == "" or not isinstance(name, str) or name == "":
            continue

        target_dimension = target_dimensions_by_name.get(name)
        if target_dimension is None:
            target_dimension = Dimension(
                id=uuid.uuid4(),
                name=name,
                dimension_type=_resolve_dimension_type(raw_dimension.get("dimension_type")),
                max_items=raw_dimension.get("max_items"),
                model_id=target_model_id,
            )
            db.add(target_dimension)
            await db.flush()
            target_dimensions_by_name[name] = target_dimension
            dimensions_added += 1

        source_dimension_id_to_target_id[source_dimension_id] = target_dimension.id

    items_by_dimension_id = _group_snapshot_entries(source_dimension_items, "dimension_id")
    newly_created_source_item_ids: Set[str] = set()
    source_item_id_to_target_item: Dict[str, DimensionItem] = {}

    for source_dimension_id, raw_items in items_by_dimension_id.items():
        target_dimension_id = source_dimension_id_to_target_id.get(source_dimension_id)
        if target_dimension_id is None:
            continue

        target_items_result = await db.execute(
            select(DimensionItem).where(DimensionItem.dimension_id == target_dimension_id)
        )
        target_items_by_code = {
            item.code: item for item in target_items_result.scalars().all()
        }

        for raw_item in sorted(raw_items, key=lambda item: (item.get("sort_order", 0), item.get("name") or "")):
            source_item_id = str(raw_item.get("id") or "")
            code = raw_item.get("code")
            name = raw_item.get("name")
            if source_item_id == "" or not isinstance(code, str) or code == "":
                continue
            if not isinstance(name, str) or name == "":
                name = code

            target_item = target_items_by_code.get(code)
            if target_item is None:
                target_item = DimensionItem(
                    id=uuid.uuid4(),
                    name=name,
                    code=code,
                    dimension_id=target_dimension_id,
                    parent_id=None,
                    sort_order=int(raw_item.get("sort_order") or 0),
                )
                db.add(target_item)
                await db.flush()
                target_items_by_code[code] = target_item
                newly_created_source_item_ids.add(source_item_id)
                dimension_items_added += 1

            source_item_id_to_target_id[source_item_id] = target_item.id
            source_item_id_to_target_item[source_item_id] = target_item

    for raw_item in source_dimension_items:
        source_item_id = str(raw_item.get("id") or "")
        if source_item_id not in newly_created_source_item_ids:
            continue

        target_item = source_item_id_to_target_item.get(source_item_id)
        if target_item is None:
            continue

        parent_source_id = raw_item.get("parent_id")
        if parent_source_id is None:
            continue

        target_parent_id = source_item_id_to_target_id.get(str(parent_source_id))
        if target_parent_id is not None:
            target_item.parent_id = target_parent_id

    await db.flush()

    for raw_module in source_modules:
        source_module_id = str(raw_module.get("id") or "")
        module_name = raw_module.get("name")
        if source_module_id == "" or not isinstance(module_name, str) or module_name == "":
            continue

        target_module = target_modules_by_name.get(module_name)
        if target_module is None:
            target_module = Module(
                id=uuid.uuid4(),
                name=module_name,
                description=raw_module.get("description"),
                conditional_format_rules=raw_module.get("conditional_format_rules")
                or [],
                model_id=target_model_id,
            )
            db.add(target_module)
            await db.flush()
            target_modules_by_name[module_name] = target_module
            modules_added += 1

        source_module_id_to_target_module[source_module_id] = target_module

    line_items_by_module_id = _group_snapshot_entries(source_line_items, "module_id")

    for source_module_id, raw_line_items in line_items_by_module_id.items():
        target_module = source_module_id_to_target_module.get(source_module_id)
        if target_module is None:
            continue

        existing_line_items_result = await db.execute(
            select(LineItem).where(LineItem.module_id == target_module.id)
        )
        target_line_items_by_name = {
            line_item.name: line_item
            for line_item in existing_line_items_result.scalars().all()
        }

        for raw_line_item in sorted(raw_line_items, key=lambda li: (li.get("sort_order", 0), li.get("name") or "")):
            source_line_item_id = str(raw_line_item.get("id") or "")
            line_item_name = raw_line_item.get("name")
            if source_line_item_id == "" or not isinstance(line_item_name, str) or line_item_name == "":
                continue

            existing_line_item = target_line_items_by_name.get(line_item_name)
            if existing_line_item is not None:
                continue

            new_line_item = LineItem(
                id=uuid.uuid4(),
                name=line_item_name,
                module_id=target_module.id,
                format=_resolve_line_item_format(raw_line_item.get("format")),
                formula=raw_line_item.get("formula"),
                summary_method=_resolve_summary_method(raw_line_item.get("summary_method")),
                sort_order=int(raw_line_item.get("sort_order") or 0),
                conditional_format_rules=raw_line_item.get(
                    "conditional_format_rules"
                )
                or [],
            )
            db.add(new_line_item)
            await db.flush()

            raw_applies_to_dimensions = raw_line_item.get("applies_to_dimensions") or []
            for sort_order, source_dimension_id in enumerate(raw_applies_to_dimensions):
                target_dimension_id = source_dimension_id_to_target_id.get(str(source_dimension_id))
                if target_dimension_id is None:
                    continue
                db.add(
                    LineItemDimension(
                        id=uuid.uuid4(),
                        line_item_id=new_line_item.id,
                        dimension_id=target_dimension_id,
                        sort_order=sort_order,
                    )
                )

            await db.flush()
            target_line_items_by_name[line_item_name] = new_line_item
            new_source_line_item_id_to_target_id[source_line_item_id] = new_line_item.id
            line_items_added += 1

    await db.flush()

    deduped_cells: Dict[Tuple[uuid.UUID, str], Dict[str, Any]] = {}

    for raw_cell in source_cells:
        source_line_item_id = str(raw_cell.get("line_item_id") or "")
        target_line_item_id = new_source_line_item_id_to_target_id.get(source_line_item_id)
        if target_line_item_id is None:
            continue

        source_dimension_key = str(raw_cell.get("dimension_key") or "")
        target_dimension_key = _remap_dimension_key(
            source_dimension_key,
            source_item_id_to_target_id,
        )
        if source_dimension_key != "" and target_dimension_key is None:
            cells_skipped += 1
            continue
        if target_dimension_key is None:
            target_dimension_key = ""

        deduped_cells[(target_line_item_id, target_dimension_key)] = raw_cell

    for (target_line_item_id, target_dimension_key), raw_cell in deduped_cells.items():
        db.add(
            CellValue(
                id=uuid.uuid4(),
                line_item_id=target_line_item_id,
                dimension_key=target_dimension_key,
                value_number=raw_cell.get("value_number"),
                value_text=raw_cell.get("value_text"),
                value_boolean=raw_cell.get("value_boolean"),
            )
        )
        cells_copied += 1

    await db.flush()

    return {
        "dimensions_added": dimensions_added,
        "dimension_items_added": dimension_items_added,
        "modules_added": modules_added,
        "line_items_added": line_items_added,
        "cells_copied": cells_copied,
        "cells_skipped": cells_skipped,
    }


async def _get_source_snapshot_for_promotion(
    db: AsyncSession,
    source_model_id: uuid.UUID,
    tag: RevisionTag,
) -> Dict[str, List[Dict[str, Any]]]:
    if isinstance(tag.snapshot_data, dict) and tag.snapshot_data:
        return _ensure_snapshot_data(tag.snapshot_data)
    return await _serialize_model_state(db, source_model_id)


async def _get_latest_completed_promotion(
    db: AsyncSession,
    source_env_id: uuid.UUID,
    target_env_id: uuid.UUID,
) -> Optional[PromotionRecord]:
    result = await db.execute(
        select(PromotionRecord)
        .where(PromotionRecord.source_env_id == source_env_id)
        .where(PromotionRecord.target_env_id == target_env_id)
        .where(PromotionRecord.status == PromotionStatus.completed)
        .order_by(PromotionRecord.completed_at.desc(), PromotionRecord.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _build_conflict_payload(
    db: AsyncSession,
    source_env_id: uuid.UUID,
    target_env_id: uuid.UUID,
    current_target_structural_snapshot: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    latest_promotion = await _get_latest_completed_promotion(
        db,
        source_env_id=source_env_id,
        target_env_id=target_env_id,
    )

    if latest_promotion is None:
        return {
            "has_conflicts": False,
            "last_completed_promotion_id": None,
            "last_completed_at": None,
            "details": {},
        }

    latest_summary = latest_promotion.change_summary if latest_promotion.change_summary else {}
    latest_target_snapshot = latest_summary.get("target_after_snapshot")
    latest_target_signature = latest_summary.get("target_after_signature")

    current_signature = _snapshot_signature(current_target_structural_snapshot)

    if isinstance(latest_target_snapshot, dict):
        baseline_snapshot = _ensure_snapshot_data(latest_target_snapshot)
        structural_diff = _build_structural_diff(
            baseline_snapshot,
            current_target_structural_snapshot,
        )
        has_conflicts = _has_structural_changes(structural_diff)
        details: Dict[str, Any] = structural_diff
    else:
        has_conflicts = bool(
            isinstance(latest_target_signature, str)
            and latest_target_signature != current_signature
        )
        details = {}
        if has_conflicts:
            details = {
                "message": "Target structure changed since last completed promotion"
            }

    return {
        "has_conflicts": has_conflicts,
        "last_completed_promotion_id": str(latest_promotion.id),
        "last_completed_at": latest_promotion.completed_at.isoformat()
        if latest_promotion.completed_at is not None
        else None,
        "details": details,
    }


# ---------------------------------------------------------------------------
# Environment CRUD
# ---------------------------------------------------------------------------


async def create_environment(
    db: AsyncSession,
    model_id: uuid.UUID,
    data: EnvironmentCreate,
) -> ALMEnvironment:
    env = ALMEnvironment(
        model_id=model_id,
        env_type=EnvironmentType(data.env_type),
        name=data.name,
        description=data.description,
        source_env_id=data.source_env_id,
    )
    db.add(env)
    await db.commit()
    await db.refresh(env)
    return env


async def get_environment_by_id(
    db: AsyncSession, env_id: uuid.UUID
) -> Optional[ALMEnvironment]:
    result = await db.execute(
        select(ALMEnvironment).where(ALMEnvironment.id == env_id)
    )
    return result.scalar_one_or_none()


async def list_environments_for_model(
    db: AsyncSession, model_id: uuid.UUID
) -> List[ALMEnvironment]:
    result = await db.execute(
        select(ALMEnvironment)
        .where(ALMEnvironment.model_id == model_id)
        .order_by(ALMEnvironment.created_at.asc())
    )
    return list(result.scalars().all())


async def update_environment(
    db: AsyncSession, env: ALMEnvironment, data: EnvironmentUpdate
) -> ALMEnvironment:
    if data.name is not None:
        env.name = data.name
    if data.description is not None:
        env.description = data.description
    db.add(env)
    await db.commit()
    await db.refresh(env)
    return env


async def delete_environment(db: AsyncSession, env: ALMEnvironment) -> None:
    await db.delete(env)
    await db.commit()


# ---------------------------------------------------------------------------
# Lock / Unlock
# ---------------------------------------------------------------------------


async def set_environment_lock(
    db: AsyncSession, env: ALMEnvironment, data: LockRequest
) -> ALMEnvironment:
    env.is_locked = data.is_locked
    db.add(env)
    await db.commit()
    await db.refresh(env)
    return env


# ---------------------------------------------------------------------------
# Revision Tags
# ---------------------------------------------------------------------------


async def create_revision_tag(
    db: AsyncSession,
    env_id: uuid.UUID,
    user_id: uuid.UUID,
    data: RevisionTagCreate,
) -> RevisionTag:
    snapshot_data = data.snapshot_data
    if snapshot_data is None:
        env = await get_environment_by_id(db, env_id)
        if env is None:
            raise ValueError("Environment not found")
        snapshot_data = await _serialize_model_state(db, env.model_id)

    tag = RevisionTag(
        environment_id=env_id,
        tag_name=data.tag_name,
        description=data.description,
        created_by=user_id,
        snapshot_data=snapshot_data,
    )
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return tag


async def get_revision_tag_by_id(
    db: AsyncSession, tag_id: uuid.UUID
) -> Optional[RevisionTag]:
    result = await db.execute(
        select(RevisionTag).where(RevisionTag.id == tag_id)
    )
    return result.scalar_one_or_none()


async def list_revision_tags(
    db: AsyncSession, env_id: uuid.UUID
) -> List[RevisionTag]:
    result = await db.execute(
        select(RevisionTag)
        .where(RevisionTag.environment_id == env_id)
        .order_by(RevisionTag.created_at.asc())
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Promotions
# ---------------------------------------------------------------------------


async def initiate_promotion(
    db: AsyncSession,
    source_env_id: uuid.UUID,
    user_id: uuid.UUID,
    data: PromotionCreate,
) -> PromotionRecord:
    source_env = await get_environment_by_id(db, source_env_id)
    target_env = await get_environment_by_id(db, data.target_env_id)
    tag = await get_revision_tag_by_id(db, data.revision_tag_id)

    if source_env is None:
        raise ValueError("Source environment not found")
    if target_env is None:
        raise ValueError("Target environment not found")
    if tag is None:
        raise ValueError("Revision tag not found")

    merge_strategy = _validate_merge_strategy(data.merge_strategy)

    source_snapshot = await _get_source_snapshot_for_promotion(
        db,
        source_model_id=source_env.model_id,
        tag=tag,
    )
    target_snapshot = await _serialize_model_state(db, target_env.model_id)

    source_structural_snapshot = _structural_snapshot(source_snapshot)
    target_structural_snapshot = _structural_snapshot(target_snapshot)

    structural_diff = _build_structural_diff(
        source_structural_snapshot,
        target_structural_snapshot,
    )
    conflict_payload = await _build_conflict_payload(
        db,
        source_env_id=source_env_id,
        target_env_id=data.target_env_id,
        current_target_structural_snapshot=target_structural_snapshot,
    )

    change_summary: Dict[str, Any] = dict(data.change_summary or {})
    change_summary["merge_strategy"] = merge_strategy
    change_summary["structural_diff"] = structural_diff
    change_summary["conflicts"] = conflict_payload
    change_summary["source_signature"] = _snapshot_signature(source_structural_snapshot)
    change_summary["target_signature_at_initiation"] = _snapshot_signature(
        target_structural_snapshot
    )

    record = PromotionRecord(
        source_env_id=source_env_id,
        target_env_id=data.target_env_id,
        revision_tag_id=data.revision_tag_id,
        promoted_by=user_id,
        status=PromotionStatus.pending,
        change_summary=change_summary,
        started_at=datetime.now(timezone.utc),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_promotion_by_id(
    db: AsyncSession, promotion_id: uuid.UUID
) -> Optional[PromotionRecord]:
    result = await db.execute(
        select(PromotionRecord)
        .where(PromotionRecord.id == promotion_id)
        .options(
            selectinload(PromotionRecord.source_env),
            selectinload(PromotionRecord.target_env),
            selectinload(PromotionRecord.revision_tag),
        )
    )
    return result.scalar_one_or_none()


async def list_promotions_for_env(
    db: AsyncSession, env_id: uuid.UUID
) -> List[PromotionRecord]:
    result = await db.execute(
        select(PromotionRecord)
        .where(PromotionRecord.source_env_id == env_id)
        .order_by(PromotionRecord.created_at.desc())
    )
    return list(result.scalars().all())


async def complete_promotion(
    db: AsyncSession, record: PromotionRecord
) -> PromotionRecord:
    promotion_id = record.id
    db_record = await get_promotion_by_id(db, promotion_id)
    if db_record is None:
        raise ValueError("Promotion not found")

    if db_record.status not in (PromotionStatus.pending, PromotionStatus.in_progress):
        raise ValueError(
            "Cannot complete promotion with status " + db_record.status.value
        )

    source_env = await get_environment_by_id(db, db_record.source_env_id)
    target_env = await get_environment_by_id(db, db_record.target_env_id)
    tag = await get_revision_tag_by_id(db, db_record.revision_tag_id)

    if source_env is None:
        raise ValueError("Source environment not found")
    if target_env is None:
        raise ValueError("Target environment not found")
    if tag is None:
        raise ValueError("Revision tag not found")
    if target_env.is_locked:
        raise ValueError("Target environment is locked")

    source_snapshot = await _get_source_snapshot_for_promotion(
        db,
        source_model_id=source_env.model_id,
        tag=tag,
    )
    source_structural_snapshot = _structural_snapshot(source_snapshot)

    target_snapshot_before = await _serialize_model_state(db, target_env.model_id)
    target_structural_snapshot_before = _structural_snapshot(target_snapshot_before)

    change_summary: Dict[str, Any] = dict(db_record.change_summary or {})
    merge_strategy = _validate_merge_strategy(change_summary.get("merge_strategy", "additive"))

    runtime_conflicts = dict(change_summary.get("conflicts") or {})
    runtime_conflicts["has_conflicts"] = bool(runtime_conflicts.get("has_conflicts", False))

    expected_target_signature = change_summary.get("target_signature_at_initiation")
    current_target_signature = _snapshot_signature(target_structural_snapshot_before)
    if isinstance(expected_target_signature, str):
        changed_since_initiation = expected_target_signature != current_target_signature
        runtime_conflicts["target_changed_since_initiation"] = changed_since_initiation
        if changed_since_initiation:
            runtime_conflicts["has_conflicts"] = True

    latest_conflicts = await _build_conflict_payload(
        db,
        source_env_id=db_record.source_env_id,
        target_env_id=db_record.target_env_id,
        current_target_structural_snapshot=target_structural_snapshot_before,
    )
    runtime_conflicts["latest_sync_conflicts"] = latest_conflicts
    if latest_conflicts.get("has_conflicts"):
        runtime_conflicts["has_conflicts"] = True

    if merge_strategy == "manual" and runtime_conflicts.get("has_conflicts"):
        raise ValueError(
            "Manual promotion requires conflict resolution before execution"
        )

    db_record.status = PromotionStatus.in_progress
    if db_record.started_at is None:
        db_record.started_at = datetime.now(timezone.utc)
    db.add(db_record)
    await db.flush()

    target_model_id = target_env.model_id

    try:
        if merge_strategy == "replace":
            execution = await _apply_replace_promotion(
                db,
                target_model_id=target_model_id,
                source_snapshot=source_snapshot,
            )
        else:
            execution = await _apply_additive_promotion(
                db,
                target_model_id=target_model_id,
                source_snapshot=source_snapshot,
            )

        target_snapshot_after = await _serialize_model_state(db, target_model_id)
        target_structural_snapshot_after = _structural_snapshot(target_snapshot_after)

        change_summary["merge_strategy"] = merge_strategy
        change_summary["conflicts"] = runtime_conflicts
        change_summary["structural_diff"] = _build_structural_diff(
            source_structural_snapshot,
            target_structural_snapshot_before,
        )
        change_summary["execution"] = execution
        change_summary["source_signature"] = _snapshot_signature(source_structural_snapshot)
        change_summary["target_before_signature"] = _snapshot_signature(
            target_structural_snapshot_before
        )
        change_summary["target_after_signature"] = _snapshot_signature(
            target_structural_snapshot_after
        )
        change_summary["target_after_snapshot"] = target_structural_snapshot_after
        change_summary["rollback"] = {"performed": False}

        db_record.change_summary = change_summary
        db_record.status = PromotionStatus.completed
        db_record.completed_at = datetime.now(timezone.utc)
        db.add(db_record)

        await db.commit()
        await db.refresh(db_record)
        return db_record

    except Exception as exc:
        await db.rollback()

        restore_error: Optional[str] = None
        try:
            await _apply_replace_promotion(
                db,
                target_model_id=target_model_id,
                source_snapshot=target_snapshot_before,
            )
            await db.commit()
        except Exception as restore_exc:
            await db.rollback()
            restore_error = str(restore_exc)

        failed_record = await get_promotion_by_id(db, promotion_id)
        if failed_record is None:
            raise ValueError("Promotion not found after rollback")

        failed_summary: Dict[str, Any] = dict(failed_record.change_summary or {})
        failed_summary["merge_strategy"] = merge_strategy
        failed_summary["conflicts"] = runtime_conflicts
        failed_summary["execution_error"] = str(exc)
        failed_summary["rollback"] = {
            "performed": restore_error is None,
            "restore_error": restore_error,
        }

        if restore_error is None:
            restored_target_snapshot = await _serialize_model_state(db, target_model_id)
            restored_structural_snapshot = _structural_snapshot(restored_target_snapshot)
            failed_summary["target_after_rollback_signature"] = _snapshot_signature(
                restored_structural_snapshot
            )

        failed_record.change_summary = failed_summary
        failed_record.status = (
            PromotionStatus.rolled_back
            if restore_error is None
            else PromotionStatus.failed
        )
        failed_record.completed_at = datetime.now(timezone.utc)
        db.add(failed_record)

        await db.commit()
        await db.refresh(failed_record)
        return failed_record


async def fail_promotion(
    db: AsyncSession, record: PromotionRecord
) -> PromotionRecord:
    if record.status not in (PromotionStatus.pending, PromotionStatus.in_progress):
        raise ValueError(
            "Cannot fail promotion with status " + record.status.value
        )
    record.status = PromotionStatus.failed
    record.completed_at = datetime.now(timezone.utc)
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


# ---------------------------------------------------------------------------
# Tag comparison
# ---------------------------------------------------------------------------


def _diff_dicts(old: dict, new: dict) -> Dict[str, Any]:
    """Shallow diff two dicts, returning added/removed/modified keys."""
    added: Dict[str, Any] = {}
    removed: Dict[str, Any] = {}
    modified: Dict[str, Any] = {}

    all_keys = set(list(old.keys()) + list(new.keys()))
    for key in all_keys:
        if key not in old:
            added[key] = new[key]
        elif key not in new:
            removed[key] = old[key]
        elif old[key] != new[key]:
            modified[key] = {"old": old[key], "new": new[key]}

    return {"added": added, "removed": removed, "modified": modified}


async def compare_revision_tags(
    db: AsyncSession,
    tag_1: RevisionTag,
    tag_2: RevisionTag,
) -> TagComparisonResponse:
    del db  # Keep signature symmetric with other service functions.
    snap_1 = tag_1.snapshot_data if tag_1.snapshot_data else {}
    snap_2 = tag_2.snapshot_data if tag_2.snapshot_data else {}
    diff = _diff_dicts(snap_1, snap_2)
    return TagComparisonResponse(
        tag_1_id=tag_1.id,
        tag_1_name=tag_1.tag_name,
        tag_2_id=tag_2.id,
        tag_2_name=tag_2.tag_name,
        added=diff["added"],
        removed=diff["removed"],
        modified=diff["modified"],
    )
