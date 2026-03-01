"""
Tests for F008: Cell-level data storage.

Covers:
- Write single cell and read it back
- Write cell with different value types (number, text, boolean)
- Overwrite existing cell (upsert)
- Bulk write multiple cells
- Read cells for a line item
- Dimension key generation (sorted, deterministic)
- Delete cells for line item
- Auth required for all endpoints
- Dimension key uniqueness constraint
"""
import asyncio
import uuid

import pytest
from httpx import AsyncClient

from app.services.cell import make_dimension_key


# ---------------------------------------------------------------------------
# Helpers — chain through existing APIs to set up test data
# ---------------------------------------------------------------------------

async def register_and_login(
    client: AsyncClient, email: str, password: str = "testpass123"
) -> str:
    await client.post("/auth/register", json={
        "email": email,
        "full_name": "Test User",
        "password": password,
    })
    resp = await client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def create_workspace(client: AsyncClient, token: str, name: str = "Test WS") -> str:
    resp = await client.post(
        "/workspaces/",
        json={"name": name},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_model(
    client: AsyncClient, token: str, workspace_id: str, name: str = "My Model"
) -> str:
    resp = await client.post(
        "/models",
        json={"name": name, "workspace_id": workspace_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_module(
    client: AsyncClient, token: str, model_id: str, name: str = "Sales Module"
) -> str:
    resp = await client.post(
        f"/models/{model_id}/modules",
        json={"name": name},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_line_item(
    client: AsyncClient, token: str, module_id: str, name: str = "Revenue"
) -> str:
    resp = await client.post(
        f"/modules/{module_id}/line-items",
        json={"name": name, "format": "number"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def setup_line_item(client: AsyncClient, email_suffix: str) -> tuple:
    """Full setup: register, login, create workspace/model/module/line_item.
    Returns (token, line_item_id).
    """
    token = await register_and_login(client, f"cell_{email_suffix}@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module_id = await create_module(client, token, model_id)
    line_item_id = await create_line_item(client, token, module_id)
    return token, line_item_id


# ---------------------------------------------------------------------------
# Unit tests for make_dimension_key (no HTTP)
# ---------------------------------------------------------------------------

def test_dimension_key_sorted():
    """Keys must be sorted regardless of input order."""
    uid_a = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    uid_b = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    uid_c = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")

    key1 = make_dimension_key([uid_a, uid_b, uid_c])
    key2 = make_dimension_key([uid_c, uid_a, uid_b])
    key3 = make_dimension_key([uid_b, uid_c, uid_a])

    assert key1 == key2 == key3


def test_dimension_key_deterministic():
    """Same input always produces the same key."""
    uid_a = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    uid_b = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    key = make_dimension_key([uid_a, uid_b])
    assert key == make_dimension_key([uid_a, uid_b])


def test_dimension_key_pipe_separated():
    """Key should be pipe-separated UUID strings."""
    uid_a = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    uid_b = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    key = make_dimension_key([uid_b, uid_a])
    parts = key.split("|")
    assert len(parts) == 2
    assert str(uid_a) in parts
    assert str(uid_b) in parts


def test_dimension_key_single_member():
    uid = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    key = make_dimension_key([uid])
    assert key == str(uid)


def test_dimension_key_empty():
    key = make_dimension_key([])
    assert key == ""


# ---------------------------------------------------------------------------
# POST /cells — write single cell
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_cell_number(client: AsyncClient):
    token, line_item_id = await setup_line_item(client, "write_num")
    dim1 = str(uuid.uuid4())
    dim2 = str(uuid.uuid4())

    resp = await client.post(
        "/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": [dim1, dim2],
            "value": 42.5,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["value"] == 42.5
    assert data["value_type"] == "number"
    assert data["line_item_id"] == line_item_id
    assert "dimension_key" in data
    assert "dimension_members" in data


@pytest.mark.asyncio
async def test_write_cell_text(client: AsyncClient):
    token, line_item_id = await setup_line_item(client, "write_text")
    dim1 = str(uuid.uuid4())

    resp = await client.post(
        "/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": [dim1],
            "value": "hello world",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["value"] == "hello world"
    assert data["value_type"] == "text"


@pytest.mark.asyncio
async def test_write_cell_boolean(client: AsyncClient):
    token, line_item_id = await setup_line_item(client, "write_bool")
    dim1 = str(uuid.uuid4())

    resp = await client.post(
        "/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": [dim1],
            "value": True,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["value"] is True
    assert data["value_type"] == "boolean"


@pytest.mark.asyncio
async def test_write_cell_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/cells",
        json={
            "line_item_id": str(uuid.uuid4()),
            "dimension_members": [str(uuid.uuid4())],
            "value": 1.0,
        },
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Upsert behaviour — overwriting an existing cell
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_cell_upsert_same_value_type(client: AsyncClient):
    """Writing to the same cell twice updates the value."""
    token, line_item_id = await setup_line_item(client, "upsert_same")
    dim1 = str(uuid.uuid4())

    await client.post(
        "/cells",
        json={"line_item_id": line_item_id, "dimension_members": [dim1], "value": 10.0},
        headers=auth_headers(token),
    )

    resp = await client.post(
        "/cells",
        json={"line_item_id": line_item_id, "dimension_members": [dim1], "value": 99.0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["value"] == 99.0
    assert data["value_type"] == "number"


@pytest.mark.asyncio
async def test_write_cell_upsert_changes_type(client: AsyncClient):
    """Writing a text value to a cell that previously had a number."""
    token, line_item_id = await setup_line_item(client, "upsert_type")
    dim1 = str(uuid.uuid4())

    await client.post(
        "/cells",
        json={"line_item_id": line_item_id, "dimension_members": [dim1], "value": 100.0},
        headers=auth_headers(token),
    )

    resp = await client.post(
        "/cells",
        json={"line_item_id": line_item_id, "dimension_members": [dim1], "value": "new value"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["value"] == "new value"
    assert data["value_type"] == "text"


@pytest.mark.asyncio
async def test_write_cell_succeeds_when_engine_sync_fails(client: AsyncClient, monkeypatch):
    token, line_item_id = await setup_line_item(client, "engine_sync_failure")
    dim1 = str(uuid.uuid4())

    from app.services import cell as cell_service

    async def _raise_engine_error(*_args, **_kwargs):
        raise RuntimeError("engine bridge unavailable")

    monkeypatch.setattr(cell_service, "_sync_engine_after_commit", _raise_engine_error)

    resp = await client.post(
        "/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": [dim1],
            "value": 123.0,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["value"] == 123.0

    query_resp = await client.post(
        "/cells/query",
        json={"line_item_id": line_item_id},
        headers=auth_headers(token),
    )
    assert query_resp.status_code == 200
    rows = query_resp.json()
    assert len(rows) == 1
    assert rows[0]["value"] == 123.0


@pytest.mark.asyncio
async def test_write_cell_dimension_order_independent(client: AsyncClient):
    """Different orderings of dimension_members produce the same cell (same key)."""
    token, line_item_id = await setup_line_item(client, "upsert_order")
    dim1 = str(uuid.uuid4())
    dim2 = str(uuid.uuid4())

    # Write with [dim1, dim2]
    await client.post(
        "/cells",
        json={"line_item_id": line_item_id, "dimension_members": [dim1, dim2], "value": 1.0},
        headers=auth_headers(token),
    )

    # Overwrite with [dim2, dim1] — should upsert the same cell
    resp = await client.post(
        "/cells",
        json={"line_item_id": line_item_id, "dimension_members": [dim2, dim1], "value": 2.0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["value"] == 2.0

    # Query — should be exactly one cell
    q_resp = await client.post(
        "/cells/query",
        json={"line_item_id": line_item_id},
        headers=auth_headers(token),
    )
    assert q_resp.status_code == 200
    cells = q_resp.json()
    assert len(cells) == 1
    assert cells[0]["value"] == 2.0


# ---------------------------------------------------------------------------
# POST /cells/bulk — bulk write
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_cells_bulk(client: AsyncClient):
    token, line_item_id = await setup_line_item(client, "bulk_write")
    dim1 = str(uuid.uuid4())
    dim2 = str(uuid.uuid4())
    dim3 = str(uuid.uuid4())

    resp = await client.post(
        "/cells/bulk",
        json={
            "cells": [
                {"line_item_id": line_item_id, "dimension_members": [dim1], "value": 10.0},
                {"line_item_id": line_item_id, "dimension_members": [dim2], "value": 20.0},
                {"line_item_id": line_item_id, "dimension_members": [dim3], "value": 30.0},
            ]
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 3
    values = {r["value"] for r in results}
    assert values == {10.0, 20.0, 30.0}


@pytest.mark.asyncio
async def test_write_cells_bulk_upsert(client: AsyncClient):
    """Bulk write can overwrite existing cells."""
    token, line_item_id = await setup_line_item(client, "bulk_upsert")
    dim1 = str(uuid.uuid4())

    # Initial write
    await client.post(
        "/cells/bulk",
        json={"cells": [{"line_item_id": line_item_id, "dimension_members": [dim1], "value": 1.0}]},
        headers=auth_headers(token),
    )

    # Overwrite via bulk
    resp = await client.post(
        "/cells/bulk",
        json={"cells": [{"line_item_id": line_item_id, "dimension_members": [dim1], "value": 999.0}]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()[0]["value"] == 999.0


@pytest.mark.asyncio
async def test_write_cells_bulk_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/cells/bulk",
        json={"cells": [{"line_item_id": str(uuid.uuid4()), "dimension_members": [], "value": 1}]},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /cells/query — read cells
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_query_cells_all(client: AsyncClient):
    """Read all cells for a line item (no filters)."""
    token, line_item_id = await setup_line_item(client, "query_all")
    dim1 = str(uuid.uuid4())
    dim2 = str(uuid.uuid4())

    await client.post(
        "/cells/bulk",
        json={
            "cells": [
                {"line_item_id": line_item_id, "dimension_members": [dim1], "value": 1.0},
                {"line_item_id": line_item_id, "dimension_members": [dim2], "value": 2.0},
            ]
        },
        headers=auth_headers(token),
    )

    resp = await client.post(
        "/cells/query",
        json={"line_item_id": line_item_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    cells = resp.json()
    assert len(cells) == 2
    values = {c["value"] for c in cells}
    assert values == {1.0, 2.0}


@pytest.mark.asyncio
async def test_query_cells_empty(client: AsyncClient):
    """Querying a line item with no cells returns empty list."""
    token, line_item_id = await setup_line_item(client, "query_empty")

    resp = await client.post(
        "/cells/query",
        json={"line_item_id": line_item_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_query_cells_with_dimension_filter(client: AsyncClient):
    """Dimension filters narrow down results to cells that include a matching member."""
    token, line_item_id = await setup_line_item(client, "query_filter")
    dim_a = str(uuid.uuid4())
    dim_b = str(uuid.uuid4())
    dim_c = str(uuid.uuid4())

    # Write three cells at different dimension intersections
    await client.post(
        "/cells/bulk",
        json={
            "cells": [
                {"line_item_id": line_item_id, "dimension_members": [dim_a], "value": 1.0},
                {"line_item_id": line_item_id, "dimension_members": [dim_b], "value": 2.0},
                {"line_item_id": line_item_id, "dimension_members": [dim_c], "value": 3.0},
            ]
        },
        headers=auth_headers(token),
    )

    # Filter to only cells containing dim_a or dim_b
    resp = await client.post(
        "/cells/query",
        json={
            "line_item_id": line_item_id,
            "dimension_filters": {
                "filter_group": [dim_a, dim_b]
            },
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    cells = resp.json()
    assert len(cells) == 2
    values = {c["value"] for c in cells}
    assert values == {1.0, 2.0}


@pytest.mark.asyncio
async def test_query_cells_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/cells/query",
        json={"line_item_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /cells/line-item/{line_item_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_cells_for_line_item(client: AsyncClient):
    token, line_item_id = await setup_line_item(client, "delete_cells")
    dim1 = str(uuid.uuid4())
    dim2 = str(uuid.uuid4())

    # Write some cells
    await client.post(
        "/cells/bulk",
        json={
            "cells": [
                {"line_item_id": line_item_id, "dimension_members": [dim1], "value": 1.0},
                {"line_item_id": line_item_id, "dimension_members": [dim2], "value": 2.0},
            ]
        },
        headers=auth_headers(token),
    )

    # Confirm cells are there
    q_resp = await client.post(
        "/cells/query",
        json={"line_item_id": line_item_id},
        headers=auth_headers(token),
    )
    assert len(q_resp.json()) == 2

    # Delete
    del_resp = await client.delete(
        f"/cells/line-item/{line_item_id}",
        headers=auth_headers(token),
    )
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] == 2

    # Confirm cells are gone
    q_resp2 = await client.post(
        "/cells/query",
        json={"line_item_id": line_item_id},
        headers=auth_headers(token),
    )
    assert q_resp2.json() == []


@pytest.mark.asyncio
async def test_delete_cells_nonexistent_line_item_returns_zero(client: AsyncClient):
    """Deleting cells for a line item that has no cells returns 0 deleted."""
    token, _ = await setup_line_item(client, "delete_zero")
    fake_line_item_id = str(uuid.uuid4())

    resp = await client.delete(
        f"/cells/line-item/{fake_line_item_id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 0


@pytest.mark.asyncio
async def test_delete_cells_requires_auth(client: AsyncClient):
    resp = await client.delete(f"/cells/line-item/{uuid.uuid4()}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Dimension key uniqueness — only one cell per (line_item, dimension_key)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_uniqueness_one_cell_per_intersection(client: AsyncClient):
    """Writing the same cell multiple times does not create duplicate rows."""
    token, line_item_id = await setup_line_item(client, "unique_cell")
    dim1 = str(uuid.uuid4())

    for value in [1.0, 2.0, 3.0]:
        await client.post(
            "/cells",
            json={"line_item_id": line_item_id, "dimension_members": [dim1], "value": value},
            headers=auth_headers(token),
        )

    q_resp = await client.post(
        "/cells/query",
        json={"line_item_id": line_item_id},
        headers=auth_headers(token),
    )
    cells = q_resp.json()
    assert len(cells) == 1  # Only one row despite three writes
    assert cells[0]["value"] == 3.0  # Last write wins


# ---------------------------------------------------------------------------
# Read back — verify round-trip fidelity
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_read_back_number_cell(client: AsyncClient):
    token, line_item_id = await setup_line_item(client, "readback_num")
    dim1 = str(uuid.uuid4())

    await client.post(
        "/cells",
        json={"line_item_id": line_item_id, "dimension_members": [dim1], "value": 123.456},
        headers=auth_headers(token),
    )

    q_resp = await client.post(
        "/cells/query",
        json={"line_item_id": line_item_id},
        headers=auth_headers(token),
    )
    cells = q_resp.json()
    assert len(cells) == 1
    assert cells[0]["value"] == 123.456
    assert cells[0]["value_type"] == "number"
    assert cells[0]["line_item_id"] == line_item_id


@pytest.mark.asyncio
async def test_read_back_boolean_cell(client: AsyncClient):
    token, line_item_id = await setup_line_item(client, "readback_bool")
    dim1 = str(uuid.uuid4())

    await client.post(
        "/cells",
        json={"line_item_id": line_item_id, "dimension_members": [dim1], "value": False},
        headers=auth_headers(token),
    )

    q_resp = await client.post(
        "/cells/query",
        json={"line_item_id": line_item_id},
        headers=auth_headers(token),
    )
    cells = q_resp.json()
    assert len(cells) == 1
    assert cells[0]["value"] is False
    assert cells[0]["value_type"] == "boolean"


@pytest.mark.asyncio
async def test_read_back_text_cell(client: AsyncClient):
    token, line_item_id = await setup_line_item(client, "readback_text")
    dim1 = str(uuid.uuid4())

    await client.post(
        "/cells",
        json={"line_item_id": line_item_id, "dimension_members": [dim1], "value": "test string"},
        headers=auth_headers(token),
    )

    q_resp = await client.post(
        "/cells/query",
        json={"line_item_id": line_item_id},
        headers=auth_headers(token),
    )
    cells = q_resp.json()
    assert len(cells) == 1
    assert cells[0]["value"] == "test string"
    assert cells[0]["value_type"] == "text"


@pytest.mark.asyncio
async def test_cells_isolated_per_line_item(client: AsyncClient):
    """Cells from different line items do not bleed into each other."""
    token = await register_and_login(client, "cell_isolation@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module_id = await create_module(client, token, model_id)
    line_item_a = await create_line_item(client, token, module_id, name="Revenue")
    line_item_b = await create_line_item(client, token, module_id, name="Cost")

    dim1 = str(uuid.uuid4())

    # Write cell for line_item_a
    await client.post(
        "/cells",
        json={"line_item_id": line_item_a, "dimension_members": [dim1], "value": 100.0},
        headers=auth_headers(token),
    )

    # Query line_item_b — should be empty
    q_resp = await client.post(
        "/cells/query",
        json={"line_item_id": line_item_b},
        headers=auth_headers(token),
    )
    assert q_resp.json() == []


# ---------------------------------------------------------------------------
# Backpressure-focused coverage (high-volume and bursty write patterns)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.backpressure
async def test_bulk_write_large_payload_backpressure(client: AsyncClient):
    """Bulk endpoint should handle a large payload and persist all intersections."""
    token, line_item_id = await setup_line_item(client, "bp_bulk_large")
    dimension_ids = [str(uuid.uuid4()) for _ in range(250)]

    payload = {
        "cells": [
            {
                "line_item_id": line_item_id,
                "dimension_members": [dim_id],
                "value": float(i),
            }
            for i, dim_id in enumerate(dimension_ids)
        ]
    }

    resp = await client.post(
        "/cells/bulk",
        json=payload,
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 250

    q_resp = await client.post(
        "/cells/query",
        json={"line_item_id": line_item_id},
        headers=auth_headers(token),
    )
    assert q_resp.status_code == 200
    assert len(q_resp.json()) == 250


@pytest.mark.asyncio
@pytest.mark.backpressure
async def test_bulk_write_repeated_bursts_last_write_wins(client: AsyncClient):
    """Repeated bulk bursts over the same key set should remain idempotent."""
    token, line_item_id = await setup_line_item(client, "bp_bursts")
    dimension_ids = [str(uuid.uuid4()) for _ in range(120)]
    total_bursts = 4

    for burst in range(total_bursts):
        payload = {
            "cells": [
                {
                    "line_item_id": line_item_id,
                    "dimension_members": [dim_id],
                    "value": float(burst * 1000 + i),
                }
                for i, dim_id in enumerate(dimension_ids)
            ]
        }
        resp = await client.post(
            "/cells/bulk",
            json=payload,
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == len(dimension_ids)

    q_resp = await client.post(
        "/cells/query",
        json={"line_item_id": line_item_id},
        headers=auth_headers(token),
    )
    assert q_resp.status_code == 200
    cells = q_resp.json()
    assert len(cells) == len(dimension_ids)

    by_dimension_key = {cell["dimension_key"]: cell["value"] for cell in cells}
    for i, dim_id in enumerate(dimension_ids):
        assert by_dimension_key[dim_id] == float((total_bursts - 1) * 1000 + i)


@pytest.mark.asyncio
@pytest.mark.backpressure
async def test_bulk_write_hot_key_pressure_single_intersection(client: AsyncClient):
    """
    A hot-key workload (many writes to one intersection) should not create
    duplicate cell rows.
    """
    token, line_item_id = await setup_line_item(client, "bp_hot_key")
    dim_id = str(uuid.uuid4())

    payload = {
        "cells": [
            {
                "line_item_id": line_item_id,
                "dimension_members": [dim_id],
                "value": float(i),
            }
            for i in range(150)
        ]
    }

    resp = await client.post(
        "/cells/bulk",
        json=payload,
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 150

    q_resp = await client.post(
        "/cells/query",
        json={"line_item_id": line_item_id},
        headers=auth_headers(token),
    )
    assert q_resp.status_code == 200
    cells = q_resp.json()
    assert len(cells) == 1
    assert cells[0]["value"] == 149.0


@pytest.mark.asyncio
@pytest.mark.backpressure
async def test_query_large_filter_set_after_bulk_write(client: AsyncClient):
    """Large filter lists should correctly narrow results after heavy writes."""
    token, line_item_id = await setup_line_item(client, "bp_query_filter")
    dimension_ids = [str(uuid.uuid4()) for _ in range(180)]

    write_resp = await client.post(
        "/cells/bulk",
        json={
            "cells": [
                {
                    "line_item_id": line_item_id,
                    "dimension_members": [dim_id],
                    "value": float(i),
                }
                for i, dim_id in enumerate(dimension_ids)
            ]
        },
        headers=auth_headers(token),
    )
    assert write_resp.status_code == 200

    allowed_dims = dimension_ids[30:100]
    query_resp = await client.post(
        "/cells/query",
        json={
            "line_item_id": line_item_id,
            "dimension_filters": {"large_filter_group": allowed_dims},
        },
        headers=auth_headers(token),
    )
    assert query_resp.status_code == 200
    rows = query_resp.json()
    assert len(rows) == len(allowed_dims)
    assert {row["dimension_key"] for row in rows} == set(allowed_dims)


@pytest.mark.asyncio
@pytest.mark.backpressure
async def test_bulk_write_atomicity_rolls_back_on_error(client: AsyncClient, monkeypatch):
    """A failure during bulk write must not commit partial rows."""
    token, line_item_id = await setup_line_item(client, "bp_atomicity")
    dim_a = str(uuid.uuid4())
    dim_b = str(uuid.uuid4())

    from app.services import cell as cell_service

    original_extract = cell_service._extract_value_and_type

    def _boom_on_marker(value):
        if value == "__force_error__":
            raise RuntimeError("forced bulk write failure")
        return original_extract(value)

    monkeypatch.setattr(cell_service, "_extract_value_and_type", _boom_on_marker)

    with pytest.raises(RuntimeError, match="forced bulk write failure"):
        await client.post(
            "/cells/bulk",
            json={
                "cells": [
                    {
                        "line_item_id": line_item_id,
                        "dimension_members": [dim_a],
                        "value": 111.0,
                    },
                    {
                        "line_item_id": line_item_id,
                        "dimension_members": [dim_b],
                        "value": "__force_error__",
                    },
                ]
            },
            headers=auth_headers(token),
        )

    q_resp = await client.post(
        "/cells/query",
        json={"line_item_id": line_item_id},
        headers=auth_headers(token),
    )
    assert q_resp.status_code == 200
    assert q_resp.json() == []


@pytest.mark.asyncio
@pytest.mark.backpressure
async def test_concurrent_bulk_writes_disjoint_sets(client: AsyncClient):
    """Concurrent bulk writes with disjoint keys should preserve all rows."""
    token, line_item_id = await setup_line_item(client, "bp_concurrent_disjoint")
    worker_count = 4
    batch_size = 40

    async def _write_batch(worker_idx: int):
        dims = [str(uuid.uuid4()) for _ in range(batch_size)]
        return await client.post(
            "/cells/bulk",
            json={
                "cells": [
                    {
                        "line_item_id": line_item_id,
                        "dimension_members": [dim],
                        "value": float(worker_idx * 1000 + i),
                    }
                    for i, dim in enumerate(dims)
                ]
            },
            headers=auth_headers(token),
        )

    responses = await asyncio.gather(*[_write_batch(i) for i in range(worker_count)])
    assert all(resp.status_code == 200 for resp in responses)

    q_resp = await client.post(
        "/cells/query",
        json={"line_item_id": line_item_id},
        headers=auth_headers(token),
    )
    assert q_resp.status_code == 200
    assert len(q_resp.json()) == worker_count * batch_size


@pytest.mark.asyncio
@pytest.mark.backpressure
@pytest.mark.xfail(
    reason="In-memory SQLite StaticPool cannot reliably emulate same-key concurrent writes",
    strict=False,
)
async def test_concurrent_writes_same_intersection_single_row(client: AsyncClient):
    """
    Concurrent writes to one intersection should keep one persisted row.

    In-memory SQLite (single shared connection in tests) can raise transient
    concurrency exceptions under intense overlap. This test still verifies
    consistency of persisted data after the burst.
    """
    token, line_item_id = await setup_line_item(client, "bp_concurrent_hot")
    dim = str(uuid.uuid4())
    values = [float(i) for i in range(30)]

    async def _write_value(v: float):
        return await client.post(
            "/cells",
            json={
                "line_item_id": line_item_id,
                "dimension_members": [dim],
                "value": v,
            },
            headers=auth_headers(token),
        )

    responses = await asyncio.gather(*[_write_value(v) for v in values], return_exceptions=True)
    successful = [resp for resp in responses if not isinstance(resp, Exception)]
    assert successful, "Expected at least one successful write under contention"
    assert all(resp.status_code == 200 for resp in successful)

    q_resp = await client.post(
        "/cells/query",
        json={"line_item_id": line_item_id},
        headers=auth_headers(token),
    )
    assert q_resp.status_code == 200
    rows = q_resp.json()
    assert len(rows) == 1
    assert rows[0]["value"] in values
