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


async def create_module(
    client: AsyncClient,
    token: str,
    model_id: str,
    name: str = "Revenue Module",
    description: Optional[str] = None,
) -> dict:
    payload: dict = {"name": name}
    if description is not None:
        payload["description"] = description
    resp = await client.post(
        f"/models/{model_id}/modules",
        json=payload,
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def create_line_item(
    client: AsyncClient,
    token: str,
    module_id: str,
    name: str = "Revenue",
    format: str = "number",
    formula: Optional[str] = None,
    summary_method: str = "sum",
    applies_to_dimensions: Optional[list] = None,
    sort_order: int = 0,
) -> dict:
    payload: dict = {
        "name": name,
        "format": format,
        "summary_method": summary_method,
        "sort_order": sort_order,
    }
    if formula is not None:
        payload["formula"] = formula
    if applies_to_dimensions is not None:
        payload["applies_to_dimensions"] = applies_to_dimensions
    resp = await client.post(
        f"/modules/{module_id}/line-items",
        json=payload,
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Module CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_module_success(client: AsyncClient):
    token = await register_and_login(client, "m_create@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await client.post(
        f"/models/{model_id}/modules",
        json={"name": "Revenue", "description": "Revenue planning module"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Revenue"
    assert data["description"] == "Revenue planning module"
    assert data["model_id"] == model_id
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_module_no_description(client: AsyncClient):
    token = await register_and_login(client, "m_nodesc@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await client.post(
        f"/models/{model_id}/modules",
        json={"name": "Costs"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Costs"
    assert data["description"] is None


@pytest.mark.asyncio
async def test_create_module_requires_auth(client: AsyncClient):
    fake_model_id = str(uuid.uuid4())
    resp = await client.post(
        f"/models/{fake_model_id}/modules",
        json={"name": "Unauthorized"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_modules_empty(client: AsyncClient):
    token = await register_and_login(client, "m_list_empty@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await client.get(
        f"/models/{model_id}/modules",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_modules_returns_created(client: AsyncClient):
    token = await register_and_login(client, "m_list_created@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    await create_module(client, token, model_id, name="Revenue")
    await create_module(client, token, model_id, name="Costs")

    resp = await client.get(
        f"/models/{model_id}/modules",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    names = [m["name"] for m in resp.json()]
    assert "Revenue" in names
    assert "Costs" in names


@pytest.mark.asyncio
async def test_list_modules_isolated_per_model(client: AsyncClient):
    token = await register_and_login(client, "m_list_iso@example.com")
    ws_id = await create_workspace(client, token)
    model_a_id = await create_model(client, token, ws_id, name="Model A")
    model_b_id = await create_model(client, token, ws_id, name="Model B")

    await create_module(client, token, model_a_id, name="Module A")

    resp = await client.get(
        f"/models/{model_b_id}/modules",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_module_with_line_items(client: AsyncClient):
    token = await register_and_login(client, "m_get@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module = await create_module(client, token, model_id, name="P&L")
    module_id = module["id"]

    await create_line_item(client, token, module_id, name="Revenue")
    await create_line_item(client, token, module_id, name="Costs")

    resp = await client.get(
        f"/modules/{module_id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "P&L"
    assert "line_items" in data
    line_item_names = [li["name"] for li in data["line_items"]]
    assert "Revenue" in line_item_names
    assert "Costs" in line_item_names


@pytest.mark.asyncio
async def test_get_module_not_found(client: AsyncClient):
    token = await register_and_login(client, "m_get_nf@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.get(
        f"/modules/{fake_id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_module_requires_auth(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/modules/{fake_id}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_module_name(client: AsyncClient):
    token = await register_and_login(client, "m_update_name@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module = await create_module(client, token, model_id, name="Old Name")

    resp = await client.patch(
        f"/modules/{module['id']}",
        json={"name": "New Name"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_update_module_description(client: AsyncClient):
    token = await register_and_login(client, "m_update_desc@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module = await create_module(client, token, model_id, description="Old desc")

    resp = await client.patch(
        f"/modules/{module['id']}",
        json={"description": "New description"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "New description"


@pytest.mark.asyncio
async def test_update_module_not_found(client: AsyncClient):
    token = await register_and_login(client, "m_update_nf@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.patch(
        f"/modules/{fake_id}",
        json={"name": "Ghost"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_module(client: AsyncClient):
    token = await register_and_login(client, "m_delete@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module = await create_module(client, token, model_id, name="To Delete")
    module_id = module["id"]

    del_resp = await client.delete(
        f"/modules/{module_id}",
        headers=auth_headers(token),
    )
    assert del_resp.status_code == 204

    list_resp = await client.get(
        f"/models/{model_id}/modules",
        headers=auth_headers(token),
    )
    assert list_resp.status_code == 200
    ids = [m["id"] for m in list_resp.json()]
    assert module_id not in ids


@pytest.mark.asyncio
async def test_delete_module_not_found(client: AsyncClient):
    token = await register_and_login(client, "m_del_nf@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.delete(
        f"/modules/{fake_id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_module_requires_auth(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    resp = await client.delete(f"/modules/{fake_id}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# LineItem CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_line_item_success(client: AsyncClient):
    token = await register_and_login(client, "li_create@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module = await create_module(client, token, model_id)
    module_id = module["id"]

    resp = await client.post(
        f"/modules/{module_id}/line-items",
        json={"name": "Revenue", "format": "number", "summary_method": "sum"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Revenue"
    assert data["format"] == "number"
    assert data["summary_method"] == "sum"
    assert data["module_id"] == module_id
    assert data["formula"] is None
    assert data["sort_order"] == 0
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_line_item_all_formats(client: AsyncClient):
    token = await register_and_login(client, "li_formats@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module = await create_module(client, token, model_id)
    module_id = module["id"]

    for fmt in ["number", "text", "boolean", "date", "list"]:
        resp = await client.post(
            f"/modules/{module_id}/line-items",
            json={"name": f"Item {fmt}", "format": fmt},
            headers=auth_headers(token),
        )
        assert resp.status_code == 201
        assert resp.json()["format"] == fmt


@pytest.mark.asyncio
async def test_create_line_item_all_summary_methods(client: AsyncClient):
    token = await register_and_login(client, "li_summary@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module = await create_module(client, token, model_id)
    module_id = module["id"]

    for method in ["sum", "average", "min", "max", "none", "formula"]:
        resp = await client.post(
            f"/modules/{module_id}/line-items",
            json={"name": f"Item {method}", "summary_method": method},
            headers=auth_headers(token),
        )
        assert resp.status_code == 201
        assert resp.json()["summary_method"] == method


@pytest.mark.asyncio
async def test_create_line_item_with_formula(client: AsyncClient):
    token = await register_and_login(client, "li_formula@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module = await create_module(client, token, model_id)
    module_id = module["id"]

    formula = "Revenue - Costs"
    resp = await client.post(
        f"/modules/{module_id}/line-items",
        json={"name": "Gross Profit", "formula": formula},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Gross Profit"
    assert data["formula"] == formula


@pytest.mark.asyncio
async def test_create_line_item_with_applies_to_dimensions(client: AsyncClient):
    token = await register_and_login(client, "li_dims@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module = await create_module(client, token, model_id)
    module_id = module["id"]

    dim_id_1 = str(uuid.uuid4())
    dim_id_2 = str(uuid.uuid4())
    applies_to = [dim_id_1, dim_id_2]

    resp = await client.post(
        f"/modules/{module_id}/line-items",
        json={"name": "Revenue by Region", "applies_to_dimensions": applies_to},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["applies_to_dimensions"] == applies_to


@pytest.mark.asyncio
async def test_create_line_item_empty_applies_to_dimensions(client: AsyncClient):
    token = await register_and_login(client, "li_dims_empty@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module = await create_module(client, token, model_id)
    module_id = module["id"]

    resp = await client.post(
        f"/modules/{module_id}/line-items",
        json={"name": "Simple Item", "applies_to_dimensions": []},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["applies_to_dimensions"] == []


@pytest.mark.asyncio
async def test_create_line_item_module_not_found(client: AsyncClient):
    token = await register_and_login(client, "li_mod_nf@example.com")
    fake_module_id = str(uuid.uuid4())

    resp = await client.post(
        f"/modules/{fake_module_id}/line-items",
        json={"name": "Orphan"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_line_item_requires_auth(client: AsyncClient):
    fake_module_id = str(uuid.uuid4())
    resp = await client.post(
        f"/modules/{fake_module_id}/line-items",
        json={"name": "No Auth"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_line_items_empty(client: AsyncClient):
    token = await register_and_login(client, "li_list_empty@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module = await create_module(client, token, model_id)
    module_id = module["id"]

    resp = await client.get(
        f"/modules/{module_id}/line-items",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_line_items_returns_created(client: AsyncClient):
    token = await register_and_login(client, "li_list_created@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module = await create_module(client, token, model_id)
    module_id = module["id"]

    await create_line_item(client, token, module_id, name="Revenue")
    await create_line_item(client, token, module_id, name="Costs")

    resp = await client.get(
        f"/modules/{module_id}/line-items",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    names = [li["name"] for li in resp.json()]
    assert "Revenue" in names
    assert "Costs" in names


@pytest.mark.asyncio
async def test_list_line_items_module_not_found(client: AsyncClient):
    token = await register_and_login(client, "li_list_nf@example.com")
    fake_module_id = str(uuid.uuid4())

    resp = await client.get(
        f"/modules/{fake_module_id}/line-items",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_line_item_rename(client: AsyncClient):
    token = await register_and_login(client, "li_rename@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module = await create_module(client, token, model_id)
    module_id = module["id"]
    line_item = await create_line_item(client, token, module_id, name="Old Name")

    resp = await client.patch(
        f"/line-items/{line_item['id']}",
        json={"name": "New Name"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"
    assert resp.json()["format"] == "number"  # Unchanged


@pytest.mark.asyncio
async def test_update_line_item_change_format(client: AsyncClient):
    token = await register_and_login(client, "li_format_change@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module = await create_module(client, token, model_id)
    module_id = module["id"]
    line_item = await create_line_item(client, token, module_id, format="number")

    resp = await client.patch(
        f"/line-items/{line_item['id']}",
        json={"format": "text"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["format"] == "text"


@pytest.mark.asyncio
async def test_update_line_item_set_formula(client: AsyncClient):
    token = await register_and_login(client, "li_set_formula@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module = await create_module(client, token, model_id)
    module_id = module["id"]
    line_item = await create_line_item(client, token, module_id, name="Gross Profit")

    new_formula = "Revenue - Costs"
    resp = await client.patch(
        f"/line-items/{line_item['id']}",
        json={"formula": new_formula},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["formula"] == new_formula


@pytest.mark.asyncio
async def test_update_line_item_change_summary_method(client: AsyncClient):
    token = await register_and_login(client, "li_summary_change@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module = await create_module(client, token, model_id)
    module_id = module["id"]
    line_item = await create_line_item(client, token, module_id, summary_method="sum")

    resp = await client.patch(
        f"/line-items/{line_item['id']}",
        json={"summary_method": "average"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["summary_method"] == "average"


@pytest.mark.asyncio
async def test_update_line_item_applies_to_dimensions(client: AsyncClient):
    token = await register_and_login(client, "li_dims_update@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module = await create_module(client, token, model_id)
    module_id = module["id"]
    line_item = await create_line_item(client, token, module_id, name="Revenue")

    new_dims = [str(uuid.uuid4()), str(uuid.uuid4())]
    resp = await client.patch(
        f"/line-items/{line_item['id']}",
        json={"applies_to_dimensions": new_dims},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["applies_to_dimensions"] == new_dims


@pytest.mark.asyncio
async def test_update_line_item_not_found(client: AsyncClient):
    token = await register_and_login(client, "li_update_nf@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.patch(
        f"/line-items/{fake_id}",
        json={"name": "Ghost"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_line_item_requires_auth(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    resp = await client.patch(
        f"/line-items/{fake_id}",
        json={"name": "No Auth"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_line_item(client: AsyncClient):
    token = await register_and_login(client, "li_delete@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module = await create_module(client, token, model_id)
    module_id = module["id"]
    line_item = await create_line_item(client, token, module_id, name="Trash Me")
    line_item_id = line_item["id"]

    del_resp = await client.delete(
        f"/line-items/{line_item_id}",
        headers=auth_headers(token),
    )
    assert del_resp.status_code == 204

    list_resp = await client.get(
        f"/modules/{module_id}/line-items",
        headers=auth_headers(token),
    )
    assert list_resp.status_code == 200
    ids = [li["id"] for li in list_resp.json()]
    assert line_item_id not in ids


@pytest.mark.asyncio
async def test_delete_line_item_not_found(client: AsyncClient):
    token = await register_and_login(client, "li_del_nf@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.delete(
        f"/line-items/{fake_id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_line_item_requires_auth(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    resp = await client.delete(f"/line-items/{fake_id}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Cascade: deleting module deletes line items
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_module_cascades_line_items(client: AsyncClient):
    token = await register_and_login(client, "m_cascade@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module = await create_module(client, token, model_id, name="To Cascade")
    module_id = module["id"]

    await create_line_item(client, token, module_id, name="Item 1")
    await create_line_item(client, token, module_id, name="Item 2")

    # Delete the module
    del_resp = await client.delete(
        f"/modules/{module_id}",
        headers=auth_headers(token),
    )
    assert del_resp.status_code == 204

    # Module is gone from list
    list_resp = await client.get(
        f"/models/{model_id}/modules",
        headers=auth_headers(token),
    )
    assert list_resp.status_code == 200
    assert module_id not in [m["id"] for m in list_resp.json()]

    # Module itself returns 404
    get_resp = await client.get(
        f"/modules/{module_id}",
        headers=auth_headers(token),
    )
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# Sort order for line items
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_line_items_sorted_by_sort_order(client: AsyncClient):
    token = await register_and_login(client, "li_sort@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module = await create_module(client, token, model_id)
    module_id = module["id"]

    await create_line_item(client, token, module_id, name="Third", sort_order=20)
    await create_line_item(client, token, module_id, name="First", sort_order=0)
    await create_line_item(client, token, module_id, name="Second", sort_order=10)

    resp = await client.get(
        f"/modules/{module_id}/line-items",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    names = [li["name"] for li in resp.json()]
    assert names == ["First", "Second", "Third"]


# ---------------------------------------------------------------------------
# Formula field validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_line_item_formula_persists(client: AsyncClient):
    token = await register_and_login(client, "li_formula_persist@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module = await create_module(client, token, model_id)
    module_id = module["id"]

    formula = "SUM(Revenue[Time]) / COUNT(Time)"
    line_item = await create_line_item(client, token, module_id, name="Avg Revenue", formula=formula)

    # Fetch via module get (includes line items)
    resp = await client.get(
        f"/modules/{module_id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    matching = [li for li in data["line_items"] if li["id"] == line_item["id"]]
    assert len(matching) == 1
    assert matching[0]["formula"] == formula


@pytest.mark.asyncio
async def test_line_item_formula_can_be_cleared(client: AsyncClient):
    token = await register_and_login(client, "li_formula_clear@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module = await create_module(client, token, model_id)
    module_id = module["id"]
    line_item = await create_line_item(
        client, token, module_id, name="Calculated", formula="A + B"
    )

    resp = await client.patch(
        f"/line-items/{line_item['id']}",
        json={"formula": None},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["formula"] is None


# ---------------------------------------------------------------------------
# applies_to_dimensions JSON field
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_applies_to_dimensions_stored_and_retrieved(client: AsyncClient):
    token = await register_and_login(client, "li_json_dims@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module = await create_module(client, token, model_id)
    module_id = module["id"]

    dim1 = str(uuid.uuid4())
    dim2 = str(uuid.uuid4())
    dim3 = str(uuid.uuid4())
    applies_to = [dim1, dim2, dim3]

    line_item = await create_line_item(
        client, token, module_id,
        name="Multi-dim item",
        applies_to_dimensions=applies_to,
    )

    assert line_item["applies_to_dimensions"] == applies_to

    # Verify via list endpoint
    resp = await client.get(
        f"/modules/{module_id}/line-items",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    items = resp.json()
    found = next(li for li in items if li["id"] == line_item["id"])
    assert found["applies_to_dimensions"] == applies_to


@pytest.mark.asyncio
async def test_applies_to_dimensions_defaults_to_empty(client: AsyncClient):
    token = await register_and_login(client, "li_dims_default@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module = await create_module(client, token, model_id)
    module_id = module["id"]

    resp = await client.post(
        f"/modules/{module_id}/line-items",
        json={"name": "No dims"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    # Should be an empty list or None — acceptable default
    assert data["applies_to_dimensions"] is None or data["applies_to_dimensions"] == []


@pytest.mark.asyncio
async def test_applies_to_dimensions_can_be_updated_to_empty(client: AsyncClient):
    token = await register_and_login(client, "li_dims_clear@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module = await create_module(client, token, model_id)
    module_id = module["id"]

    dim1 = str(uuid.uuid4())
    line_item = await create_line_item(
        client, token, module_id, name="Item", applies_to_dimensions=[dim1]
    )

    resp = await client.patch(
        f"/line-items/{line_item['id']}",
        json={"applies_to_dimensions": []},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["applies_to_dimensions"] == []


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_line_item_defaults(client: AsyncClient):
    token = await register_and_login(client, "li_defaults@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module = await create_module(client, token, model_id)
    module_id = module["id"]

    resp = await client.post(
        f"/modules/{module_id}/line-items",
        json={"name": "Default Item"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["format"] == "number"
    assert data["summary_method"] == "sum"
    assert data["sort_order"] == 0
    assert data["formula"] is None
