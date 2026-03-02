import uuid

import pytest
from httpx import AsyncClient


async def register_and_login(
    client: AsyncClient, email: str, password: str = "testpass123"
) -> str:
    await client.post(
        "/auth/register",
        json={
            "email": email,
            "full_name": "Test User",
            "password": password,
        },
    )
    resp = await client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def create_workspace(client: AsyncClient, token: str) -> str:
    resp = await client.post(
        "/workspaces/",
        json={"name": "Workspace"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_model(client: AsyncClient, token: str, workspace_id: str) -> str:
    resp = await client.post(
        "/models",
        json={"name": "Model", "workspace_id": workspace_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_module(client: AsyncClient, token: str, model_id: str) -> str:
    resp = await client.post(
        f"/models/{model_id}/modules",
        json={"name": "Sales"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def sample_view_config() -> dict:
    return {
        "row_dims": [str(uuid.uuid4())],
        "col_dims": [str(uuid.uuid4())],
        "filters": {
            str(uuid.uuid4()): [str(uuid.uuid4()), str(uuid.uuid4())],
        },
        "sort": {"column_key": "metric|actuals", "direction": "asc"},
    }


@pytest.mark.asyncio
async def test_saved_view_crud_flow(client: AsyncClient):
    token = await register_and_login(client, "saved_view_crud@example.com")
    workspace_id = await create_workspace(client, token)
    model_id = await create_model(client, token, workspace_id)
    module_id = await create_module(client, token, model_id)

    create_resp = await client.post(
        f"/modules/{module_id}/saved-views",
        json={
            "name": "Analyst View",
            "view_config": sample_view_config(),
            "is_default": False,
        },
        headers=auth_headers(token),
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    saved_view_id = created["id"]
    assert created["name"] == "Analyst View"
    assert created["module_id"] == module_id
    assert created["is_default"] is False
    assert created["view_config"]["sort"]["direction"] == "asc"

    list_resp = await client.get(
        f"/modules/{module_id}/saved-views",
        headers=auth_headers(token),
    )
    assert list_resp.status_code == 200
    listed = list_resp.json()
    assert len(listed) == 1
    assert listed[0]["id"] == saved_view_id

    get_resp = await client.get(
        f"/saved-views/{saved_view_id}",
        headers=auth_headers(token),
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Analyst View"

    patch_resp = await client.patch(
        f"/saved-views/{saved_view_id}",
        json={
            "name": "Updated Analyst View",
            "view_config": {
                **sample_view_config(),
                "sort": {"column_key": "metric|forecast", "direction": "desc"},
            },
            "is_default": True,
        },
        headers=auth_headers(token),
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.json()
    assert updated["name"] == "Updated Analyst View"
    assert updated["is_default"] is True
    assert updated["view_config"]["sort"]["direction"] == "desc"

    delete_resp = await client.delete(
        f"/saved-views/{saved_view_id}",
        headers=auth_headers(token),
    )
    assert delete_resp.status_code == 204

    list_after_delete_resp = await client.get(
        f"/modules/{module_id}/saved-views",
        headers=auth_headers(token),
    )
    assert list_after_delete_resp.status_code == 200
    assert list_after_delete_resp.json() == []


@pytest.mark.asyncio
async def test_saved_view_default_uniqueness_and_set_default(client: AsyncClient):
    token = await register_and_login(client, "saved_view_default@example.com")
    workspace_id = await create_workspace(client, token)
    model_id = await create_model(client, token, workspace_id)
    module_id = await create_module(client, token, model_id)

    first_resp = await client.post(
        f"/modules/{module_id}/saved-views",
        json={
            "name": "First",
            "view_config": sample_view_config(),
            "is_default": True,
        },
        headers=auth_headers(token),
    )
    assert first_resp.status_code == 201
    first_id = first_resp.json()["id"]
    assert first_resp.json()["is_default"] is True

    second_resp = await client.post(
        f"/modules/{module_id}/saved-views",
        json={
            "name": "Second",
            "view_config": sample_view_config(),
            "is_default": True,
        },
        headers=auth_headers(token),
    )
    assert second_resp.status_code == 201
    second_id = second_resp.json()["id"]

    list_resp = await client.get(
        f"/modules/{module_id}/saved-views",
        headers=auth_headers(token),
    )
    assert list_resp.status_code == 200
    listed_by_id = {row["id"]: row for row in list_resp.json()}
    assert listed_by_id[first_id]["is_default"] is False
    assert listed_by_id[second_id]["is_default"] is True

    set_default_resp = await client.put(
        f"/saved-views/{first_id}/default",
        headers=auth_headers(token),
    )
    assert set_default_resp.status_code == 200
    assert set_default_resp.json()["is_default"] is True

    list_after_set_resp = await client.get(
        f"/modules/{module_id}/saved-views",
        headers=auth_headers(token),
    )
    assert list_after_set_resp.status_code == 200
    listed_after_set_by_id = {row["id"]: row for row in list_after_set_resp.json()}
    assert listed_after_set_by_id[first_id]["is_default"] is True
    assert listed_after_set_by_id[second_id]["is_default"] is False


@pytest.mark.asyncio
async def test_saved_view_is_user_scoped(client: AsyncClient):
    token_a = await register_and_login(client, "saved_view_scope_a@example.com")
    token_b = await register_and_login(client, "saved_view_scope_b@example.com")

    workspace_id = await create_workspace(client, token_a)
    model_id = await create_model(client, token_a, workspace_id)
    module_id = await create_module(client, token_a, model_id)

    create_resp = await client.post(
        f"/modules/{module_id}/saved-views",
        json={
            "name": "Private View",
            "view_config": sample_view_config(),
        },
        headers=auth_headers(token_a),
    )
    assert create_resp.status_code == 201
    saved_view_id = create_resp.json()["id"]

    list_b_resp = await client.get(
        f"/modules/{module_id}/saved-views",
        headers=auth_headers(token_b),
    )
    assert list_b_resp.status_code == 200
    assert list_b_resp.json() == []

    get_b_resp = await client.get(
        f"/saved-views/{saved_view_id}",
        headers=auth_headers(token_b),
    )
    assert get_b_resp.status_code == 404

    patch_b_resp = await client.patch(
        f"/saved-views/{saved_view_id}",
        json={"name": "Hijacked"},
        headers=auth_headers(token_b),
    )
    assert patch_b_resp.status_code == 404

    delete_b_resp = await client.delete(
        f"/saved-views/{saved_view_id}",
        headers=auth_headers(token_b),
    )
    assert delete_b_resp.status_code == 404


@pytest.mark.asyncio
async def test_saved_view_validation_and_duplicates(client: AsyncClient):
    token = await register_and_login(client, "saved_view_validation@example.com")
    workspace_id = await create_workspace(client, token)
    model_id = await create_model(client, token, workspace_id)
    module_id = await create_module(client, token, model_id)

    not_found_resp = await client.post(
        f"/modules/{uuid.uuid4()}/saved-views",
        json={"name": "Missing Module", "view_config": sample_view_config()},
        headers=auth_headers(token),
    )
    assert not_found_resp.status_code == 404

    create_resp = await client.post(
        f"/modules/{module_id}/saved-views",
        json={"name": "Unique Name", "view_config": sample_view_config()},
        headers=auth_headers(token),
    )
    assert create_resp.status_code == 201

    duplicate_resp = await client.post(
        f"/modules/{module_id}/saved-views",
        json={"name": "Unique Name", "view_config": sample_view_config()},
        headers=auth_headers(token),
    )
    assert duplicate_resp.status_code == 409

    blank_name_resp = await client.post(
        f"/modules/{module_id}/saved-views",
        json={"name": "   ", "view_config": sample_view_config()},
        headers=auth_headers(token),
    )
    assert blank_name_resp.status_code == 400
