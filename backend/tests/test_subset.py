import uuid
from typing import Optional

import pytest
from httpx import AsyncClient

# Import subset models so they are registered with Base.metadata
# before conftest's setup_database fixture calls create_all.
from app.models.subset import (  # noqa: F401
    LineItemSubset,
    LineItemSubsetMember,
    ListSubset,
    ListSubsetMember,
)



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
    code: str = "A",
    parent_id: Optional[str] = None,
    sort_order: int = 0,
) -> dict:
    payload: dict = {"name": name, "code": code, "sort_order": sort_order}
    if parent_id is not None:
        payload["parent_id"] = parent_id
    resp = await client.post(
        f"/dimensions/{dimension_id}/items",
        json=payload,
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def create_module(
    client: AsyncClient,
    token: str,
    model_id: str,
    name: str = "Revenue Module",
) -> dict:
    resp = await client.post(
        f"/models/{model_id}/modules",
        json={"name": name},
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
    summary_method: str = "sum",
    sort_order: int = 0,
) -> dict:
    payload: dict = {
        "name": name,
        "format": format,
        "summary_method": summary_method,
        "sort_order": sort_order,
    }
    resp = await client.post(
        f"/modules/{module_id}/line-items",
        json=payload,
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def _setup_dimension_with_items(client, token):
    """Helper: create workspace > model > dimension > 3 items, return IDs."""
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dim = await create_dimension(client, token, model_id, name="Regions")
    dim_id = dim["id"]
    item_a = await create_item(client, token, dim_id, name="North America", code="NA")
    item_b = await create_item(client, token, dim_id, name="Europe", code="EU")
    item_c = await create_item(client, token, dim_id, name="Asia Pacific", code="APAC")
    return ws_id, model_id, dim_id, [item_a, item_b, item_c]


async def _setup_module_with_line_items(client, token):
    """Helper: create workspace > model > module > 3 line items, return IDs."""
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    mod = await create_module(client, token, model_id, name="Finance")
    mod_id = mod["id"]
    li_a = await create_line_item(client, token, mod_id, name="Revenue")
    li_b = await create_line_item(client, token, mod_id, name="Costs")
    li_c = await create_line_item(client, token, mod_id, name="Profit")
    return ws_id, model_id, mod_id, [li_a, li_b, li_c]


# ===========================================================================
# LIST SUBSET CRUD
# ===========================================================================

@pytest.mark.asyncio
async def test_create_list_subset_success(client: AsyncClient):
    token = await register_and_login(client, "ls_create@example.com")
    ws_id, model_id, dim_id, items = await _setup_dimension_with_items(client, token)

    resp = await client.post(
        f"/dimensions/{dim_id}/subsets",
        json={"name": "Key Regions", "description": "Important regions"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Key Regions"
    assert data["description"] == "Important regions"
    assert data["dimension_id"] == dim_id
    assert data["is_dynamic"] is False
    assert data["filter_expression"] is None
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_list_subset_dynamic(client: AsyncClient):
    token = await register_and_login(client, "ls_dyn@example.com")
    ws_id, model_id, dim_id, items = await _setup_dimension_with_items(client, token)

    resp = await client.post(
        f"/dimensions/{dim_id}/subsets",
        json={
            "name": "NA Subset",
            "is_dynamic": True,
            "filter_expression": "code:startswith:N",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["is_dynamic"] is True
    assert data["filter_expression"] == "code:startswith:N"


@pytest.mark.asyncio
async def test_create_list_subset_requires_auth(client: AsyncClient):
    fake_dim_id = str(uuid.uuid4())
    resp = await client.post(
        f"/dimensions/{fake_dim_id}/subsets",
        json={"name": "No Auth"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_list_subset_dimension_not_found(client: AsyncClient):
    token = await register_and_login(client, "ls_dim_nf@example.com")
    fake_dim_id = str(uuid.uuid4())

    resp = await client.post(
        f"/dimensions/{fake_dim_id}/subsets",
        json={"name": "Ghost"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_subsets_for_dimension(client: AsyncClient):
    token = await register_and_login(client, "ls_list@example.com")
    ws_id, model_id, dim_id, items = await _setup_dimension_with_items(client, token)

    await client.post(
        f"/dimensions/{dim_id}/subsets",
        json={"name": "Subset A"},
        headers=auth_headers(token),
    )
    await client.post(
        f"/dimensions/{dim_id}/subsets",
        json={"name": "Subset B"},
        headers=auth_headers(token),
    )

    resp = await client.get(
        f"/dimensions/{dim_id}/subsets",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    names = [s["name"] for s in resp.json()]
    assert "Subset A" in names
    assert "Subset B" in names


@pytest.mark.asyncio
async def test_list_subsets_empty(client: AsyncClient):
    token = await register_and_login(client, "ls_empty@example.com")
    ws_id, model_id, dim_id, items = await _setup_dimension_with_items(client, token)

    resp = await client.get(
        f"/dimensions/{dim_id}/subsets",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_subset_by_id(client: AsyncClient):
    token = await register_and_login(client, "ls_get@example.com")
    ws_id, model_id, dim_id, items = await _setup_dimension_with_items(client, token)

    create_resp = await client.post(
        f"/dimensions/{dim_id}/subsets",
        json={"name": "My Subset"},
        headers=auth_headers(token),
    )
    subset_id = create_resp.json()["id"]

    resp = await client.get(
        f"/subsets/{subset_id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "My Subset"
    assert resp.json()["id"] == subset_id


@pytest.mark.asyncio
async def test_get_subset_not_found(client: AsyncClient):
    token = await register_and_login(client, "ls_get_nf@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.get(
        f"/subsets/{fake_id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_list_subset(client: AsyncClient):
    token = await register_and_login(client, "ls_update@example.com")
    ws_id, model_id, dim_id, items = await _setup_dimension_with_items(client, token)

    create_resp = await client.post(
        f"/dimensions/{dim_id}/subsets",
        json={"name": "Old Name"},
        headers=auth_headers(token),
    )
    subset_id = create_resp.json()["id"]

    resp = await client.put(
        f"/subsets/{subset_id}",
        json={"name": "New Name", "description": "Updated"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"
    assert resp.json()["description"] == "Updated"


@pytest.mark.asyncio
async def test_update_list_subset_not_found(client: AsyncClient):
    token = await register_and_login(client, "ls_upd_nf@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.put(
        f"/subsets/{fake_id}",
        json={"name": "Ghost"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_list_subset(client: AsyncClient):
    token = await register_and_login(client, "ls_delete@example.com")
    ws_id, model_id, dim_id, items = await _setup_dimension_with_items(client, token)

    create_resp = await client.post(
        f"/dimensions/{dim_id}/subsets",
        json={"name": "To Delete"},
        headers=auth_headers(token),
    )
    subset_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/subsets/{subset_id}",
        headers=auth_headers(token),
    )
    assert del_resp.status_code == 204

    # Verify it's gone
    get_resp = await client.get(
        f"/subsets/{subset_id}",
        headers=auth_headers(token),
    )
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_list_subset_not_found(client: AsyncClient):
    token = await register_and_login(client, "ls_del_nf@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.delete(
        f"/subsets/{fake_id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ===========================================================================
# LIST SUBSET MEMBERS
# ===========================================================================

@pytest.mark.asyncio
async def test_add_members_to_list_subset(client: AsyncClient):
    token = await register_and_login(client, "lsm_add@example.com")
    ws_id, model_id, dim_id, items = await _setup_dimension_with_items(client, token)

    create_resp = await client.post(
        f"/dimensions/{dim_id}/subsets",
        json={"name": "Key Regions"},
        headers=auth_headers(token),
    )
    subset_id = create_resp.json()["id"]

    resp = await client.post(
        f"/subsets/{subset_id}/members",
        json={"dimension_item_ids": [items[0]["id"], items[1]["id"]]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_add_members_duplicate_skipped(client: AsyncClient):
    token = await register_and_login(client, "lsm_dup@example.com")
    ws_id, model_id, dim_id, items = await _setup_dimension_with_items(client, token)

    create_resp = await client.post(
        f"/dimensions/{dim_id}/subsets",
        json={"name": "Dedup"},
        headers=auth_headers(token),
    )
    subset_id = create_resp.json()["id"]

    # Add first time
    await client.post(
        f"/subsets/{subset_id}/members",
        json={"dimension_item_ids": [items[0]["id"]]},
        headers=auth_headers(token),
    )

    # Add same member again — should return empty (no new members)
    resp = await client.post(
        f"/subsets/{subset_id}/members",
        json={"dimension_item_ids": [items[0]["id"]]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    assert len(resp.json()) == 0  # Duplicate skipped


@pytest.mark.asyncio
async def test_add_members_invalid_item(client: AsyncClient):
    token = await register_and_login(client, "lsm_bad@example.com")
    ws_id, model_id, dim_id, items = await _setup_dimension_with_items(client, token)

    create_resp = await client.post(
        f"/dimensions/{dim_id}/subsets",
        json={"name": "Bad"},
        headers=auth_headers(token),
    )
    subset_id = create_resp.json()["id"]

    fake_item_id = str(uuid.uuid4())
    resp = await client.post(
        f"/subsets/{subset_id}/members",
        json={"dimension_item_ids": [fake_item_id]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_remove_member_from_list_subset(client: AsyncClient):
    token = await register_and_login(client, "lsm_rm@example.com")
    ws_id, model_id, dim_id, items = await _setup_dimension_with_items(client, token)

    create_resp = await client.post(
        f"/dimensions/{dim_id}/subsets",
        json={"name": "Remove Test"},
        headers=auth_headers(token),
    )
    subset_id = create_resp.json()["id"]

    add_resp = await client.post(
        f"/subsets/{subset_id}/members",
        json={"dimension_item_ids": [items[0]["id"]]},
        headers=auth_headers(token),
    )
    member_id = add_resp.json()[0]["id"]

    del_resp = await client.delete(
        f"/subsets/{subset_id}/members/{member_id}",
        headers=auth_headers(token),
    )
    assert del_resp.status_code == 204

    # Verify member is gone via resolved endpoint
    resolved = await client.get(
        f"/subsets/{subset_id}/resolved",
        headers=auth_headers(token),
    )
    assert len(resolved.json()["members"]) == 0


@pytest.mark.asyncio
async def test_remove_member_not_found(client: AsyncClient):
    token = await register_and_login(client, "lsm_rm_nf@example.com")
    ws_id, model_id, dim_id, items = await _setup_dimension_with_items(client, token)

    create_resp = await client.post(
        f"/dimensions/{dim_id}/subsets",
        json={"name": "NF"},
        headers=auth_headers(token),
    )
    subset_id = create_resp.json()["id"]
    fake_member_id = str(uuid.uuid4())

    resp = await client.delete(
        f"/subsets/{subset_id}/members/{fake_member_id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ===========================================================================
# DYNAMIC SUBSET RESOLUTION
# ===========================================================================

@pytest.mark.asyncio
async def test_resolve_static_subset(client: AsyncClient):
    token = await register_and_login(client, "res_static@example.com")
    ws_id, model_id, dim_id, items = await _setup_dimension_with_items(client, token)

    create_resp = await client.post(
        f"/dimensions/{dim_id}/subsets",
        json={"name": "Static"},
        headers=auth_headers(token),
    )
    subset_id = create_resp.json()["id"]

    # Add two members
    await client.post(
        f"/subsets/{subset_id}/members",
        json={"dimension_item_ids": [items[0]["id"], items[2]["id"]]},
        headers=auth_headers(token),
    )

    resp = await client.get(
        f"/subsets/{subset_id}/resolved",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["subset_name"] == "Static"
    assert data["is_dynamic"] is False
    assert len(data["members"]) == 2
    member_names = [m["name"] for m in data["members"]]
    assert "North America" in member_names
    assert "Asia Pacific" in member_names


@pytest.mark.asyncio
async def test_resolve_dynamic_subset_contains(client: AsyncClient):
    token = await register_and_login(client, "res_dyn_c@example.com")
    ws_id, model_id, dim_id, items = await _setup_dimension_with_items(client, token)

    create_resp = await client.post(
        f"/dimensions/{dim_id}/subsets",
        json={
            "name": "Contains America",
            "is_dynamic": True,
            "filter_expression": "name:contains:America",
        },
        headers=auth_headers(token),
    )
    subset_id = create_resp.json()["id"]

    resp = await client.get(
        f"/subsets/{subset_id}/resolved",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_dynamic"] is True
    assert len(data["members"]) == 1
    assert data["members"][0]["name"] == "North America"


@pytest.mark.asyncio
async def test_resolve_dynamic_subset_startswith(client: AsyncClient):
    token = await register_and_login(client, "res_dyn_sw@example.com")
    ws_id, model_id, dim_id, items = await _setup_dimension_with_items(client, token)

    create_resp = await client.post(
        f"/dimensions/{dim_id}/subsets",
        json={
            "name": "Code starts with A",
            "is_dynamic": True,
            "filter_expression": "code:startswith:A",
        },
        headers=auth_headers(token),
    )
    subset_id = create_resp.json()["id"]

    resp = await client.get(
        f"/subsets/{subset_id}/resolved",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["members"]) == 1
    assert data["members"][0]["code"] == "APAC"


@pytest.mark.asyncio
async def test_resolve_dynamic_subset_eq(client: AsyncClient):
    token = await register_and_login(client, "res_dyn_eq@example.com")
    ws_id, model_id, dim_id, items = await _setup_dimension_with_items(client, token)

    create_resp = await client.post(
        f"/dimensions/{dim_id}/subsets",
        json={
            "name": "Exact EU",
            "is_dynamic": True,
            "filter_expression": "code:eq:EU",
        },
        headers=auth_headers(token),
    )
    subset_id = create_resp.json()["id"]

    resp = await client.get(
        f"/subsets/{subset_id}/resolved",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["members"]) == 1
    assert data["members"][0]["code"] == "EU"


@pytest.mark.asyncio
async def test_resolve_dynamic_subset_regex(client: AsyncClient):
    token = await register_and_login(client, "res_dyn_re@example.com")
    ws_id, model_id, dim_id, items = await _setup_dimension_with_items(client, token)

    create_resp = await client.post(
        f"/dimensions/{dim_id}/subsets",
        json={
            "name": "Regex Match",
            "is_dynamic": True,
            "filter_expression": "name:matches:^(North|Europe)",
        },
        headers=auth_headers(token),
    )
    subset_id = create_resp.json()["id"]

    resp = await client.get(
        f"/subsets/{subset_id}/resolved",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["members"]) == 2
    names = [m["name"] for m in data["members"]]
    assert "North America" in names
    assert "Europe" in names


@pytest.mark.asyncio
async def test_resolve_dynamic_subset_no_match(client: AsyncClient):
    token = await register_and_login(client, "res_dyn_nm@example.com")
    ws_id, model_id, dim_id, items = await _setup_dimension_with_items(client, token)

    create_resp = await client.post(
        f"/dimensions/{dim_id}/subsets",
        json={
            "name": "No Match",
            "is_dynamic": True,
            "filter_expression": "code:eq:ZZZZZ",
        },
        headers=auth_headers(token),
    )
    subset_id = create_resp.json()["id"]

    resp = await client.get(
        f"/subsets/{subset_id}/resolved",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert len(resp.json()["members"]) == 0


# ===========================================================================
# LINE ITEM SUBSET CRUD
# ===========================================================================

@pytest.mark.asyncio
async def test_create_line_item_subset_success(client: AsyncClient):
    token = await register_and_login(client, "lis_create@example.com")
    ws_id, model_id, mod_id, line_items = await _setup_module_with_line_items(client, token)

    resp = await client.post(
        f"/modules/{mod_id}/line-item-subsets",
        json={"name": "Financial KPIs", "description": "Key financial line items"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Financial KPIs"
    assert data["description"] == "Key financial line items"
    assert data["module_id"] == mod_id
    assert "id" in data


@pytest.mark.asyncio
async def test_create_line_item_subset_requires_auth(client: AsyncClient):
    fake_mod_id = str(uuid.uuid4())
    resp = await client.post(
        f"/modules/{fake_mod_id}/line-item-subsets",
        json={"name": "No Auth"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_line_item_subset_module_not_found(client: AsyncClient):
    token = await register_and_login(client, "lis_mod_nf@example.com")
    fake_mod_id = str(uuid.uuid4())

    resp = await client.post(
        f"/modules/{fake_mod_id}/line-item-subsets",
        json={"name": "Ghost"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_line_item_subsets(client: AsyncClient):
    token = await register_and_login(client, "lis_list@example.com")
    ws_id, model_id, mod_id, line_items = await _setup_module_with_line_items(client, token)

    await client.post(
        f"/modules/{mod_id}/line-item-subsets",
        json={"name": "Subset A"},
        headers=auth_headers(token),
    )
    await client.post(
        f"/modules/{mod_id}/line-item-subsets",
        json={"name": "Subset B"},
        headers=auth_headers(token),
    )

    resp = await client.get(
        f"/modules/{mod_id}/line-item-subsets",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    names = [s["name"] for s in resp.json()]
    assert "Subset A" in names
    assert "Subset B" in names


@pytest.mark.asyncio
async def test_get_line_item_subset_by_id(client: AsyncClient):
    token = await register_and_login(client, "lis_get@example.com")
    ws_id, model_id, mod_id, line_items = await _setup_module_with_line_items(client, token)

    create_resp = await client.post(
        f"/modules/{mod_id}/line-item-subsets",
        json={"name": "Detail"},
        headers=auth_headers(token),
    )
    subset_id = create_resp.json()["id"]

    resp = await client.get(
        f"/line-item-subsets/{subset_id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Detail"


@pytest.mark.asyncio
async def test_update_line_item_subset(client: AsyncClient):
    token = await register_and_login(client, "lis_upd@example.com")
    ws_id, model_id, mod_id, line_items = await _setup_module_with_line_items(client, token)

    create_resp = await client.post(
        f"/modules/{mod_id}/line-item-subsets",
        json={"name": "Old"},
        headers=auth_headers(token),
    )
    subset_id = create_resp.json()["id"]

    resp = await client.put(
        f"/line-item-subsets/{subset_id}",
        json={"name": "Renamed", "description": "Now with desc"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"
    assert resp.json()["description"] == "Now with desc"


@pytest.mark.asyncio
async def test_delete_line_item_subset(client: AsyncClient):
    token = await register_and_login(client, "lis_del@example.com")
    ws_id, model_id, mod_id, line_items = await _setup_module_with_line_items(client, token)

    create_resp = await client.post(
        f"/modules/{mod_id}/line-item-subsets",
        json={"name": "To Delete"},
        headers=auth_headers(token),
    )
    subset_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/line-item-subsets/{subset_id}",
        headers=auth_headers(token),
    )
    assert del_resp.status_code == 204

    get_resp = await client.get(
        f"/line-item-subsets/{subset_id}",
        headers=auth_headers(token),
    )
    assert get_resp.status_code == 404


# ===========================================================================
# LINE ITEM SUBSET MEMBERS
# ===========================================================================

@pytest.mark.asyncio
async def test_add_line_item_members(client: AsyncClient):
    token = await register_and_login(client, "lism_add@example.com")
    ws_id, model_id, mod_id, line_items = await _setup_module_with_line_items(client, token)

    create_resp = await client.post(
        f"/modules/{mod_id}/line-item-subsets",
        json={"name": "KPIs"},
        headers=auth_headers(token),
    )
    subset_id = create_resp.json()["id"]

    resp = await client.post(
        f"/line-item-subsets/{subset_id}/members",
        json={"line_item_ids": [line_items[0]["id"], line_items[2]["id"]]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_add_line_item_members_invalid(client: AsyncClient):
    token = await register_and_login(client, "lism_bad@example.com")
    ws_id, model_id, mod_id, line_items = await _setup_module_with_line_items(client, token)

    create_resp = await client.post(
        f"/modules/{mod_id}/line-item-subsets",
        json={"name": "Bad"},
        headers=auth_headers(token),
    )
    subset_id = create_resp.json()["id"]

    fake_li_id = str(uuid.uuid4())
    resp = await client.post(
        f"/line-item-subsets/{subset_id}/members",
        json={"line_item_ids": [fake_li_id]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_remove_line_item_member(client: AsyncClient):
    token = await register_and_login(client, "lism_rm@example.com")
    ws_id, model_id, mod_id, line_items = await _setup_module_with_line_items(client, token)

    create_resp = await client.post(
        f"/modules/{mod_id}/line-item-subsets",
        json={"name": "Remove Test"},
        headers=auth_headers(token),
    )
    subset_id = create_resp.json()["id"]

    add_resp = await client.post(
        f"/line-item-subsets/{subset_id}/members",
        json={"line_item_ids": [line_items[0]["id"]]},
        headers=auth_headers(token),
    )
    member_id = add_resp.json()[0]["id"]

    del_resp = await client.delete(
        f"/line-item-subsets/{subset_id}/members/{member_id}",
        headers=auth_headers(token),
    )
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_resolve_line_item_subset(client: AsyncClient):
    token = await register_and_login(client, "lism_res@example.com")
    ws_id, model_id, mod_id, line_items = await _setup_module_with_line_items(client, token)

    create_resp = await client.post(
        f"/modules/{mod_id}/line-item-subsets",
        json={"name": "Resolved"},
        headers=auth_headers(token),
    )
    subset_id = create_resp.json()["id"]

    await client.post(
        f"/line-item-subsets/{subset_id}/members",
        json={"line_item_ids": [line_items[0]["id"], line_items[1]["id"]]},
        headers=auth_headers(token),
    )

    resp = await client.get(
        f"/line-item-subsets/{subset_id}/resolved",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["subset_name"] == "Resolved"
    assert len(data["members"]) == 2
    names = [m["name"] for m in data["members"]]
    assert "Revenue" in names
    assert "Costs" in names


@pytest.mark.asyncio
async def test_resolve_line_item_subset_not_found(client: AsyncClient):
    token = await register_and_login(client, "lism_res_nf@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.get(
        f"/line-item-subsets/{fake_id}/resolved",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404
