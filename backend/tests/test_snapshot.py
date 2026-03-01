"""
Tests for F030: Model history & snapshots.
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


async def setup_model(client: AsyncClient, email: str) -> tuple:
    """Register user, create workspace + model. Returns (token, ws_id, model_id)."""
    token = await register_and_login(client, email)
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    return token, ws_id, model_id


async def create_dimension(
    client: AsyncClient, token: str, model_id: str, name: str = "Products"
) -> dict:
    resp = await client.post(
        f"/models/{model_id}/dimensions",
        json={"name": name, "dimension_type": "custom"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def create_dimension_item(
    client: AsyncClient, token: str, dimension_id: str, name: str = "Item A", code: str = "A"
) -> dict:
    resp = await client.post(
        f"/dimensions/{dimension_id}/items",
        json={"name": name, "code": code, "sort_order": 0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def create_module(
    client: AsyncClient, token: str, model_id: str, name: str = "Revenue"
) -> dict:
    resp = await client.post(
        f"/models/{model_id}/modules",
        json={"name": name},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def create_line_item(
    client: AsyncClient, token: str, module_id: str, name: str = "Sales"
) -> dict:
    resp = await client.post(
        f"/modules/{module_id}/line-items",
        json={"name": name, "format": "number"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def create_version(
    client: AsyncClient, token: str, model_id: str, name: str = "Budget 2024"
) -> dict:
    resp = await client.post(
        f"/models/{model_id}/versions",
        json={"name": name, "version_type": "budget"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def create_snapshot(
    client: AsyncClient, token: str, model_id: str, name: str = "Snapshot 1", description: str = None
) -> dict:
    payload = {"name": name}
    if description is not None:
        payload["description"] = description
    resp = await client.post(
        f"/models/{model_id}/snapshots",
        json=payload,
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Create snapshot
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_snapshot_empty_model(client: AsyncClient):
    """Snapshot of an empty model should succeed and capture empty data."""
    token, ws_id, model_id = await setup_model(client, "snap_empty@example.com")

    resp = await client.post(
        f"/models/{model_id}/snapshots",
        json={"name": "Empty Snapshot"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Empty Snapshot"
    assert data["model_id"] == model_id
    assert "id" in data
    assert "created_at" in data
    assert "created_by" in data
    # Metadata response should NOT include snapshot_data
    assert "snapshot_data" not in data


@pytest.mark.asyncio
async def test_create_snapshot_with_description(client: AsyncClient):
    token, ws_id, model_id = await setup_model(client, "snap_desc@example.com")

    resp = await client.post(
        f"/models/{model_id}/snapshots",
        json={"name": "Described", "description": "Before major change"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["description"] == "Before major change"


@pytest.mark.asyncio
async def test_create_snapshot_captures_model_state(client: AsyncClient):
    """Snapshot should include serialized dimensions, modules, etc."""
    token, ws_id, model_id = await setup_model(client, "snap_state@example.com")

    # Populate model
    await create_dimension(client, token, model_id, name="Regions")
    await create_module(client, token, model_id, name="Revenue")

    snap = await create_snapshot(client, token, model_id, "Full State")

    # Get the snapshot detail to verify data was captured
    resp = await client.get(f"/snapshots/{snap['id']}", headers=auth_headers(token))
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["snapshot_data"] is not None
    assert len(detail["snapshot_data"]["dimensions"]) == 1
    assert detail["snapshot_data"]["dimensions"][0]["name"] == "Regions"
    assert len(detail["snapshot_data"]["modules"]) == 1
    assert detail["snapshot_data"]["modules"][0]["name"] == "Revenue"


@pytest.mark.asyncio
async def test_create_snapshot_requires_auth(client: AsyncClient):
    token, ws_id, model_id = await setup_model(client, "snap_auth_create@example.com")

    resp = await client.post(
        f"/models/{model_id}/snapshots",
        json={"name": "No Auth"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_snapshot_with_full_model_data(client: AsyncClient):
    """Snapshot with dimensions, items, modules, line items, versions, cells."""
    token, ws_id, model_id = await setup_model(client, "snap_full@example.com")

    dim = await create_dimension(client, token, model_id, name="Products")
    await create_dimension_item(client, token, dim["id"], name="Widget A", code="WA")
    mod = await create_module(client, token, model_id, name="Sales")
    await create_line_item(client, token, mod["id"], name="Revenue")
    await create_version(client, token, model_id, name="Budget 2024")

    snap = await create_snapshot(client, token, model_id, "Full Model")

    resp = await client.get(f"/snapshots/{snap['id']}", headers=auth_headers(token))
    detail = resp.json()

    assert len(detail["snapshot_data"]["dimensions"]) == 1
    assert len(detail["snapshot_data"]["dimension_items"]) == 1
    assert len(detail["snapshot_data"]["modules"]) == 1
    assert len(detail["snapshot_data"]["line_items"]) == 1
    assert len(detail["snapshot_data"]["versions"]) == 1


# ---------------------------------------------------------------------------
# List snapshots
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_snapshots_empty(client: AsyncClient):
    token, ws_id, model_id = await setup_model(client, "snap_list_empty@example.com")

    resp = await client.get(
        f"/models/{model_id}/snapshots",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_snapshots_metadata_only(client: AsyncClient):
    """List endpoint must return metadata only — no snapshot_data field."""
    token, ws_id, model_id = await setup_model(client, "snap_list_meta@example.com")
    await create_dimension(client, token, model_id, name="Dim1")
    await create_snapshot(client, token, model_id, "S1")

    resp = await client.get(
        f"/models/{model_id}/snapshots",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    snapshots = resp.json()
    assert len(snapshots) == 1
    # Must NOT include snapshot_data
    assert "snapshot_data" not in snapshots[0]
    assert "name" in snapshots[0]
    assert "id" in snapshots[0]
    assert "created_at" in snapshots[0]


@pytest.mark.asyncio
async def test_list_snapshots_multiple(client: AsyncClient):
    """Multiple snapshots for the same model are all returned."""
    token, ws_id, model_id = await setup_model(client, "snap_list_multi@example.com")

    await create_snapshot(client, token, model_id, "Snapshot A")
    await create_snapshot(client, token, model_id, "Snapshot B")
    await create_snapshot(client, token, model_id, "Snapshot C")

    resp = await client.get(
        f"/models/{model_id}/snapshots",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    names = [s["name"] for s in resp.json()]
    assert "Snapshot A" in names
    assert "Snapshot B" in names
    assert "Snapshot C" in names


@pytest.mark.asyncio
async def test_list_snapshots_isolated_per_model(client: AsyncClient):
    """Snapshots are isolated per model."""
    token, ws_id, model_id_a = await setup_model(client, "snap_iso@example.com")
    model_id_b = await create_model(client, token, ws_id, name="Model B")

    await create_snapshot(client, token, model_id_a, "Snap for A")

    resp = await client.get(
        f"/models/{model_id_b}/snapshots",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_snapshots_requires_auth(client: AsyncClient):
    token, ws_id, model_id = await setup_model(client, "snap_list_auth@example.com")

    resp = await client.get(f"/models/{model_id}/snapshots")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Get snapshot detail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_snapshot_detail_includes_data(client: AsyncClient):
    token, ws_id, model_id = await setup_model(client, "snap_detail@example.com")
    await create_dimension(client, token, model_id, name="Expenses")
    snap = await create_snapshot(client, token, model_id, "Detail Test")

    resp = await client.get(f"/snapshots/{snap['id']}", headers=auth_headers(token))
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["id"] == snap["id"]
    assert "snapshot_data" in detail
    assert detail["snapshot_data"] is not None
    assert "dimensions" in detail["snapshot_data"]
    assert "modules" in detail["snapshot_data"]
    assert "versions" in detail["snapshot_data"]


@pytest.mark.asyncio
async def test_get_snapshot_not_found(client: AsyncClient):
    token, ws_id, model_id = await setup_model(client, "snap_detail_404@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.get(f"/snapshots/{fake_id}", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_snapshot_requires_auth(client: AsyncClient):
    token, ws_id, model_id = await setup_model(client, "snap_detail_auth@example.com")
    snap = await create_snapshot(client, token, model_id, "Auth Test")

    resp = await client.get(f"/snapshots/{snap['id']}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Delete snapshot
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_snapshot(client: AsyncClient):
    token, ws_id, model_id = await setup_model(client, "snap_del@example.com")
    snap = await create_snapshot(client, token, model_id, "Delete Me")
    snap_id = snap["id"]

    del_resp = await client.delete(
        f"/snapshots/{snap_id}",
        headers=auth_headers(token),
    )
    assert del_resp.status_code == 204

    # Verify it's gone
    get_resp = await client.get(f"/snapshots/{snap_id}", headers=auth_headers(token))
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_snapshot_not_found(client: AsyncClient):
    token, ws_id, model_id = await setup_model(client, "snap_del_404@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.delete(f"/snapshots/{fake_id}", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_snapshot_requires_auth(client: AsyncClient):
    token, ws_id, model_id = await setup_model(client, "snap_del_auth@example.com")
    snap = await create_snapshot(client, token, model_id, "Auth Delete")

    resp = await client.delete(f"/snapshots/{snap['id']}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Restore snapshot
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_restore_snapshot_recreates_entities(client: AsyncClient):
    """After restore, the model should contain the snapshot's entities."""
    token, ws_id, model_id = await setup_model(client, "snap_restore@example.com")

    # Create initial state
    await create_dimension(client, token, model_id, name="Regions")
    await create_module(client, token, model_id, name="Revenue")
    snap = await create_snapshot(client, token, model_id, "Before Change")

    # Modify model (add extra dimension)
    await create_dimension(client, token, model_id, name="Extra Dim")

    # Restore
    restore_resp = await client.post(
        f"/snapshots/{snap['id']}/restore",
        headers=auth_headers(token),
    )
    assert restore_resp.status_code == 200
    result = restore_resp.json()
    assert result["snapshot_id"] == snap["id"]
    assert result["model_id"] == model_id
    assert "entities_restored" in result
    assert result["entities_restored"]["dimensions"] == 1
    assert result["entities_restored"]["modules"] == 1


