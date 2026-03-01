"""
F049 Rust bridge for the calculation engine.

This module exposes a stable Python API whether or not the native PyO3 module
(`dynaplan_engine`) is available at runtime.
"""

import json
import os
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from app.engine.dependency_graph import DependencyGraph
from app.engine.formula import evaluate_formula as evaluate_formula_python
from app.engine.spread import (
    SpreadMethod,
    aggregate_values as aggregate_values_python,
    spread_value as spread_value_python,
)

try:
    import dynaplan_engine as _dynaplan_engine  # type: ignore
except Exception:  # pragma: no cover - import can fail on unsupported platforms
    _dynaplan_engine = None

_MODEL_HANDLES: Dict[str, Any] = {}
_MODEL_HANDLES_LOCK = threading.Lock()


def _env_rust_enabled() -> bool:
    raw = os.getenv("DYNAPLAN_USE_RUST_ENGINE", "1").strip().lower()
    return raw not in {"0", "false", "off", "no"}


def rust_engine_available() -> bool:
    return _env_rust_enabled() and _dynaplan_engine is not None


@dataclass
class _PythonModelHandle:
    model_id: Optional[str] = None
    graph: DependencyGraph = field(default_factory=DependencyGraph)
    cells: Dict[Tuple[str, str], Any] = field(default_factory=dict)


def _parse_dimension_key(dimension_key: Any) -> List[str]:
    if dimension_key is None:
        return []

    if isinstance(dimension_key, str):
        return [part for part in dimension_key.split("|") if part]

    if isinstance(dimension_key, (list, tuple, set)):
        return [str(part) for part in dimension_key if str(part)]

    raise TypeError("dimension_key must be str or list-like")


def _dimension_key_to_str(dimension_key: Any) -> str:
    parts = _parse_dimension_key(dimension_key)
    return "|".join(sorted(parts))


def _build_recalc_result(order: List[str], changed_count: int) -> Dict[str, Any]:
    return {
        "ordered_nodes": order,
        "levels": [[node] for node in order],
        "recalculated_line_items": len(order),
        "recalculated_cells": changed_count,
    }


