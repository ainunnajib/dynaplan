"""
Tests for F024: Scenario comparison.

Covers:
- Compare two versions with matching cells
- Compare with missing cells in one version (shows as null)
- Variance summary (abs diff, % diff, changed/unchanged counts)
- Compare with no overlapping cells
- Compare three versions simultaneously
- Filter by line_item_ids
- Matrix view for single line item
- Percentage diff when base is zero (handle division by zero)
- Auth required for all endpoints
- 404 for nonexistent model/version
- Empty comparison (no cells)
"""
import uuid

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def register_and_login(client: AsyncClient, email: str, password: str = "testpass123") -> str:
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


async def create_model(client: AsyncClient, token: str, workspace_id: str, name: str = "My Model") -> str:
    resp = await client.post(
        "/models",
        json={"name": name, "workspace_id": workspace_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_version(
    client: AsyncClient,
    token: str,
    model_id: str,
    name: str,
    version_type: str = "forecast",
) -> str:
    resp = await client.post(
        f"/models/{model_id}/versions",
        json={"name": name, "version_type": version_type},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_module(client: AsyncClient, token: str, model_id: str, name: str = "Revenue") -> str:
    resp = await client.post(
        f"/models/{model_id}/modules",
        json={"name": name},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_line_item(client: AsyncClient, token: str, module_id: str, name: str = "Revenue Item") -> str:
    resp = await client.post(
        f"/modules/{module_id}/line-items",
        json={"name": name, "format": "number"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def write_cell(
    client: AsyncClient,
    token: str,
    line_item_id: str,
    dimension_members: list,
    value: float,
) -> dict:
    resp = await client.post(
        "/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": dimension_members,
            "value": value,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    return resp.json()


async def setup_basic(client: AsyncClient, email: str):
    """Full setup: register, create workspace, model, module, line_item.
    Returns (token, model_id, module_id, line_item_id).
    """
    token = await register_and_login(client, email)
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module_id = await create_module(client, token, model_id)
    line_item_id = await create_line_item(client, token, module_id)
    return token, model_id, module_id, line_item_id


# ---------------------------------------------------------------------------
# POST /models/{model_id}/compare
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compare_two_versions_matching_cells(client: AsyncClient):
    """Compare two versions that both have cells at the same dimension intersection."""
    token, model_id, module_id, li_id = await setup_basic(client, "sc_match@example.com")

    v1_id = await create_version(client, token, model_id, "Budget 2024", "budget")
    v2_id = await create_version(client, token, model_id, "Forecast 2024", "forecast")

    # A shared non-version dimension member
    dim_key = str(uuid.uuid4())

    # Write cells: each cell contains version_id + dim_key as dimension members
    await write_cell(client, token, li_id, [v1_id, dim_key], 100.0)
    await write_cell(client, token, li_id, [v2_id, dim_key], 150.0)

    resp = await client.post(
        f"/models/{model_id}/compare",
        json={"version_ids": [v1_id, v2_id]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "rows" in data
    assert "version_names" in data
    assert data["version_names"][v1_id] == "Budget 2024"
    assert data["version_names"][v2_id] == "Forecast 2024"

    # Should have exactly one row (the dim_key intersection)
    assert len(data["rows"]) == 1
    row = data["rows"][0]
    assert row["line_item_id"] == li_id
    assert row["values"][v1_id] == 100.0
    assert row["values"][v2_id] == 150.0
    assert row["absolute_diff"] == pytest.approx(50.0)
    assert row["percentage_diff"] == pytest.approx(50.0)


@pytest.mark.asyncio
async def test_compare_missing_cells_in_one_version(client: AsyncClient):
    """When one version has a cell and the other does not, value shows as null."""
    token, model_id, module_id, li_id = await setup_basic(client, "sc_missing@example.com")

    v1_id = await create_version(client, token, model_id, "V1")
    v2_id = await create_version(client, token, model_id, "V2")

    dim_key = str(uuid.uuid4())

    # Only write for v1, not v2
    await write_cell(client, token, li_id, [v1_id, dim_key], 200.0)

    resp = await client.post(
        f"/models/{model_id}/compare",
        json={"version_ids": [v1_id, v2_id]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["rows"]) == 1
    row = data["rows"][0]
    assert row["values"][v1_id] == 200.0
    assert row["values"][v2_id] is None
    # With one null value, absolute_diff and percentage_diff should be None
    assert row["absolute_diff"] is None
    assert row["percentage_diff"] is None


@pytest.mark.asyncio
async def test_compare_no_cells_empty_result(client: AsyncClient):
    """Comparing versions with no cells returns empty rows list."""
    token, model_id, module_id, li_id = await setup_basic(client, "sc_empty@example.com")

    v1_id = await create_version(client, token, model_id, "Empty V1")
    v2_id = await create_version(client, token, model_id, "Empty V2")

    resp = await client.post(
        f"/models/{model_id}/compare",
        json={"version_ids": [v1_id, v2_id]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["rows"] == []
    assert v1_id in data["version_names"]
    assert v2_id in data["version_names"]


@pytest.mark.asyncio
async def test_compare_three_versions(client: AsyncClient):
    """Compare three versions simultaneously."""
    token, model_id, module_id, li_id = await setup_basic(client, "sc_three@example.com")

    v1_id = await create_version(client, token, model_id, "Actuals", "actuals")
    v2_id = await create_version(client, token, model_id, "Budget", "budget")
    v3_id = await create_version(client, token, model_id, "Scenario", "scenario")

    dim_key = str(uuid.uuid4())

    await write_cell(client, token, li_id, [v1_id, dim_key], 100.0)
    await write_cell(client, token, li_id, [v2_id, dim_key], 120.0)
    await write_cell(client, token, li_id, [v3_id, dim_key], 90.0)

    resp = await client.post(
        f"/models/{model_id}/compare",
        json={"version_ids": [v1_id, v2_id, v3_id]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["version_names"]) == 3
    assert v1_id in data["version_names"]
    assert v2_id in data["version_names"]
    assert v3_id in data["version_names"]

    assert len(data["rows"]) == 1
    row = data["rows"][0]
    assert row["values"][v1_id] == 100.0
    assert row["values"][v2_id] == 120.0
    assert row["values"][v3_id] == 90.0
    # With 3 versions, absolute_diff and percentage_diff should be None
    assert row["absolute_diff"] is None
    assert row["percentage_diff"] is None


@pytest.mark.asyncio
async def test_compare_filter_by_line_item_ids(client: AsyncClient):
    """Filtering by line_item_ids restricts comparison to those items."""
    token, model_id, module_id, li_id_1 = await setup_basic(client, "sc_filter@example.com")
    li_id_2 = await create_line_item(client, token, module_id, "Cost Item")

    v1_id = await create_version(client, token, model_id, "Version A")
    v2_id = await create_version(client, token, model_id, "Version B")

    dim_key = str(uuid.uuid4())

    await write_cell(client, token, li_id_1, [v1_id, dim_key], 50.0)
    await write_cell(client, token, li_id_1, [v2_id, dim_key], 60.0)
    await write_cell(client, token, li_id_2, [v1_id, dim_key], 30.0)
    await write_cell(client, token, li_id_2, [v2_id, dim_key], 40.0)

    # Filter to only li_id_1
    resp = await client.post(
        f"/models/{model_id}/compare",
        json={"version_ids": [v1_id, v2_id], "line_item_ids": [li_id_1]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()

    li_ids_in_rows = {row["line_item_id"] for row in data["rows"]}
    assert li_id_1 in li_ids_in_rows
    assert li_id_2 not in li_ids_in_rows


@pytest.mark.asyncio
async def test_compare_no_overlapping_cells(client: AsyncClient):
    """When no cells exist for both versions at same keys, each version has its own rows."""
    token, model_id, module_id, li_id = await setup_basic(client, "sc_nooverlap@example.com")

    v1_id = await create_version(client, token, model_id, "V1")
    v2_id = await create_version(client, token, model_id, "V2")

    dim_key_a = str(uuid.uuid4())
    dim_key_b = str(uuid.uuid4())

    # v1 has one key, v2 has a completely different key
    await write_cell(client, token, li_id, [v1_id, dim_key_a], 11.0)
    await write_cell(client, token, li_id, [v2_id, dim_key_b], 22.0)

    resp = await client.post(
        f"/models/{model_id}/compare",
        json={"version_ids": [v1_id, v2_id]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()

    # Should have 2 rows (one for each unique base key)
    assert len(data["rows"]) == 2

    # Each row has null for the version that lacks a cell at that key
    for row in data["rows"]:
        values = row["values"]
        v1_val = values.get(v1_id)
        v2_val = values.get(v2_id)
        # At least one is non-null, the other is null
        assert not (v1_val is not None and v2_val is not None), (
            "Both cannot be non-null since no overlap"
        )


@pytest.mark.asyncio
async def test_compare_percentage_diff_base_zero(client: AsyncClient):
    """When base version value is zero, percentage_diff should be None."""
    token, model_id, module_id, li_id = await setup_basic(client, "sc_zero@example.com")

    v1_id = await create_version(client, token, model_id, "Zero Base")
    v2_id = await create_version(client, token, model_id, "Compare")

    dim_key = str(uuid.uuid4())

    await write_cell(client, token, li_id, [v1_id, dim_key], 0.0)
    await write_cell(client, token, li_id, [v2_id, dim_key], 100.0)

    resp = await client.post(
        f"/models/{model_id}/compare",
        json={"version_ids": [v1_id, v2_id]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["rows"]) == 1
    row = data["rows"][0]
    assert row["values"][v1_id] == 0.0
    assert row["values"][v2_id] == 100.0
    assert row["absolute_diff"] == pytest.approx(100.0)
    # percentage_diff must be None because base is zero
    assert row["percentage_diff"] is None


@pytest.mark.asyncio
async def test_compare_requires_auth(client: AsyncClient):
    """Comparison endpoint requires JWT authentication."""
    token, model_id, _, _ = await setup_basic(client, "sc_auth_cmp@example.com")
    v1_id = await create_version(client, token, model_id, "V1 Auth")
    v2_id = await create_version(client, token, model_id, "V2 Auth")

    resp = await client.post(
        f"/models/{model_id}/compare",
        json={"version_ids": [v1_id, v2_id]},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_compare_nonexistent_model(client: AsyncClient):
    """Comparison with a nonexistent model_id returns 404."""
    token = await register_and_login(client, "sc_404_model@example.com")
    fake_model_id = str(uuid.uuid4())
    fake_v1 = str(uuid.uuid4())
    fake_v2 = str(uuid.uuid4())

    resp = await client.post(
        f"/models/{fake_model_id}/compare",
        json={"version_ids": [fake_v1, fake_v2]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_compare_nonexistent_version(client: AsyncClient):
    """Comparison with a nonexistent version_id returns 404."""
    token, model_id, _, _ = await setup_basic(client, "sc_404_ver@example.com")
    fake_v1 = str(uuid.uuid4())
    fake_v2 = str(uuid.uuid4())

    resp = await client.post(
        f"/models/{model_id}/compare",
        json={"version_ids": [fake_v1, fake_v2]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_compare_multiple_line_items(client: AsyncClient):
    """Comparison returns rows for all line items in the model."""
    token, model_id, module_id, li_id_1 = await setup_basic(client, "sc_multi_li@example.com")
    li_id_2 = await create_line_item(client, token, module_id, "Expenses")

    v1_id = await create_version(client, token, model_id, "V1")
    v2_id = await create_version(client, token, model_id, "V2")

    dim_key = str(uuid.uuid4())

    await write_cell(client, token, li_id_1, [v1_id, dim_key], 500.0)
    await write_cell(client, token, li_id_1, [v2_id, dim_key], 600.0)
    await write_cell(client, token, li_id_2, [v1_id, dim_key], 200.0)
    await write_cell(client, token, li_id_2, [v2_id, dim_key], 250.0)

    resp = await client.post(
        f"/models/{model_id}/compare",
        json={"version_ids": [v1_id, v2_id]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()

    li_ids_in_rows = {row["line_item_id"] for row in data["rows"]}
    assert li_id_1 in li_ids_in_rows
    assert li_id_2 in li_ids_in_rows


# ---------------------------------------------------------------------------
# POST /models/{model_id}/compare/variance
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_variance_summary_basic(client: AsyncClient):
    """Variance summary returns correct stats for two versions."""
    token, model_id, module_id, li_id = await setup_basic(client, "sc_var_basic@example.com")

    v1_id = await create_version(client, token, model_id, "Base Version")
    v2_id = await create_version(client, token, model_id, "Compare Version")

    dim_a = str(uuid.uuid4())
    dim_b = str(uuid.uuid4())

    # Cell 1: 100 -> 120 (changed, diff=20, pct=20%)
    await write_cell(client, token, li_id, [v1_id, dim_a], 100.0)
    await write_cell(client, token, li_id, [v2_id, dim_a], 120.0)
    # Cell 2: 50 -> 50 (unchanged)
    await write_cell(client, token, li_id, [v1_id, dim_b], 50.0)
    await write_cell(client, token, li_id, [v2_id, dim_b], 50.0)

    resp = await client.post(
        f"/models/{model_id}/compare/variance",
        json={"base_version_id": v1_id, "compare_version_id": v2_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_cells"] == 2
    assert data["changed_cells"] == 1
    assert data["unchanged_cells"] == 1
    assert data["total_absolute_diff"] == pytest.approx(20.0)
    assert data["avg_percentage_diff"] == pytest.approx(20.0)


@pytest.mark.asyncio
async def test_variance_summary_all_unchanged(client: AsyncClient):
    """Variance summary when all cells are identical between versions."""
    token, model_id, module_id, li_id = await setup_basic(client, "sc_var_same@example.com")

    v1_id = await create_version(client, token, model_id, "Base")
    v2_id = await create_version(client, token, model_id, "Compare")

    dim_key = str(uuid.uuid4())

    await write_cell(client, token, li_id, [v1_id, dim_key], 75.0)
    await write_cell(client, token, li_id, [v2_id, dim_key], 75.0)

    resp = await client.post(
        f"/models/{model_id}/compare/variance",
        json={"base_version_id": v1_id, "compare_version_id": v2_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["changed_cells"] == 0
    assert data["unchanged_cells"] == 1
    assert data["total_absolute_diff"] == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_variance_summary_no_cells(client: AsyncClient):
    """Variance summary returns zeros when there are no cells."""
    token, model_id, _, _ = await setup_basic(client, "sc_var_empty@example.com")

    v1_id = await create_version(client, token, model_id, "Base Empty")
    v2_id = await create_version(client, token, model_id, "Compare Empty")

    resp = await client.post(
        f"/models/{model_id}/compare/variance",
        json={"base_version_id": v1_id, "compare_version_id": v2_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_cells"] == 0
    assert data["changed_cells"] == 0
    assert data["unchanged_cells"] == 0
    assert data["total_absolute_diff"] == pytest.approx(0.0)
    assert data["avg_percentage_diff"] is None


@pytest.mark.asyncio
async def test_variance_summary_requires_auth(client: AsyncClient):
    """Variance summary endpoint requires JWT authentication."""
    token, model_id, _, _ = await setup_basic(client, "sc_var_auth@example.com")
    v1_id = await create_version(client, token, model_id, "V1 Auth")
    v2_id = await create_version(client, token, model_id, "V2 Auth")

    resp = await client.post(
        f"/models/{model_id}/compare/variance",
        json={"base_version_id": v1_id, "compare_version_id": v2_id},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_variance_summary_not_found(client: AsyncClient):
    """Variance summary with nonexistent versions returns 404."""
    token, model_id, _, _ = await setup_basic(client, "sc_var_404@example.com")
    fake_v1 = str(uuid.uuid4())
    fake_v2 = str(uuid.uuid4())

    resp = await client.post(
        f"/models/{model_id}/compare/variance",
        json={"base_version_id": fake_v1, "compare_version_id": fake_v2},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /models/{model_id}/compare/matrix
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_matrix_basic(client: AsyncClient):
    """Matrix view returns correct structure for a single line item."""
    token, model_id, module_id, li_id = await setup_basic(client, "sc_matrix@example.com")

    v1_id = await create_version(client, token, model_id, "Matrix V1")
    v2_id = await create_version(client, token, model_id, "Matrix V2")

    dim_a = str(uuid.uuid4())
    dim_b = str(uuid.uuid4())

    await write_cell(client, token, li_id, [v1_id, dim_a], 10.0)
    await write_cell(client, token, li_id, [v2_id, dim_a], 20.0)
    await write_cell(client, token, li_id, [v1_id, dim_b], 30.0)
    await write_cell(client, token, li_id, [v2_id, dim_b], 40.0)

    resp = await client.post(
        f"/models/{model_id}/compare/matrix",
        json={"version_ids": [v1_id, v2_id], "line_item_id": li_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["line_item_id"] == li_id
    assert v1_id in data["version_names"]
    assert v2_id in data["version_names"]
    assert len(data["dimension_keys"]) == 2
    assert len(data["matrix"]) == 2

    # Each dimension_key should have values for both versions
    for dim_key, version_vals in data["matrix"].items():
        assert v1_id in version_vals
        assert v2_id in version_vals


@pytest.mark.asyncio
async def test_matrix_empty(client: AsyncClient):
    """Matrix view with no cells returns empty matrix."""
    token, model_id, module_id, li_id = await setup_basic(client, "sc_matrix_empty@example.com")

    v1_id = await create_version(client, token, model_id, "ME V1")
    v2_id = await create_version(client, token, model_id, "ME V2")

    resp = await client.post(
        f"/models/{model_id}/compare/matrix",
        json={"version_ids": [v1_id, v2_id], "line_item_id": li_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["line_item_id"] == li_id
    assert data["dimension_keys"] == []
    assert data["matrix"] == {}


@pytest.mark.asyncio
async def test_matrix_requires_auth(client: AsyncClient):
    """Matrix endpoint requires JWT authentication."""
    token, model_id, module_id, li_id = await setup_basic(client, "sc_matrix_auth@example.com")
    v1_id = await create_version(client, token, model_id, "MA V1")
    v2_id = await create_version(client, token, model_id, "MA V2")

    resp = await client.post(
        f"/models/{model_id}/compare/matrix",
        json={"version_ids": [v1_id, v2_id], "line_item_id": li_id},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_matrix_not_found(client: AsyncClient):
    """Matrix endpoint with nonexistent model or versions returns 404."""
    token = await register_and_login(client, "sc_matrix_404@example.com")
    fake_model_id = str(uuid.uuid4())
    fake_v1 = str(uuid.uuid4())
    fake_v2 = str(uuid.uuid4())
    fake_li = str(uuid.uuid4())

    resp = await client.post(
        f"/models/{fake_model_id}/compare/matrix",
        json={"version_ids": [fake_v1, fake_v2], "line_item_id": fake_li},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_compare_response_includes_line_item_name(client: AsyncClient):
    """ComparisonRow includes the line item name."""
    token, model_id, module_id, li_id = await setup_basic(client, "sc_li_name@example.com")

    v1_id = await create_version(client, token, model_id, "V1 Name")
    v2_id = await create_version(client, token, model_id, "V2 Name")

    dim_key = str(uuid.uuid4())
    await write_cell(client, token, li_id, [v1_id, dim_key], 77.0)
    await write_cell(client, token, li_id, [v2_id, dim_key], 88.0)

    resp = await client.post(
        f"/models/{model_id}/compare",
        json={"version_ids": [v1_id, v2_id]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["rows"]) == 1
    row = data["rows"][0]
    assert row["line_item_name"] == "Revenue Item"


@pytest.mark.asyncio
async def test_compare_negative_absolute_diff(client: AsyncClient):
    """Absolute diff is negative when compare version is less than base."""
    token, model_id, module_id, li_id = await setup_basic(client, "sc_neg_diff@example.com")

    v1_id = await create_version(client, token, model_id, "High Base")
    v2_id = await create_version(client, token, model_id, "Low Compare")

    dim_key = str(uuid.uuid4())
    await write_cell(client, token, li_id, [v1_id, dim_key], 200.0)
    await write_cell(client, token, li_id, [v2_id, dim_key], 100.0)

    resp = await client.post(
        f"/models/{model_id}/compare",
        json={"version_ids": [v1_id, v2_id]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()

    row = data["rows"][0]
    assert row["absolute_diff"] == pytest.approx(-100.0)
    assert row["percentage_diff"] == pytest.approx(-50.0)


@pytest.mark.asyncio
async def test_variance_summary_with_line_item_filter(client: AsyncClient):
    """Variance summary respects the line_item_ids filter."""
    token, model_id, module_id, li_id_1 = await setup_basic(client, "sc_var_filter@example.com")
    li_id_2 = await create_line_item(client, token, module_id, "Another Item")

    v1_id = await create_version(client, token, model_id, "Base Filter")
    v2_id = await create_version(client, token, model_id, "Compare Filter")

    dim_key = str(uuid.uuid4())

    # li_1: changed (100 -> 200)
    await write_cell(client, token, li_id_1, [v1_id, dim_key], 100.0)
    await write_cell(client, token, li_id_1, [v2_id, dim_key], 200.0)
    # li_2: unchanged (50 -> 50)
    await write_cell(client, token, li_id_2, [v1_id, dim_key], 50.0)
    await write_cell(client, token, li_id_2, [v2_id, dim_key], 50.0)

    # Filter to only li_id_1
    resp = await client.post(
        f"/models/{model_id}/compare/variance",
        json={
            "base_version_id": v1_id,
            "compare_version_id": v2_id,
            "line_item_ids": [li_id_1],
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()

    # Only li_1's cells are counted
    assert data["total_cells"] == 1
    assert data["changed_cells"] == 1
    assert data["unchanged_cells"] == 0
    assert data["total_absolute_diff"] == pytest.approx(100.0)
