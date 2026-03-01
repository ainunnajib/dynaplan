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


def test_spread_top_down_python_fallback_supports_core_methods():
    even = rust_bridge.spread_top_down(
        handle=None,
        total=90.0,
        member_count=3,
        method="even",
    )
    assert even == [30.0, 30.0, 30.0]

    proportional = rust_bridge.spread_top_down(
        handle=None,
        total=200.0,
        member_count=2,
        method="proportional",
        existing_values=[25.0, 75.0],
    )
    assert proportional == [50.0, 150.0]


def test_aggregate_bottom_up_python_fallback_normalizes_none_and_formula():
    values = [10.0, 20.0, 30.0]
    assert rust_bridge.aggregate_bottom_up(None, values, "none") == 60.0
    assert rust_bridge.aggregate_bottom_up(None, values, "formula") == 60.0
    assert rust_bridge.aggregate_bottom_up(None, values, "average") == 20.0


def test_f050_bridge_methods_delegate_to_native_module_when_available(monkeypatch):
    class NativeStub:
        def __init__(self):
            self.spread_calls = []
            self.aggregate_calls = []

        def spread_top_down(
            self,
            handle,
            total,
            member_count,
            method,
            weights,
            existing_values,
        ):
            self.spread_calls.append(
                (handle, total, member_count, method, weights, existing_values)
            )
            return [11.0, 22.0]

        def aggregate_bottom_up(self, handle, values, method):
            self.aggregate_calls.append((handle, values, method))
            return 33.0

    native = NativeStub()
    monkeypatch.setattr(rust_bridge, "_dynaplan_engine", native)

    handle = object()
    spread = rust_bridge.spread_top_down(
        handle=handle,
        total=100.0,
        member_count=2,
        method="weighted",
        weights=[1.0, 3.0],
    )
    aggregated = rust_bridge.aggregate_bottom_up(
        handle=handle,
        values=[5.0, 10.0],
        method="sum",
    )

    assert spread == [11.0, 22.0]
    assert aggregated == 33.0
    assert native.spread_calls == [
        (handle, 100.0, 2, "weighted", [1.0, 3.0], None)
    ]
    assert native.aggregate_calls == [(handle, [5.0, 10.0], "sum")]
