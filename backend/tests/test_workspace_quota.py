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
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def create_workspace(
    client: AsyncClient, token: str, name: str = "Quota Workspace"
) -> str:
    resp = await client.post(
        "/workspaces/",
        json={"name": name},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def update_workspace_quota(
    client: AsyncClient,
    token: str,
    workspace_id: str,
    payload: dict,
) -> dict:
    resp = await client.put(
        f"/workspaces/{workspace_id}/quota",
        json=payload,
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def create_model(
    client: AsyncClient,
    token: str,
    workspace_id: str,
    name: str = "Quota Model",
) -> str:
    resp = await client.post(
        "/models",
        json={"name": name, "workspace_id": workspace_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def create_dimension(
    client: AsyncClient,
    token: str,
    model_id: str,
    name: str = "Products",
) -> str:
    resp = await client.post(
        f"/models/{model_id}/dimensions",
        json={"name": name, "dimension_type": "custom"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def create_module(
    client: AsyncClient,
    token: str,
    model_id: str,
    name: str = "Sales Module",
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
) -> str:
    resp = await client.post(
        f"/modules/{module_id}/line-items",
        json={"name": name, "format": "number"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_workspace_quota_defaults_created(client: AsyncClient):
    token = await register_and_login(client, "quota_defaults@example.com")
    workspace_id = await create_workspace(client, token)

    resp = await client.get(
        f"/workspaces/{workspace_id}/quota",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["workspace_id"] == workspace_id
    assert data["max_models"] == 100
    assert data["max_cells_per_model"] == 1_000_000
    assert data["max_dimensions_per_model"] == 200
    assert data["storage_limit_mb"] == 1024


@pytest.mark.asyncio
async def test_update_workspace_quota(client: AsyncClient):
    token = await register_and_login(client, "quota_update@example.com")
    workspace_id = await create_workspace(client, token)

    data = await update_workspace_quota(
        client,
        token,
        workspace_id,
        {
            "max_models": 2,
            "max_cells_per_model": 50,
            "max_dimensions_per_model": 5,
            "storage_limit_mb": 10,
        },
    )
    assert data["max_models"] == 2
    assert data["max_cells_per_model"] == 50
    assert data["max_dimensions_per_model"] == 5
    assert data["storage_limit_mb"] == 10


@pytest.mark.asyncio
async def test_workspace_quota_requires_owner(client: AsyncClient):
    token_a = await register_and_login(client, "quota_owner_a@example.com")
    token_b = await register_and_login(client, "quota_owner_b@example.com")
    workspace_id = await create_workspace(client, token_a)

    resp = await client.get(
        f"/workspaces/{workspace_id}/quota",
        headers=auth_headers(token_b),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_enforce_max_models_on_create(client: AsyncClient):
    token = await register_and_login(client, "quota_models@example.com")
    workspace_id = await create_workspace(client, token)
    await update_workspace_quota(
        client,
        token,
        workspace_id,
        {"max_models": 1},
    )

    await create_model(client, token, workspace_id, name="Model A")
    resp = await client.post(
        "/models",
        json={"name": "Model B", "workspace_id": workspace_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 409
    assert "model quota exceeded" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_enforce_max_models_on_clone(client: AsyncClient):
    token = await register_and_login(client, "quota_clone@example.com")
    workspace_id = await create_workspace(client, token)
    model_id = await create_model(client, token, workspace_id, name="Source")
    await update_workspace_quota(client, token, workspace_id, {"max_models": 1})

    resp = await client.post(
        f"/models/{model_id}/clone",
        json={"name": "Clone"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 409
    assert "model quota exceeded" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_enforce_max_dimensions_per_model(client: AsyncClient):
    token = await register_and_login(client, "quota_dims@example.com")
    workspace_id = await create_workspace(client, token)
    model_id = await create_model(client, token, workspace_id)
    await update_workspace_quota(
        client,
        token,
        workspace_id,
        {"max_dimensions_per_model": 1},
    )

    await create_dimension(client, token, model_id, name="D1")
    resp = await client.post(
        f"/models/{model_id}/dimensions",
        json={"name": "D2", "dimension_type": "custom"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 409
    assert "dimension quota exceeded" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_enforce_max_dimensions_for_time_dimensions(client: AsyncClient):
    token = await register_and_login(client, "quota_time_dims@example.com")
    workspace_id = await create_workspace(client, token)
    model_id = await create_model(client, token, workspace_id)
    await update_workspace_quota(
        client,
        token,
        workspace_id,
        {"max_dimensions_per_model": 1},
    )

    first = await client.post(
        f"/models/{model_id}/time-dimensions",
        json={
            "name": "Time",
            "start_year": 2024,
            "end_year": 2024,
            "granularity": "month",
        },
        headers=auth_headers(token),
    )
    assert first.status_code == 201

    second = await client.post(
        f"/models/{model_id}/time-dimensions",
        json={
            "name": "Time 2",
            "start_year": 2024,
            "end_year": 2024,
            "granularity": "month",
        },
        headers=auth_headers(token),
    )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_enforce_max_cells_per_model(client: AsyncClient):
    token = await register_and_login(client, "quota_cells@example.com")
    workspace_id = await create_workspace(client, token)
    model_id = await create_model(client, token, workspace_id)
    module_id = await create_module(client, token, model_id)
    line_item_id = await create_line_item(client, token, module_id)
    await update_workspace_quota(
        client,
        token,
        workspace_id,
        {"max_cells_per_model": 1},
    )

    first = await client.post(
        "/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": [str(uuid.uuid4())],
            "value": 1,
        },
        headers=auth_headers(token),
    )
    assert first.status_code == 200

    second = await client.post(
        "/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": [str(uuid.uuid4())],
            "value": 2,
        },
        headers=auth_headers(token),
    )
    assert second.status_code == 409
    assert "cell quota exceeded" in second.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cell_upsert_does_not_consume_extra_quota(client: AsyncClient):
    token = await register_and_login(client, "quota_upsert@example.com")
    workspace_id = await create_workspace(client, token)
    model_id = await create_model(client, token, workspace_id)
    module_id = await create_module(client, token, model_id)
    line_item_id = await create_line_item(client, token, module_id)
    await update_workspace_quota(
        client,
        token,
        workspace_id,
        {"max_cells_per_model": 1},
    )

    dim_member = str(uuid.uuid4())
    first = await client.post(
        "/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": [dim_member],
            "value": 10,
        },
        headers=auth_headers(token),
    )
    assert first.status_code == 200

    second = await client.post(
        "/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": [dim_member],
            "value": 99,
        },
        headers=auth_headers(token),
    )
    assert second.status_code == 200
    assert second.json()["value"] == 99.0


@pytest.mark.asyncio
async def test_enforce_storage_limit_mb_on_cell_write(client: AsyncClient):
    token = await register_and_login(client, "quota_storage@example.com")
    workspace_id = await create_workspace(client, token)
    model_id = await create_model(client, token, workspace_id)
    module_id = await create_module(client, token, model_id)
    line_item_id = await create_line_item(client, token, module_id)
    await update_workspace_quota(
        client,
        token,
        workspace_id,
        {"storage_limit_mb": 1},
    )

    huge_value = "x" * 1_100_000
    resp = await client.post(
        "/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": [str(uuid.uuid4())],
            "value": huge_value,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 409
    assert "storage quota exceeded" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_workspace_quota_usage_summary(client: AsyncClient):
    token = await register_and_login(client, "quota_usage@example.com")
    workspace_id = await create_workspace(client, token)
    model_id = await create_model(client, token, workspace_id, name="Usage Model")
    await create_dimension(client, token, model_id, name="Region")
    module_id = await create_module(client, token, model_id)
    line_item_id = await create_line_item(client, token, module_id)

    await client.post(
        "/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": [str(uuid.uuid4())],
            "value": 12,
        },
        headers=auth_headers(token),
    )
    await client.post(
        "/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": [str(uuid.uuid4())],
            "value": 34,
        },
        headers=auth_headers(token),
    )

    resp = await client.get(
        f"/workspaces/{workspace_id}/quota/usage",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["workspace_id"] == workspace_id
    assert data["model_count"] == 1
    assert data["total_dimension_count"] == 1
    assert data["total_cell_count"] == 2
    assert len(data["models"]) == 1
    assert data["models"][0]["model_name"] == "Usage Model"
