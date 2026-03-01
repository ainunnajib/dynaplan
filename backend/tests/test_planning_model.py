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


async def create_workspace(client: AsyncClient, token: str, name: str = "Test Workspace") -> str:
    resp = await client.post(
        "/workspaces/",
        json={"name": name},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_model(
    client: AsyncClient,
    token: str,
    workspace_id: str,
    name: str = "My Model",
    description: Optional[str] = None,
    settings: Optional[dict] = None,
) -> dict:
    payload: dict = {"name": name, "workspace_id": workspace_id}
    if description is not None:
        payload["description"] = description
    if settings is not None:
        payload["settings"] = settings
    resp = await client.post("/models", json=payload, headers=auth_headers(token))
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Create model
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_model_success(client: AsyncClient):
    token = await register_and_login(client, "m_create@example.com")
    ws_id = await create_workspace(client, token)

    resp = await client.post(
        "/models",
        json={"name": "Forecast Model", "workspace_id": ws_id, "description": "Annual forecast"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Forecast Model"
    assert data["description"] == "Annual forecast"
    assert data["workspace_id"] == ws_id
    assert "owner_id" in data
    assert data["is_archived"] is False
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_model_with_settings(client: AsyncClient):
    token = await register_and_login(client, "m_settings@example.com")
    ws_id = await create_workspace(client, token)

    resp = await client.post(
        "/models",
        json={
            "name": "Model With Settings",
            "workspace_id": ws_id,
            "settings": {"fiscal_year_start": "April", "currency": "USD"},
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["settings"]["fiscal_year_start"] == "April"
    assert data["settings"]["currency"] == "USD"


@pytest.mark.asyncio
async def test_create_model_no_description(client: AsyncClient):
    token = await register_and_login(client, "m_nodesc@example.com")
    ws_id = await create_workspace(client, token)

    resp = await client.post(
        "/models",
        json={"name": "No Desc Model", "workspace_id": ws_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    assert resp.json()["description"] is None


@pytest.mark.asyncio
async def test_create_model_requires_auth(client: AsyncClient):
    fake_ws_id = str(uuid.uuid4())
    resp = await client.post(
        "/models",
        json={"name": "Unauth Model", "workspace_id": fake_ws_id},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# List models for workspace
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_models_empty(client: AsyncClient):
    token = await register_and_login(client, "m_list_empty@example.com")
    ws_id = await create_workspace(client, token)

    resp = await client.get(f"/models/workspace/{ws_id}", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_models_returns_created(client: AsyncClient):
    token = await register_and_login(client, "m_list_created@example.com")
    ws_id = await create_workspace(client, token)

    await create_model(client, token, ws_id, name="Model A")
    await create_model(client, token, ws_id, name="Model B")

    resp = await client.get(f"/models/workspace/{ws_id}", headers=auth_headers(token))
    assert resp.status_code == 200
    names = [m["name"] for m in resp.json()]
    assert "Model A" in names
    assert "Model B" in names


@pytest.mark.asyncio
async def test_list_models_excludes_archived_by_default(client: AsyncClient):
    token = await register_and_login(client, "m_list_arch@example.com")
    ws_id = await create_workspace(client, token)

    active = await create_model(client, token, ws_id, name="Active Model")
    archived_data = await create_model(client, token, ws_id, name="Archived Model")
    model_id = archived_data["id"]

    await client.post(f"/models/{model_id}/archive", headers=auth_headers(token))

    resp = await client.get(f"/models/workspace/{ws_id}", headers=auth_headers(token))
    assert resp.status_code == 200
    names = [m["name"] for m in resp.json()]
    assert "Active Model" in names
    assert "Archived Model" not in names


@pytest.mark.asyncio
async def test_list_models_includes_archived_when_requested(client: AsyncClient):
    token = await register_and_login(client, "m_list_arch_incl@example.com")
    ws_id = await create_workspace(client, token)

    await create_model(client, token, ws_id, name="Active")
    archived_data = await create_model(client, token, ws_id, name="Archived")
    model_id = archived_data["id"]
    await client.post(f"/models/{model_id}/archive", headers=auth_headers(token))

    resp = await client.get(
        f"/models/workspace/{ws_id}",
        params={"include_archived": "true"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    names = [m["name"] for m in resp.json()]
    assert "Active" in names
    assert "Archived" in names


@pytest.mark.asyncio
async def test_list_models_requires_auth(client: AsyncClient):
    fake_ws_id = str(uuid.uuid4())
    resp = await client.get(f"/models/workspace/{fake_ws_id}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Get single model
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_model_success(client: AsyncClient):
    token = await register_and_login(client, "m_get@example.com")
    ws_id = await create_workspace(client, token)
    model_data = await create_model(client, token, ws_id, name="Fetch Me")
    model_id = model_data["id"]

    resp = await client.get(f"/models/{model_id}", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["name"] == "Fetch Me"


@pytest.mark.asyncio
async def test_get_model_not_found(client: AsyncClient):
    token = await register_and_login(client, "m_notfound@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.get(f"/models/{fake_id}", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_model_requires_auth(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/models/{fake_id}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Update model
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_model_name(client: AsyncClient):
    token = await register_and_login(client, "m_update_name@example.com")
    ws_id = await create_workspace(client, token)
    model_data = await create_model(client, token, ws_id, name="Old Name")
    model_id = model_data["id"]

    resp = await client.patch(
        f"/models/{model_id}",
        json={"name": "New Name"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_update_model_description(client: AsyncClient):
    token = await register_and_login(client, "m_update_desc@example.com")
    ws_id = await create_workspace(client, token)
    model_data = await create_model(client, token, ws_id, name="Desc Model", description="original")
    model_id = model_data["id"]

    resp = await client.patch(
        f"/models/{model_id}",
        json={"description": "updated"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Desc Model"
    assert data["description"] == "updated"


@pytest.mark.asyncio
async def test_update_model_settings(client: AsyncClient):
    token = await register_and_login(client, "m_update_settings@example.com")
    ws_id = await create_workspace(client, token)
    model_data = await create_model(client, token, ws_id, name="Settings Model")
    model_id = model_data["id"]

    resp = await client.patch(
        f"/models/{model_id}",
        json={"settings": {"currency": "EUR"}},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["settings"]["currency"] == "EUR"


@pytest.mark.asyncio
async def test_update_model_not_found(client: AsyncClient):
    token = await register_and_login(client, "m_update_notfound@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.patch(
        f"/models/{fake_id}",
        json={"name": "Ghost"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Archive / Unarchive
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_archive_model(client: AsyncClient):
    token = await register_and_login(client, "m_archive@example.com")
    ws_id = await create_workspace(client, token)
    model_data = await create_model(client, token, ws_id, name="To Archive")
    model_id = model_data["id"]

    resp = await client.post(f"/models/{model_id}/archive", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["is_archived"] is True


@pytest.mark.asyncio
async def test_unarchive_model(client: AsyncClient):
    token = await register_and_login(client, "m_unarchive@example.com")
    ws_id = await create_workspace(client, token)
    model_data = await create_model(client, token, ws_id, name="To Unarchive")
    model_id = model_data["id"]

    await client.post(f"/models/{model_id}/archive", headers=auth_headers(token))

    resp = await client.post(f"/models/{model_id}/unarchive", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["is_archived"] is False


@pytest.mark.asyncio
async def test_archive_model_not_found(client: AsyncClient):
    token = await register_and_login(client, "m_arch_notfound@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.post(f"/models/{fake_id}/archive", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_archive_requires_auth(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    resp = await client.post(f"/models/{fake_id}/archive")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Clone model
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_clone_model_same_workspace(client: AsyncClient):
    token = await register_and_login(client, "m_clone@example.com")
    ws_id = await create_workspace(client, token)
    model_data = await create_model(
        client, token, ws_id, name="Original",
        description="original desc",
        settings={"currency": "USD"},
    )
    model_id = model_data["id"]

    resp = await client.post(
        f"/models/{model_id}/clone",
        json={"name": "Clone of Original"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Clone of Original"
    assert data["description"] == "original desc"
    assert data["workspace_id"] == ws_id
    assert data["settings"]["currency"] == "USD"
    assert data["id"] != model_id
    assert data["is_archived"] is False


@pytest.mark.asyncio
async def test_clone_model_different_workspace(client: AsyncClient):
    token = await register_and_login(client, "m_clone_ws@example.com")
    ws1_id = await create_workspace(client, token, name="WS 1")
    ws2_id = await create_workspace(client, token, name="WS 2")
    model_data = await create_model(client, token, ws1_id, name="Source Model")
    model_id = model_data["id"]

    resp = await client.post(
        f"/models/{model_id}/clone",
        json={"name": "Moved Clone", "workspace_id": ws2_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["workspace_id"] == ws2_id
    assert data["name"] == "Moved Clone"


@pytest.mark.asyncio
async def test_clone_model_not_found(client: AsyncClient):
    token = await register_and_login(client, "m_clone_notfound@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.post(
        f"/models/{fake_id}/clone",
        json={"name": "Ghost Clone"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_clone_requires_auth(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    resp = await client.post(f"/models/{fake_id}/clone", json={"name": "Clone"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Delete model
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_model(client: AsyncClient):
    token = await register_and_login(client, "m_delete@example.com")
    ws_id = await create_workspace(client, token)
    model_data = await create_model(client, token, ws_id, name="Delete Me")
    model_id = model_data["id"]

    del_resp = await client.delete(f"/models/{model_id}", headers=auth_headers(token))
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/models/{model_id}", headers=auth_headers(token))
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_model_not_found(client: AsyncClient):
    token = await register_and_login(client, "m_del_notfound@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.delete(f"/models/{fake_id}", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_requires_auth(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    resp = await client.delete(f"/models/{fake_id}")
    assert resp.status_code == 401
