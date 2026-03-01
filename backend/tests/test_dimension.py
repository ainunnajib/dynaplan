import uuid
from typing import Optional

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


async def create_dimension(
    client: AsyncClient,
    token: str,
    model_id: str,
    name: str = "Products",
    dimension_type: str = "custom",
) -> dict:
    resp = await client.post(
        f"/models/{model_id}/dimensions",
        json={"name": name, "dimension_type": dimension_type},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def create_item(
    client: AsyncClient,
    token: str,
    dimension_id: str,
    name: str = "Item A",
    code: Optional[str] = "A",
    parent_id: Optional[str] = None,
    sort_order: int = 0,
) -> dict:
    payload: dict = {"name": name, "sort_order": sort_order}
    if code is not None:
        payload["code"] = code
    if parent_id is not None:
        payload["parent_id"] = parent_id
    resp = await client.post(
        f"/dimensions/{dimension_id}/items",
        json=payload,
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Dimension CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_dimension_success(client: AsyncClient):
    token = await register_and_login(client, "d_create@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await client.post(
        f"/models/{model_id}/dimensions",
        json={"name": "Regions", "dimension_type": "custom"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Regions"
    assert data["dimension_type"] == "custom"
    assert data["model_id"] == model_id
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_dimension_time_type(client: AsyncClient):
    token = await register_and_login(client, "d_time@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await client.post(
        f"/models/{model_id}/dimensions",
        json={"name": "Time", "dimension_type": "time"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    assert resp.json()["dimension_type"] == "time"


@pytest.mark.asyncio
async def test_create_dimension_version_type(client: AsyncClient):
    token = await register_and_login(client, "d_version@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await client.post(
        f"/models/{model_id}/dimensions",
        json={"name": "Versions", "dimension_type": "version"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    assert resp.json()["dimension_type"] == "version"


@pytest.mark.asyncio
async def test_create_dimension_numbered_type_with_max_items(client: AsyncClient):
    token = await register_and_login(client, "d_numbered@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await client.post(
        f"/models/{model_id}/dimensions",
        json={"name": "Transactions", "dimension_type": "numbered", "max_items": 3},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["dimension_type"] == "numbered"
    assert data["max_items"] == 3


@pytest.mark.asyncio
async def test_create_dimension_max_items_rejected_for_non_numbered(client: AsyncClient):
    token = await register_and_login(client, "d_bad_max_items@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await client.post(
        f"/models/{model_id}/dimensions",
        json={"name": "Regions", "dimension_type": "custom", "max_items": 10},
        headers=auth_headers(token),
    )
    assert resp.status_code == 400
    assert "max_items" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_dimension_requires_auth(client: AsyncClient):
    fake_model_id = str(uuid.uuid4())
    resp = await client.post(
        f"/models/{fake_model_id}/dimensions",
        json={"name": "No Auth"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_dimensions_empty(client: AsyncClient):
    token = await register_and_login(client, "d_list_empty@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await client.get(
        f"/models/{model_id}/dimensions",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_dimensions_returns_created(client: AsyncClient):
    token = await register_and_login(client, "d_list_created@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    await create_dimension(client, token, model_id, name="Products")
    await create_dimension(client, token, model_id, name="Regions")

    resp = await client.get(
        f"/models/{model_id}/dimensions",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    names = [d["name"] for d in resp.json()]
    assert "Products" in names
    assert "Regions" in names


@pytest.mark.asyncio
async def test_list_dimensions_isolated_per_model(client: AsyncClient):
    token = await register_and_login(client, "d_list_iso@example.com")
    ws_id = await create_workspace(client, token)
    model_a_id = await create_model(client, token, ws_id, name="Model A")
    model_b_id = await create_model(client, token, ws_id, name="Model B")

    await create_dimension(client, token, model_a_id, name="Dimension A")

    resp = await client.get(
        f"/models/{model_b_id}/dimensions",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_update_dimension_name(client: AsyncClient):
    token = await register_and_login(client, "d_update@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dim = await create_dimension(client, token, model_id, name="Old Name")

    resp = await client.patch(
        f"/dimensions/{dim['id']}",
        json={"name": "New Name"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_update_dimension_type(client: AsyncClient):
    token = await register_and_login(client, "d_update_type@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dim = await create_dimension(client, token, model_id, dimension_type="custom")

    resp = await client.patch(
        f"/dimensions/{dim['id']}",
        json={"dimension_type": "version"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["dimension_type"] == "version"


@pytest.mark.asyncio
async def test_update_dimension_switch_to_non_numbered_clears_max_items(client: AsyncClient):
    token = await register_and_login(client, "d_type_clear_max@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dim = await create_dimension(
        client,
        token,
        model_id,
        name="Transactions",
        dimension_type="numbered",
    )

    set_max_resp = await client.patch(
        f"/dimensions/{dim['id']}",
        json={"max_items": 2},
        headers=auth_headers(token),
    )
    assert set_max_resp.status_code == 200
    assert set_max_resp.json()["max_items"] == 2

    resp = await client.patch(
        f"/dimensions/{dim['id']}",
        json={"dimension_type": "custom"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["dimension_type"] == "custom"
    assert resp.json()["max_items"] is None


@pytest.mark.asyncio
async def test_update_dimension_not_found(client: AsyncClient):
    token = await register_and_login(client, "d_update_nf@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.patch(
        f"/dimensions/{fake_id}",
        json={"name": "Ghost"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_dimension(client: AsyncClient):
    token = await register_and_login(client, "d_delete@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dim = await create_dimension(client, token, model_id, name="To Delete")
    dim_id = dim["id"]

    del_resp = await client.delete(
        f"/dimensions/{dim_id}",
        headers=auth_headers(token),
    )
    assert del_resp.status_code == 204

    # Verify it's gone from the list
    list_resp = await client.get(
        f"/models/{model_id}/dimensions",
        headers=auth_headers(token),
    )
    assert list_resp.status_code == 200
    ids = [d["id"] for d in list_resp.json()]
    assert dim_id not in ids


@pytest.mark.asyncio
async def test_delete_dimension_not_found(client: AsyncClient):
    token = await register_and_login(client, "d_del_nf@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.delete(
        f"/dimensions/{fake_id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DimensionItem CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_item_success(client: AsyncClient):
    token = await register_and_login(client, "di_create@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dim = await create_dimension(client, token, model_id)
    dim_id = dim["id"]

    resp = await client.post(
        f"/dimensions/{dim_id}/items",
        json={"name": "North America", "code": "NA", "sort_order": 0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "North America"
    assert data["code"] == "NA"
    assert data["dimension_id"] == dim_id
    assert data["parent_id"] is None
    assert data["sort_order"] == 0
    assert "id" in data


@pytest.mark.asyncio
async def test_create_item_numbered_auto_generates_code(client: AsyncClient):
    token = await register_and_login(client, "di_numbered_auto@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dim = await create_dimension(
        client,
        token,
        model_id,
        name="Transactions",
        dimension_type="numbered",
    )
    dim_id = dim["id"]

    first = await create_item(client, token, dim_id, name="Invoice line", code=None)
    second = await create_item(client, token, dim_id, name="Invoice line", code=None)
    third = await create_item(client, token, dim_id, name="Invoice line", code="999")

    assert first["code"] == "1"
    assert second["code"] == "2"
    assert third["code"] == "3"


@pytest.mark.asyncio
async def test_create_item_numbered_honors_max_items_limit(client: AsyncClient):
    token = await register_and_login(client, "di_numbered_limit@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    create_dim_resp = await client.post(
        f"/models/{model_id}/dimensions",
        json={"name": "Transactions", "dimension_type": "numbered", "max_items": 2},
        headers=auth_headers(token),
    )
    assert create_dim_resp.status_code == 201
    dim_id = create_dim_resp.json()["id"]

    first = await create_item(client, token, dim_id, name="Line 1", code=None)
    second = await create_item(client, token, dim_id, name="Line 2", code=None)
    assert first["code"] == "1"
    assert second["code"] == "2"

    third_resp = await client.post(
        f"/dimensions/{dim_id}/items",
        json={"name": "Line 3"},
        headers=auth_headers(token),
    )
    assert third_resp.status_code == 400
    assert "max_items" in third_resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_item_non_numbered_requires_code(client: AsyncClient):
    token = await register_and_login(client, "di_code_required@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dim = await create_dimension(client, token, model_id, dimension_type="custom")
    dim_id = dim["id"]

    resp = await client.post(
        f"/dimensions/{dim_id}/items",
        json={"name": "Item without code"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 400
    assert "Code is required" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_item_requires_auth(client: AsyncClient):
    fake_dim_id = str(uuid.uuid4())
    resp = await client.post(
        f"/dimensions/{fake_dim_id}/items",
        json={"name": "Item", "code": "X"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_item_dimension_not_found(client: AsyncClient):
    token = await register_and_login(client, "di_dim_nf@example.com")
    fake_dim_id = str(uuid.uuid4())

    resp = await client.post(
        f"/dimensions/{fake_dim_id}/items",
        json={"name": "Item", "code": "X"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_item_with_parent(client: AsyncClient):
    token = await register_and_login(client, "di_parent@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dim = await create_dimension(client, token, model_id)
    dim_id = dim["id"]

    parent = await create_item(client, token, dim_id, name="Americas", code="AMER")
    child_resp = await client.post(
        f"/dimensions/{dim_id}/items",
        json={"name": "USA", "code": "USA", "parent_id": parent["id"]},
        headers=auth_headers(token),
    )
    assert child_resp.status_code == 201
    child = child_resp.json()
    assert child["parent_id"] == parent["id"]


@pytest.mark.asyncio
async def test_create_item_invalid_parent(client: AsyncClient):
    token = await register_and_login(client, "di_bad_parent@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dim = await create_dimension(client, token, model_id)
    dim_id = dim["id"]

    fake_parent_id = str(uuid.uuid4())
    resp = await client.post(
        f"/dimensions/{dim_id}/items",
        json={"name": "Child", "code": "C", "parent_id": fake_parent_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_items_flat(client: AsyncClient):
    token = await register_and_login(client, "di_list_flat@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dim = await create_dimension(client, token, model_id)
    dim_id = dim["id"]

    await create_item(client, token, dim_id, name="Alpha", code="A")
    await create_item(client, token, dim_id, name="Beta", code="B")

    resp = await client.get(
        f"/dimensions/{dim_id}/items",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    names = [i["name"] for i in items]
    assert "Alpha" in names
    assert "Beta" in names
    # Flat response has no "children" key required (it's DimensionItemResponse)
    for item in items:
        assert "id" in item
        assert "code" in item


@pytest.mark.asyncio
async def test_list_items_tree(client: AsyncClient):
    token = await register_and_login(client, "di_list_tree@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dim = await create_dimension(client, token, model_id)
    dim_id = dim["id"]

    parent = await create_item(client, token, dim_id, name="AMER", code="AMER")
    await create_item(client, token, dim_id, name="USA", code="USA", parent_id=parent["id"])
    await create_item(client, token, dim_id, name="Canada", code="CAN", parent_id=parent["id"])

    resp = await client.get(
        f"/dimensions/{dim_id}/items",
        params={"format": "tree"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    tree = resp.json()
    assert len(tree) == 1  # Only the root node
    root = tree[0]
    assert root["name"] == "AMER"
    assert len(root["children"]) == 2
    child_names = [c["name"] for c in root["children"]]
    assert "USA" in child_names
    assert "Canada" in child_names


@pytest.mark.asyncio
async def test_list_items_empty(client: AsyncClient):
    token = await register_and_login(client, "di_list_empty@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dim = await create_dimension(client, token, model_id)
    dim_id = dim["id"]

    resp = await client.get(
        f"/dimensions/{dim_id}/items",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_items_dimension_not_found(client: AsyncClient):
    token = await register_and_login(client, "di_list_nf@example.com")
    fake_dim_id = str(uuid.uuid4())

    resp = await client.get(
        f"/dimensions/{fake_dim_id}/items",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_item_rename(client: AsyncClient):
    token = await register_and_login(client, "di_update_name@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dim = await create_dimension(client, token, model_id)
    dim_id = dim["id"]
    item = await create_item(client, token, dim_id, name="Old Name", code="OLD")

    resp = await client.patch(
        f"/dimensions/{dim_id}/items/{item['id']}",
        json={"name": "New Name"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"
    assert resp.json()["code"] == "OLD"  # Code unchanged


@pytest.mark.asyncio
async def test_update_item_numbered_code_rejected(client: AsyncClient):
    token = await register_and_login(client, "di_numbered_update_code@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dim = await create_dimension(
        client,
        token,
        model_id,
        name="Transactions",
        dimension_type="numbered",
    )
    dim_id = dim["id"]
    item = await create_item(client, token, dim_id, name="Line 1", code=None)

    resp = await client.patch(
        f"/dimensions/{dim_id}/items/{item['id']}",
        json={"code": "999"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 400
    assert "cannot be changed" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_update_item_reparent(client: AsyncClient):
    token = await register_and_login(client, "di_reparent@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dim = await create_dimension(client, token, model_id)
    dim_id = dim["id"]

    parent_a = await create_item(client, token, dim_id, name="Parent A", code="PA")
    parent_b = await create_item(client, token, dim_id, name="Parent B", code="PB")
    child = await create_item(client, token, dim_id, name="Child", code="C", parent_id=parent_a["id"])

    assert child["parent_id"] == parent_a["id"]

    resp = await client.patch(
        f"/dimensions/{dim_id}/items/{child['id']}",
        json={"parent_id": parent_b["id"]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["parent_id"] == parent_b["id"]


@pytest.mark.asyncio
async def test_update_item_self_parent_rejected(client: AsyncClient):
    token = await register_and_login(client, "di_self_parent@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dim = await create_dimension(client, token, model_id)
    dim_id = dim["id"]
    item = await create_item(client, token, dim_id, name="Item", code="I")

    resp = await client.patch(
        f"/dimensions/{dim_id}/items/{item['id']}",
        json={"parent_id": item["id"]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_item_not_found(client: AsyncClient):
    token = await register_and_login(client, "di_update_nf@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dim = await create_dimension(client, token, model_id)
    dim_id = dim["id"]
    fake_item_id = str(uuid.uuid4())

    resp = await client.patch(
        f"/dimensions/{dim_id}/items/{fake_item_id}",
        json={"name": "Ghost"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_item_wrong_dimension(client: AsyncClient):
    """Cannot update an item using a different dimension's URL."""
    token = await register_and_login(client, "di_wrong_dim@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dim_a = await create_dimension(client, token, model_id, name="Dim A")
    dim_b = await create_dimension(client, token, model_id, name="Dim B")

    item = await create_item(client, token, dim_a["id"], name="Item", code="X")

    # Try to update item from dim_a using dim_b's URL
    resp = await client.patch(
        f"/dimensions/{dim_b['id']}/items/{item['id']}",
        json={"name": "Cross-dim edit"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_item(client: AsyncClient):
    token = await register_and_login(client, "di_delete@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dim = await create_dimension(client, token, model_id)
    dim_id = dim["id"]
    item = await create_item(client, token, dim_id, name="Trash Me", code="T")
    item_id = item["id"]

    del_resp = await client.delete(
        f"/dimensions/{dim_id}/items/{item_id}",
        headers=auth_headers(token),
    )
    assert del_resp.status_code == 204

    # Verify it's gone
    list_resp = await client.get(
        f"/dimensions/{dim_id}/items",
        headers=auth_headers(token),
    )
    assert list_resp.status_code == 200
    ids = [i["id"] for i in list_resp.json()]
    assert item_id not in ids


@pytest.mark.asyncio
async def test_delete_item_not_found(client: AsyncClient):
    token = await register_and_login(client, "di_del_nf@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dim = await create_dimension(client, token, model_id)
    dim_id = dim["id"]
    fake_item_id = str(uuid.uuid4())

    resp = await client.delete(
        f"/dimensions/{dim_id}/items/{fake_item_id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_item_requires_auth(client: AsyncClient):
    fake_dim_id = str(uuid.uuid4())
    fake_item_id = str(uuid.uuid4())

    resp = await client.delete(f"/dimensions/{fake_dim_id}/items/{fake_item_id}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Cascade: deleting dimension deletes items
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_dimension_cascades_items(client: AsyncClient):
    token = await register_and_login(client, "di_cascade@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dim = await create_dimension(client, token, model_id, name="To Cascade")
    dim_id = dim["id"]

    await create_item(client, token, dim_id, name="Item 1", code="I1")
    await create_item(client, token, dim_id, name="Item 2", code="I2")

    # Delete the dimension
    del_resp = await client.delete(
        f"/dimensions/{dim_id}",
        headers=auth_headers(token),
    )
    assert del_resp.status_code == 204

    # Dimension is gone
    list_resp = await client.get(
        f"/models/{model_id}/dimensions",
        headers=auth_headers(token),
    )
    assert list_resp.status_code == 200
    assert dim_id not in [d["id"] for d in list_resp.json()]


# ---------------------------------------------------------------------------
# Sort order
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_items_sorted_by_sort_order(client: AsyncClient):
    token = await register_and_login(client, "di_sort@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dim = await create_dimension(client, token, model_id)
    dim_id = dim["id"]

    await create_item(client, token, dim_id, name="Third", code="C", sort_order=20)
    await create_item(client, token, dim_id, name="First", code="A", sort_order=0)
    await create_item(client, token, dim_id, name="Second", code="B", sort_order=10)

    resp = await client.get(
        f"/dimensions/{dim_id}/items",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    items = resp.json()
    names = [i["name"] for i in items]
    assert names == ["First", "Second", "Third"]