@pytest.mark.asyncio
async def test_restore_clears_existing_data_first(client: AsyncClient):
    """Restore must wipe current state before recreating from snapshot."""
    token, ws_id, model_id = await setup_model(client, "snap_restore_clear@example.com")

    # Snapshot empty model
    snap = await create_snapshot(client, token, model_id, "Empty State")

    # Add dimensions after snapshot
    await create_dimension(client, token, model_id, name="Should Be Gone")
    await create_module(client, token, model_id, name="Also Gone")

    # Restore to empty snapshot
    restore_resp = await client.post(
        f"/snapshots/{snap['id']}/restore",
        headers=auth_headers(token),
    )
    assert restore_resp.status_code == 200
    result = restore_resp.json()
    # Empty snapshot => 0 entities restored
    assert result["entities_restored"]["dimensions"] == 0
    assert result["entities_restored"]["modules"] == 0

    # Verify dimensions are gone
    dims_resp = await client.get(
        f"/models/{model_id}/dimensions",
        headers=auth_headers(token),
    )
    assert dims_resp.status_code == 200
    assert dims_resp.json() == []


@pytest.mark.asyncio
async def test_restore_snapshot_not_found(client: AsyncClient):
    token, ws_id, model_id = await setup_model(client, "snap_restore_404@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.post(
        f"/snapshots/{fake_id}/restore",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_restore_snapshot_requires_auth(client: AsyncClient):
    token, ws_id, model_id = await setup_model(client, "snap_restore_auth@example.com")
    snap = await create_snapshot(client, token, model_id, "Auth Restore")

    resp = await client.post(f"/snapshots/{snap['id']}/restore")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_restore_snapshot_with_versions(client: AsyncClient):
    """Restore should correctly recreate versions."""
    token, ws_id, model_id = await setup_model(client, "snap_restore_versions@example.com")

    await create_version(client, token, model_id, name="Budget 2024")
    snap = await create_snapshot(client, token, model_id, "With Versions")

    # Delete the version post-snapshot
    versions_resp = await client.get(
        f"/models/{model_id}/versions",
        headers=auth_headers(token),
    )
    for v in versions_resp.json():
        await client.delete(f"/versions/{v['id']}", headers=auth_headers(token))

    # Restore
    restore_resp = await client.post(
        f"/snapshots/{snap['id']}/restore",
        headers=auth_headers(token),
    )
    assert restore_resp.status_code == 200
    result = restore_resp.json()
    assert result["entities_restored"]["versions"] == 1


# ---------------------------------------------------------------------------
# Compare snapshots
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compare_snapshots_identical(client: AsyncClient):
    """Comparing two snapshots with same data returns no differences."""
    token, ws_id, model_id = await setup_model(client, "snap_cmp_same@example.com")

    await create_dimension(client, token, model_id, name="Products")
    snap_a = await create_snapshot(client, token, model_id, "Snap A")
    snap_b = await create_snapshot(client, token, model_id, "Snap B")

    resp = await client.post(
        "/snapshots/compare",
        json={"snapshot_a_id": snap_a["id"], "snapshot_b_id": snap_b["id"]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    result = resp.json()
    assert result["snapshot_id_a"] == snap_a["id"]
    assert result["snapshot_id_b"] == snap_b["id"]
    assert result["snapshot_name_a"] == "Snap A"
    assert result["snapshot_name_b"] == "Snap B"
    assert "No differences" in result["summary"]


@pytest.mark.asyncio
async def test_compare_snapshots_show_diffs(client: AsyncClient):
    """Adding entities between snapshots should appear as diffs."""
    token, ws_id, model_id = await setup_model(client, "snap_cmp_diff@example.com")

    snap_a = await create_snapshot(client, token, model_id, "Before")

    # Add entities
    await create_dimension(client, token, model_id, name="New Dim")
    await create_module(client, token, model_id, name="New Module")
    snap_b = await create_snapshot(client, token, model_id, "After")

    resp = await client.post(
        "/snapshots/compare",
        json={"snapshot_a_id": snap_a["id"], "snapshot_b_id": snap_b["id"]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    result = resp.json()
    # New dim was added (present in B but not A)
    assert result["dimensions"]["added"] == 1
    assert result["dimensions"]["removed"] == 0
    # New module was added
    assert result["modules"]["added"] == 1


@pytest.mark.asyncio
async def test_compare_snapshots_not_found(client: AsyncClient):
    token, ws_id, model_id = await setup_model(client, "snap_cmp_404@example.com")
    fake_a = str(uuid.uuid4())
    fake_b = str(uuid.uuid4())

    resp = await client.post(
        "/snapshots/compare",
        json={"snapshot_a_id": fake_a, "snapshot_b_id": fake_b},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_compare_snapshots_requires_auth(client: AsyncClient):
    token, ws_id, model_id = await setup_model(client, "snap_cmp_auth@example.com")
    snap_a = await create_snapshot(client, token, model_id, "A")
    snap_b = await create_snapshot(client, token, model_id, "B")

    resp = await client.post(
        "/snapshots/compare",
        json={"snapshot_a_id": snap_a["id"], "snapshot_b_id": snap_b["id"]},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_compare_snapshots_response_structure(client: AsyncClient):
    """Compare response must include all entity type diffs."""
    token, ws_id, model_id = await setup_model(client, "snap_cmp_struct@example.com")
    snap_a = await create_snapshot(client, token, model_id, "X")
    snap_b = await create_snapshot(client, token, model_id, "Y")

    resp = await client.post(
        "/snapshots/compare",
        json={"snapshot_a_id": snap_a["id"], "snapshot_b_id": snap_b["id"]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    result = resp.json()
    for field in ("dimensions", "dimension_items", "modules", "line_items", "cell_values", "versions"):
        assert field in result
        assert "added" in result[field]
        assert "removed" in result[field]
        assert "changed" in result[field]
    assert "summary" in result
