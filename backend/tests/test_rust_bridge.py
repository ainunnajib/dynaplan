import json
import uuid

import pytest

from app.engine import rust_bridge


@pytest.fixture(autouse=True)
def force_python_bridge(monkeypatch):
    monkeypatch.setattr(rust_bridge, "_dynaplan_engine", None)
    monkeypatch.setenv("DYNAPLAN_USE_RUST_ENGINE", "1")
    rust_bridge.clear_model_handles()
    yield
    rust_bridge.clear_model_handles()


def test_evaluate_formula_uses_python_fallback():
    assert rust_bridge.rust_engine_available() is False
    result = rust_bridge.evaluate_formula("Revenue * 0.15", {"Revenue": 1000})
    assert result == 150.0


def test_python_handle_supports_write_read_bulk_and_recalc_order():
    payload = json.dumps(
        {
            "model_id": "model-fallback",
            "line_items": [
                {"id": "A"},
                {"id": "B", "references": {"SRC": "A"}},
            ],
        }
    )
    handle = rust_bridge.load_model(payload)

    d1 = str(uuid.uuid4())
    d2 = str(uuid.uuid4())
    d3 = str(uuid.uuid4())

    single = rust_bridge.write_cell(handle, "A", [d2, d1], 10.0)
    assert single["ordered_nodes"] == ["A", "B"]
    assert rust_bridge.read_cell(handle, "A", [d1, d2]) == 10.0

    bulk = rust_bridge.write_cells_bulk(
        handle,
        [
            {"line_item_id": "A", "dimension_key": [d1, d3], "value": 20.0},
            {"line_item_id": "A", "dimension_key": [d2, d3], "value": 30.0},
        ],
    )
    assert bulk["recalculated_cells"] == 2
    assert bulk["ordered_nodes"] == ["A", "B"]

    filtered = rust_bridge.read_cells(
        handle,
        "A",
        filters={"dim_filter": [uuid.UUID(d3)]},
    )
    assert sorted(filtered) == [20.0, 30.0]

    order = rust_bridge.get_recalc_order(handle, ["A"])
    assert order == ["A", "B"]


def test_model_handle_cache_reuses_handle_for_model_id():
    model_id = uuid.uuid4()
    first = rust_bridge.get_or_create_model_handle(model_id)
    second = rust_bridge.get_or_create_model_handle(model_id)
    assert first is second