def _extract_row_value(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _load_python_model(model_json: str) -> _PythonModelHandle:
    payload = json.loads(model_json) if model_json else {}
    handle = _PythonModelHandle(model_id=payload.get("model_id"))

    line_items = payload.get("line_items", []) or []
    for line_item in line_items:
        line_item_id = str(line_item.get("id", ""))
        if not line_item_id:
            continue
        handle.graph.add_node(line_item_id)

        references = line_item.get("references", {}) or {}
        if isinstance(references, dict):
            for dependency in references.values():
                if dependency is None:
                    continue
                handle.graph.add_dependency(line_item_id, str(dependency))

        for cell in line_item.get("cells", []) or []:
            raw_key = cell.get("dimension_key", cell.get("dimension_members", []))
            key = _dimension_key_to_str(raw_key)
            handle.cells[(line_item_id, key)] = cell.get("value")

    dependency_edges = payload.get("dependency_edges", {}) or {}
    if isinstance(dependency_edges, dict):
        for dependent, dependencies in dependency_edges.items():
            dependent_id = str(dependent)
            if not dependent_id:
                continue
            for dependency in dependencies or []:
                handle.graph.add_dependency(dependent_id, str(dependency))

    return handle


def load_model(model_json: str) -> Any:
    if rust_engine_available():
        return _dynaplan_engine.load_model(model_json)
    return _load_python_model(model_json)


def get_or_create_model_handle(model_id: uuid.UUID) -> Any:
    model_key = str(model_id)
    with _MODEL_HANDLES_LOCK:
        existing = _MODEL_HANDLES.get(model_key)
        if existing is not None:
            return existing
        handle = load_model(json.dumps({"model_id": model_key}))
        _MODEL_HANDLES[model_key] = handle
        return handle


def clear_model_handles() -> None:
    with _MODEL_HANDLES_LOCK:
        _MODEL_HANDLES.clear()


def write_cell(
    handle: Any,
    line_item_id: Any,
    dimension_key: Any,
    value: Any,
) -> Dict[str, Any]:
    line_item_id_str = str(line_item_id)
    normalized_key = _parse_dimension_key(dimension_key)

    if rust_engine_available():
        return _dynaplan_engine.write_cell(
            handle,
            line_item_id_str,
            normalized_key,
            value,
        )

    if not isinstance(handle, _PythonModelHandle):
        raise TypeError("Python fallback expected _PythonModelHandle")

    dimension_key_str = "|".join(sorted(normalized_key))
    handle.graph.add_node(line_item_id_str)
    handle.cells[(line_item_id_str, dimension_key_str)] = value
    order = get_recalc_order(handle, [line_item_id_str])
    return _build_recalc_result(order, 1)


def write_cells_bulk(handle: Any, cells: List[Any]) -> Dict[str, Any]:
    if rust_engine_available():
        normalized_cells: List[Dict[str, Any]] = []
        for row in cells:
            line_item_id = str(_extract_row_value(row, "line_item_id"))
            raw_key = _extract_row_value(row, "dimension_key")
            if raw_key is None:
                raw_key = _extract_row_value(row, "dimension_members", [])
            normalized_cells.append(
                {
                    "line_item_id": line_item_id,
                    "dimension_key": _parse_dimension_key(raw_key),
                    "value": _extract_row_value(row, "value"),
                }
            )
        return _dynaplan_engine.write_cells_bulk(handle, normalized_cells)

    if not isinstance(handle, _PythonModelHandle):
        raise TypeError("Python fallback expected _PythonModelHandle")

    changed_line_items: Set[str] = set()
    for row in cells:
        line_item_id = str(_extract_row_value(row, "line_item_id"))
        raw_key = _extract_row_value(row, "dimension_key")
        if raw_key is None:
            raw_key = _extract_row_value(row, "dimension_members", [])
        value = _extract_row_value(row, "value")
        dimension_key_str = _dimension_key_to_str(raw_key)
        handle.graph.add_node(line_item_id)
        handle.cells[(line_item_id, dimension_key_str)] = value
        changed_line_items.add(line_item_id)

    order = get_recalc_order(handle, sorted(changed_line_items))
    return _build_recalc_result(order, len(cells))


def read_cell(handle: Any, line_item_id: Any, dimension_key: Any) -> Any:
    line_item_id_str = str(line_item_id)
    normalized_key = _parse_dimension_key(dimension_key)

    if rust_engine_available():
        return _dynaplan_engine.read_cell(handle, line_item_id_str, normalized_key)

    if not isinstance(handle, _PythonModelHandle):
        raise TypeError("Python fallback expected _PythonModelHandle")

    key = "|".join(sorted(normalized_key))
    return handle.cells.get((line_item_id_str, key))


def read_cells(
    handle: Any,
    line_item_id: Any,
    filters: Optional[Dict[str, List[uuid.UUID]]] = None,
) -> List[Any]:
    line_item_id_str = str(line_item_id)

    if rust_engine_available():
        normalized_filters: Dict[str, List[str]] = {}
        if filters:
            for key, members in filters.items():
                normalized_filters[key] = [str(member) for member in members]
        return _dynaplan_engine.read_cells(handle, line_item_id_str, normalized_filters)

    if not isinstance(handle, _PythonModelHandle):
        raise TypeError("Python fallback expected _PythonModelHandle")

    allowed_groups: List[Set[str]] = []
    if filters:
        for members in filters.values():
            allowed_groups.append({str(member) for member in members})

    values: List[Any] = []
    for (stored_line_item_id, dimension_key), cell_value in handle.cells.items():
        if stored_line_item_id != line_item_id_str:
            continue
        members = set([part for part in dimension_key.split("|") if part])
        if allowed_groups and not all(group.intersection(members) for group in allowed_groups):
            continue
        values.append(cell_value)

    return values


def evaluate_formula(text: str, context: Optional[Dict[str, Any]] = None) -> Any:
    context = context or {}
    if rust_engine_available():
        return _dynaplan_engine.evaluate_formula(text, context)
    return evaluate_formula_python(text, context)


def get_recalc_order(handle: Any, changed: Iterable[Any]) -> List[str]:
    changed_list = [str(node) for node in changed]
    if rust_engine_available():
        return list(_dynaplan_engine.get_recalc_order(handle, changed_list))

    if not isinstance(handle, _PythonModelHandle):
        raise TypeError("Python fallback expected _PythonModelHandle")

    changed_set = set(changed_list)
    if not changed_set:
        return []

    try:
        order = handle.graph.get_recalc_order(changed_set)
    except ValueError:
        order = sorted(changed_set)

    if not order:
        return sorted(changed_set)
    return order


def _normalize_spread_method(method: Any) -> SpreadMethod:
    if isinstance(method, SpreadMethod):
        return method
    if isinstance(method, str):
        return SpreadMethod(method)
    raise ValueError("spread method must be a SpreadMethod enum or string value")


def spread_top_down(
    handle: Any,
    total: float,
    member_count: int,
    method: Any,
    weights: Optional[List[float]] = None,
    existing_values: Optional[List[float]] = None,
) -> List[float]:
    method_enum = _normalize_spread_method(method)

    if (
        rust_engine_available()
        and handle is not None
        and hasattr(_dynaplan_engine, "spread_top_down")
    ):
        result = _dynaplan_engine.spread_top_down(
            handle,
            float(total),
            int(member_count),
            method_enum.value,
            weights,
            existing_values,
        )
        return list(result)

    return spread_value_python(
        total=total,
        member_count=member_count,
        method=method_enum,
        weights=weights,
        existing_values=existing_values,
    )


def aggregate_bottom_up(
    handle: Any,
    values: List[float],
    method: str,
) -> float:
    normalized_method = (method or "sum").strip().lower()
    if normalized_method in {"none", "formula"}:
        normalized_method = "sum"

    if (
        rust_engine_available()
        and handle is not None
        and hasattr(_dynaplan_engine, "aggregate_bottom_up")
    ):
        result = _dynaplan_engine.aggregate_bottom_up(
            handle,
            values,
            normalized_method,
        )
        return float(result)

    return float(aggregate_values_python(values, normalized_method))


__all__ = [
    "aggregate_bottom_up",
    "clear_model_handles",
    "evaluate_formula",
    "get_or_create_model_handle",
    "get_recalc_order",
    "load_model",
    "read_cell",
    "read_cells",
    "rust_engine_available",
    "spread_top_down",
    "write_cell",
    "write_cells_bulk",
]
