"""
Tests for F025: Top-down & bottom-up planning.

Covers:
- Engine: even spread, proportional spread, weighted spread, manual spread
- Engine: aggregate sum, average, min, max, count
- Engine: compute_proportions edge cases
- Service/API: spread top-down and verify cells written
- Service/API: aggregate bottom-up and verify parent cell
- Service/API: hierarchy values retrieval
- Spread with zero existing values (proportional fallback to even)
- Division edge cases (zero total, single member)
- Bulk spread
- Auth required
- 404 for nonexistent line items/dimension members
"""
import uuid

import pytest
from httpx import AsyncClient

from app.engine.spread import (
    SpreadMethod,
    aggregate_values,
    compute_proportions,
    spread_value,
)


# ---------------------------------------------------------------------------
# Helpers
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
    client: AsyncClient,
    token: str,
    module_id: str,
    name: str = "Revenue",
    summary_method: str = "sum",
) -> str:
    resp = await client.post(
        f"/modules/{module_id}/line-items",
        json={"name": name, "format": "number", "summary_method": summary_method},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_dimension(
    client: AsyncClient,
    token: str,
    model_id: str,
    name: str = "Regions",
) -> dict:
    resp = await client.post(
        f"/models/{model_id}/dimensions",
        json={"name": name, "dimension_type": "custom"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def create_item(
    client: AsyncClient,
    token: str,
    dimension_id: str,
    name: str,
    code: str,
    parent_id: str = None,
) -> dict:
    payload = {"name": name, "code": code, "sort_order": 0}
    if parent_id is not None:
        payload["parent_id"] = parent_id
    resp = await client.post(
        f"/dimensions/{dimension_id}/items",
        json=payload,
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def write_cell(
    client: AsyncClient,
    token: str,
    line_item_id: str,
    member_id: str,
    value: float,
) -> dict:
    resp = await client.post(
        "/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": [member_id],
            "value": value,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    return resp.json()


async def setup_hierarchy(client: AsyncClient, email_suffix: str, summary_method: str = "sum"):
    """Create a full setup: user, workspace, model, module, line item, dimension,
    parent item, and two child items.

    Returns: (token, line_item_id, dimension_id, parent_item, child1, child2)
    """
    token = await register_and_login(client, f"plan_{email_suffix}@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module_id = await create_module(client, token, model_id)
    line_item_id = await create_line_item(client, token, module_id, summary_method=summary_method)
    dim = await create_dimension(client, token, model_id)
    dim_id = dim["id"]

    parent = await create_item(client, token, dim_id, "Americas", "AMER")
    child1 = await create_item(client, token, dim_id, "USA", "USA", parent_id=parent["id"])
    child2 = await create_item(client, token, dim_id, "Canada", "CAN", parent_id=parent["id"])

    return token, line_item_id, dim_id, parent, child1, child2


# ---------------------------------------------------------------------------
# Engine unit tests — no HTTP
# ---------------------------------------------------------------------------

def test_spread_even():
    """Even spread divides total equally."""
    result = spread_value(total=120.0, member_count=3, method=SpreadMethod.even)
    assert len(result) == 3
    assert all(v == 40.0 for v in result)


def test_spread_even_single_member():
    """Even spread with one member returns total."""
    result = spread_value(total=100.0, member_count=1, method=SpreadMethod.even)
    assert result == [100.0]


def test_spread_even_zero_total():
    """Even spread with zero total returns zeros."""
    result = spread_value(total=0.0, member_count=4, method=SpreadMethod.even)
    assert result == [0.0, 0.0, 0.0, 0.0]


def test_spread_even_no_members():
    """Even spread with zero members returns empty list."""
    result = spread_value(total=100.0, member_count=0, method=SpreadMethod.even)
    assert result == []


def test_spread_proportional():
    """Proportional spread distributes based on existing ratios."""
    existing = [10.0, 30.0, 60.0]
    result = spread_value(
        total=200.0,
        member_count=3,
        method=SpreadMethod.proportional,
        existing_values=existing,
    )
    assert len(result) == 3
    assert abs(result[0] - 20.0) < 1e-9
    assert abs(result[1] - 60.0) < 1e-9
    assert abs(result[2] - 120.0) < 1e-9
    assert abs(sum(result) - 200.0) < 1e-9


def test_spread_proportional_zero_existing_fallback_to_even():
    """Proportional with all-zero existing values falls back to even spread."""
    existing = [0.0, 0.0, 0.0]
    result = spread_value(
        total=90.0,
        member_count=3,
        method=SpreadMethod.proportional,
        existing_values=existing,
    )
    assert len(result) == 3
    assert all(abs(v - 30.0) < 1e-9 for v in result)


def test_spread_proportional_no_existing_fallback_to_even():
    """Proportional with no existing_values provided falls back to even."""
    result = spread_value(
        total=60.0,
        member_count=2,
        method=SpreadMethod.proportional,
    )
    assert result == [30.0, 30.0]


def test_spread_weighted():
    """Weighted spread distributes based on weight ratios."""
    weights = [1.0, 2.0, 1.0]
    result = spread_value(
        total=80.0,
        member_count=3,
        method=SpreadMethod.weighted,
        weights=weights,
    )
    assert len(result) == 3
    assert abs(result[0] - 20.0) < 1e-9
    assert abs(result[1] - 40.0) < 1e-9
    assert abs(result[2] - 20.0) < 1e-9


def test_spread_weighted_zero_weights_fallback_to_even():
    """Weighted spread with all-zero weights falls back to even."""
    weights = [0.0, 0.0, 0.0]
    result = spread_value(
        total=30.0,
        member_count=3,
        method=SpreadMethod.weighted,
        weights=weights,
    )
    assert all(abs(v - 10.0) < 1e-9 for v in result)


def test_spread_manual():
    """Manual spread returns existing values unchanged."""
    existing = [10.0, 25.0, 65.0]
    result = spread_value(
        total=999.0,  # total is ignored for manual
        member_count=3,
        method=SpreadMethod.manual,
        existing_values=existing,
    )
    assert result == [10.0, 25.0, 65.0]


def test_spread_manual_no_existing():
    """Manual spread with no existing values returns zeros."""
    result = spread_value(
        total=100.0,
        member_count=3,
        method=SpreadMethod.manual,
    )
    assert result == [0.0, 0.0, 0.0]


def test_aggregate_sum():
    assert aggregate_values([10.0, 20.0, 30.0], "sum") == 60.0


def test_aggregate_average():
    assert abs(aggregate_values([10.0, 20.0, 30.0], "average") - 20.0) < 1e-9


def test_aggregate_min():
    assert aggregate_values([10.0, 20.0, 5.0], "min") == 5.0


def test_aggregate_max():
    assert aggregate_values([10.0, 20.0, 5.0], "max") == 20.0


def test_aggregate_count():
    assert aggregate_values([1.0, 2.0, 3.0, 4.0], "count") == 4.0


def test_aggregate_first():
    assert aggregate_values([7.0, 2.0, 9.0], "first") == 7.0


def test_aggregate_last():
    assert aggregate_values([7.0, 2.0, 9.0], "last") == 9.0


def test_aggregate_opening_balance():
    assert aggregate_values([7.0, 2.0, 9.0], "opening_balance") == 7.0


def test_aggregate_closing_balance():
    assert aggregate_values([7.0, 2.0, 9.0], "closing_balance") == 9.0


def test_aggregate_weighted_average_defaults_to_average():
    assert abs(aggregate_values([10.0, 20.0, 30.0], "weighted_average") - 20.0) < 1e-9


def test_aggregate_empty_list():
    assert aggregate_values([], "sum") == 0.0
    assert aggregate_values([], "count") == 0.0


def test_compute_proportions_basic():
    proportions = compute_proportions([10.0, 30.0, 60.0])
    assert len(proportions) == 3
    assert abs(proportions[0] - 0.1) < 1e-9
    assert abs(proportions[1] - 0.3) < 1e-9
    assert abs(proportions[2] - 0.6) < 1e-9
    assert abs(sum(proportions) - 1.0) < 1e-9


def test_compute_proportions_zeros():
    """All zeros should return even distribution."""
    proportions = compute_proportions([0.0, 0.0, 0.0])
    assert len(proportions) == 3
    assert all(abs(p - 1 / 3) < 1e-9 for p in proportions)


def test_compute_proportions_empty():
    assert compute_proportions([]) == []


# ---------------------------------------------------------------------------
# API integration tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_spread_top_down_even(client: AsyncClient):
    """POST /planning/spread with even method writes correct child cells."""
    token, line_item_id, dim_id, parent, child1, child2 = await setup_hierarchy(
        client, "spread_even"
    )

    resp = await client.post(
        "/planning/spread",
        json={
            "line_item_id": line_item_id,
            "parent_member_id": parent["id"],
            "target_value": 100.0,
            "method": "even",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["line_item_id"] == line_item_id
    assert len(data["cells_updated"]) == 2
    values = {c["value"] for c in data["cells_updated"]}
    assert values == {50.0}


@pytest.mark.asyncio
async def test_spread_top_down_proportional(client: AsyncClient):
    """Proportional spread distributes based on existing cell values."""
    token, line_item_id, dim_id, parent, child1, child2 = await setup_hierarchy(
        client, "spread_prop"
    )
    # Pre-write existing values: child1=25, child2=75
    await write_cell(client, token, line_item_id, child1["id"], 25.0)
    await write_cell(client, token, line_item_id, child2["id"], 75.0)

    resp = await client.post(
        "/planning/spread",
        json={
            "line_item_id": line_item_id,
            "parent_member_id": parent["id"],
            "target_value": 200.0,
            "method": "proportional",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    cells_updated = {c["member_id"]: c["value"] for c in data["cells_updated"]}
    assert abs(cells_updated[child1["id"]] - 50.0) < 1e-9
    assert abs(cells_updated[child2["id"]] - 150.0) < 1e-9


@pytest.mark.asyncio
async def test_spread_top_down_weighted(client: AsyncClient):
    """Weighted spread distributes based on supplied weights."""
    token, line_item_id, dim_id, parent, child1, child2 = await setup_hierarchy(
        client, "spread_weighted"
    )

    resp = await client.post(
        "/planning/spread",
        json={
            "line_item_id": line_item_id,
            "parent_member_id": parent["id"],
            "target_value": 300.0,
            "method": "weighted",
            "weights": [1.0, 2.0],
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    cells_updated = {c["member_id"]: c["value"] for c in data["cells_updated"]}
    # Weights [1, 2] distribute as 1/3 and 2/3 — but order depends on DB sort
    values = sorted(cells_updated.values())
    assert abs(values[0] - 100.0) < 1e-9
    assert abs(values[1] - 200.0) < 1e-9


@pytest.mark.asyncio
async def test_aggregate_bottom_up_sum(client: AsyncClient):
    """POST /planning/aggregate aggregates children and writes parent cell."""
    token, line_item_id, dim_id, parent, child1, child2 = await setup_hierarchy(
        client, "agg_sum"
    )
    await write_cell(client, token, line_item_id, child1["id"], 40.0)
    await write_cell(client, token, line_item_id, child2["id"], 60.0)

    resp = await client.post(
        "/planning/aggregate",
        json={
            "line_item_id": line_item_id,
            "parent_member_id": parent["id"],
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert abs(data["parent_value"] - 100.0) < 1e-9
    assert len(data["children_values"]) == 2


@pytest.mark.asyncio
async def test_aggregate_bottom_up_average(client: AsyncClient):
    """Aggregate with 'average' summary method."""
    token, line_item_id, dim_id, parent, child1, child2 = await setup_hierarchy(
        client, "agg_avg", summary_method="average"
    )
    await write_cell(client, token, line_item_id, child1["id"], 20.0)
    await write_cell(client, token, line_item_id, child2["id"], 80.0)

    resp = await client.post(
        "/planning/aggregate",
        json={
            "line_item_id": line_item_id,
            "parent_member_id": parent["id"],
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert abs(resp.json()["parent_value"] - 50.0) < 1e-9


@pytest.mark.asyncio
async def test_aggregate_bottom_up_first(client: AsyncClient):
    token, line_item_id, dim_id, parent, child1, child2 = await setup_hierarchy(
        client, "agg_first", summary_method="first"
    )
    await write_cell(client, token, line_item_id, child1["id"], 15.0)
    await write_cell(client, token, line_item_id, child2["id"], 85.0)

    resp = await client.post(
        "/planning/aggregate",
        json={"line_item_id": line_item_id, "parent_member_id": parent["id"]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    # Children are ordered by (sort_order, name): Canada before USA.
    assert abs(resp.json()["parent_value"] - 85.0) < 1e-9


@pytest.mark.asyncio
async def test_aggregate_bottom_up_last(client: AsyncClient):
    token, line_item_id, dim_id, parent, child1, child2 = await setup_hierarchy(
        client, "agg_last", summary_method="last"
    )
    await write_cell(client, token, line_item_id, child1["id"], 15.0)
    await write_cell(client, token, line_item_id, child2["id"], 85.0)

    resp = await client.post(
        "/planning/aggregate",
        json={"line_item_id": line_item_id, "parent_member_id": parent["id"]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert abs(resp.json()["parent_value"] - 15.0) < 1e-9


@pytest.mark.asyncio
async def test_aggregate_bottom_up_opening_balance(client: AsyncClient):
    token, line_item_id, dim_id, parent, child1, child2 = await setup_hierarchy(
        client, "agg_opening", summary_method="opening_balance"
    )
    await write_cell(client, token, line_item_id, child1["id"], 12.0)
    await write_cell(client, token, line_item_id, child2["id"], 88.0)

    resp = await client.post(
        "/planning/aggregate",
        json={"line_item_id": line_item_id, "parent_member_id": parent["id"]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert abs(resp.json()["parent_value"] - 88.0) < 1e-9


@pytest.mark.asyncio
async def test_aggregate_bottom_up_closing_balance(client: AsyncClient):
    token, line_item_id, dim_id, parent, child1, child2 = await setup_hierarchy(
        client, "agg_closing", summary_method="closing_balance"
    )
    await write_cell(client, token, line_item_id, child1["id"], 12.0)
    await write_cell(client, token, line_item_id, child2["id"], 88.0)

    resp = await client.post(
        "/planning/aggregate",
        json={"line_item_id": line_item_id, "parent_member_id": parent["id"]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert abs(resp.json()["parent_value"] - 12.0) < 1e-9


@pytest.mark.asyncio
async def test_aggregate_bottom_up_weighted_average_defaults_to_average(client: AsyncClient):
    token, line_item_id, dim_id, parent, child1, child2 = await setup_hierarchy(
        client, "agg_weighted_average", summary_method="weighted_average"
    )
    await write_cell(client, token, line_item_id, child1["id"], 20.0)
    await write_cell(client, token, line_item_id, child2["id"], 80.0)

    resp = await client.post(
        "/planning/aggregate",
        json={"line_item_id": line_item_id, "parent_member_id": parent["id"]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert abs(resp.json()["parent_value"] - 50.0) < 1e-9


@pytest.mark.asyncio
async def test_hierarchy_values_with_parent(client: AsyncClient):
    """GET /planning/hierarchy-values returns parent + children values."""
    token, line_item_id, dim_id, parent, child1, child2 = await setup_hierarchy(
        client, "hier_vals"
    )
    await write_cell(client, token, line_item_id, parent["id"], 100.0)
    await write_cell(client, token, line_item_id, child1["id"], 30.0)
    await write_cell(client, token, line_item_id, child2["id"], 70.0)

    resp = await client.get(
        "/planning/hierarchy-values",
        params={
            "line_item_id": line_item_id,
            "dimension_id": dim_id,
            "parent_member_id": parent["id"],
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["line_item_id"] == line_item_id
    assert data["parent_member_id"] == parent["id"]
    assert abs(data["parent_value"] - 100.0) < 1e-9
    assert len(data["children"]) == 2
    child_values = {c["member_id"]: c["value"] for c in data["children"]}
    assert abs(child_values[child1["id"]] - 30.0) < 1e-9
    assert abs(child_values[child2["id"]] - 70.0) < 1e-9


@pytest.mark.asyncio
async def test_hierarchy_values_no_parent(client: AsyncClient):
    """GET /planning/hierarchy-values without parent_member_id returns top-level items."""
    token, line_item_id, dim_id, parent, child1, child2 = await setup_hierarchy(
        client, "hier_top"
    )
    await write_cell(client, token, line_item_id, parent["id"], 100.0)

    resp = await client.get(
        "/planning/hierarchy-values",
        params={
            "line_item_id": line_item_id,
            "dimension_id": dim_id,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["parent_member_id"] is None
    # Top-level item is the parent (Americas)
    assert len(data["children"]) == 1
    assert data["children"][0]["member_id"] == parent["id"]


@pytest.mark.asyncio
async def test_bulk_spread(client: AsyncClient):
    """POST /planning/bulk-spread applies multiple spreads at once."""
    token, line_item_id, dim_id, parent, child1, child2 = await setup_hierarchy(
        client, "bulk_spread"
    )
    # Add a second parent with children
    parent2 = await create_item(client, token, dim_id, "Europe", "EUR")
    await create_item(client, token, dim_id, "Germany", "DE", parent_id=parent2["id"])
    await create_item(client, token, dim_id, "France", "FR", parent_id=parent2["id"])

    resp = await client.post(
        "/planning/bulk-spread",
        json={
            "spreads": [
                {
                    "line_item_id": line_item_id,
                    "parent_member_id": parent["id"],
                    "target_value": 100.0,
                    "method": "even",
                },
                {
                    "line_item_id": line_item_id,
                    "parent_member_id": parent2["id"],
                    "target_value": 200.0,
                    "method": "even",
                },
            ]
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) == 2
    # First spread: 2 children, each 50
    assert len(data["results"][0]["cells_updated"]) == 2
    # Second spread: 2 children, each 100
    assert len(data["results"][1]["cells_updated"]) == 2


@pytest.mark.asyncio
async def test_recalculate_hierarchy(client: AsyncClient):
    """POST /planning/recalculate-hierarchy computes bottom-up for entire hierarchy."""
    token, line_item_id, dim_id, parent, child1, child2 = await setup_hierarchy(
        client, "recalc"
    )
    await write_cell(client, token, line_item_id, child1["id"], 30.0)
    await write_cell(client, token, line_item_id, child2["id"], 50.0)

    resp = await client.post(
        "/planning/recalculate-hierarchy",
        json={
            "line_item_id": line_item_id,
            "dimension_id": dim_id,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["members_updated"] >= 1
    assert data["line_item_id"] == line_item_id

    # Verify the parent cell was updated to 80 (sum)
    query_resp = await client.post(
        "/cells/query",
        json={"line_item_id": line_item_id},
        headers=auth_headers(token),
    )
    cells = {c["dimension_key"]: c["value"] for c in query_resp.json()}
    parent_key = parent["id"]
    assert abs(cells[parent_key] - 80.0) < 1e-9


@pytest.mark.asyncio
async def test_spread_requires_auth(client: AsyncClient):
    """POST /planning/spread returns 401 without token."""
    resp = await client.post(
        "/planning/spread",
        json={
            "line_item_id": str(uuid.uuid4()),
            "parent_member_id": str(uuid.uuid4()),
            "target_value": 100.0,
            "method": "even",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_aggregate_requires_auth(client: AsyncClient):
    """POST /planning/aggregate returns 401 without token."""
    resp = await client.post(
        "/planning/aggregate",
        json={
            "line_item_id": str(uuid.uuid4()),
            "parent_member_id": str(uuid.uuid4()),
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_hierarchy_values_requires_auth(client: AsyncClient):
    """GET /planning/hierarchy-values returns 401 without token."""
    resp = await client.get(
        "/planning/hierarchy-values",
        params={
            "line_item_id": str(uuid.uuid4()),
            "dimension_id": str(uuid.uuid4()),
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_spread_nonexistent_line_item(client: AsyncClient):
    """POST /planning/spread returns 404 for nonexistent line item."""
    token = await register_and_login(client, "plan_404_li@example.com")
    resp = await client.post(
        "/planning/spread",
        json={
            "line_item_id": str(uuid.uuid4()),
            "parent_member_id": str(uuid.uuid4()),
            "target_value": 100.0,
            "method": "even",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_spread_nonexistent_parent_member(client: AsyncClient):
    """POST /planning/spread returns 404 for nonexistent parent dimension member."""
    token = await register_and_login(client, "plan_404_pm@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module_id = await create_module(client, token, model_id)
    line_item_id = await create_line_item(client, token, module_id)

    resp = await client.post(
        "/planning/spread",
        json={
            "line_item_id": line_item_id,
            "parent_member_id": str(uuid.uuid4()),
            "target_value": 100.0,
            "method": "even",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_aggregate_nonexistent_line_item(client: AsyncClient):
    """POST /planning/aggregate returns 404 for nonexistent line item."""
    token = await register_and_login(client, "plan_agg_404@example.com")
    resp = await client.post(
        "/planning/aggregate",
        json={
            "line_item_id": str(uuid.uuid4()),
            "parent_member_id": str(uuid.uuid4()),
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_spread_proportional_with_zero_existing_values(client: AsyncClient):
    """Proportional spread with no pre-written cells falls back to even."""
    token, line_item_id, dim_id, parent, child1, child2 = await setup_hierarchy(
        client, "prop_zero"
    )
    # No cells written — existing values are all 0

    resp = await client.post(
        "/planning/spread",
        json={
            "line_item_id": line_item_id,
            "parent_member_id": parent["id"],
            "target_value": 60.0,
            "method": "proportional",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    values = [c["value"] for c in data["cells_updated"]]
    # Fallback to even: 30 each
    assert all(abs(v - 30.0) < 1e-9 for v in values)


@pytest.mark.asyncio
async def test_bulk_spread_requires_auth(client: AsyncClient):
    """POST /planning/bulk-spread returns 401 without token."""
    resp = await client.post(
        "/planning/bulk-spread",
        json={"spreads": []},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_recalculate_hierarchy_requires_auth(client: AsyncClient):
    """POST /planning/recalculate-hierarchy returns 401 without token."""
    resp = await client.post(
        "/planning/recalculate-hierarchy",
        json={
            "line_item_id": str(uuid.uuid4()),
            "dimension_id": str(uuid.uuid4()),
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_recalculate_nonexistent_dimension(client: AsyncClient):
    """POST /planning/recalculate-hierarchy returns 404 for nonexistent dimension."""
    token = await register_and_login(client, "plan_recalc_404@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module_id = await create_module(client, token, model_id)
    line_item_id = await create_line_item(client, token, module_id)

    resp = await client.post(
        "/planning/recalculate-hierarchy",
        json={
            "line_item_id": line_item_id,
            "dimension_id": str(uuid.uuid4()),
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 404
