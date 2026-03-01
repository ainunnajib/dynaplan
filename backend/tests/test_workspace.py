import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helper: register a user and return a bearer token
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


# ---------------------------------------------------------------------------
# Create workspace
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_workspace(client: AsyncClient):
    token = await register_and_login(client, "ws_create@example.com")

    resp = await client.post(
        "/workspaces/",
        json={"name": "My Workspace", "description": "A test workspace"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Workspace"
    assert data["description"] == "A test workspace"
    assert "id" in data
    assert "owner_id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_workspace_no_description(client: AsyncClient):
    token = await register_and_login(client, "ws_nodesc@example.com")

    resp = await client.post(
        "/workspaces/",
        json={"name": "No Desc Workspace"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "No Desc Workspace"
    assert data["description"] is None


@pytest.mark.asyncio
async def test_create_workspace_requires_auth(client: AsyncClient):
    resp = await client.post("/workspaces/", json={"name": "Unauthorized"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# List workspaces
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_workspaces_empty(client: AsyncClient):
    token = await register_and_login(client, "ws_list_empty@example.com")

    resp = await client.get("/workspaces/", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_workspaces_returns_own(client: AsyncClient):
    token = await register_and_login(client, "ws_list_own@example.com")

    await client.post("/workspaces/", json={"name": "WS One"}, headers=auth_headers(token))
    await client.post("/workspaces/", json={"name": "WS Two"}, headers=auth_headers(token))

    resp = await client.get("/workspaces/", headers=auth_headers(token))
    assert resp.status_code == 200
    names = [w["name"] for w in resp.json()]
    assert "WS One" in names
    assert "WS Two" in names


@pytest.mark.asyncio
async def test_list_workspaces_only_own(client: AsyncClient):
    """User A's workspaces should not appear in User B's list."""
    token_a = await register_and_login(client, "ws_a@example.com")
    token_b = await register_and_login(client, "ws_b@example.com")

    await client.post("/workspaces/", json={"name": "Alice WS"}, headers=auth_headers(token_a))

    resp = await client.get("/workspaces/", headers=auth_headers(token_b))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_workspaces_requires_auth(client: AsyncClient):
    resp = await client.get("/workspaces/")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Get single workspace
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_workspace(client: AsyncClient):
    token = await register_and_login(client, "ws_get@example.com")

    create_resp = await client.post(
        "/workspaces/",
        json={"name": "Fetch Me", "description": "desc"},
        headers=auth_headers(token),
    )
    ws_id = create_resp.json()["id"]

    resp = await client.get(f"/workspaces/{ws_id}", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["name"] == "Fetch Me"


@pytest.mark.asyncio
async def test_get_workspace_not_found(client: AsyncClient):
    token = await register_and_login(client, "ws_notfound@example.com")

    import uuid
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/workspaces/{fake_id}", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_workspace_forbidden(client: AsyncClient):
    """User B cannot access User A's workspace."""
    token_a = await register_and_login(client, "ws_forbidden_a@example.com")
    token_b = await register_and_login(client, "ws_forbidden_b@example.com")

    create_resp = await client.post(
        "/workspaces/",
        json={"name": "A's workspace"},
        headers=auth_headers(token_a),
    )
    ws_id = create_resp.json()["id"]

    resp = await client.get(f"/workspaces/{ws_id}", headers=auth_headers(token_b))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Rename / update workspace
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rename_workspace(client: AsyncClient):
    token = await register_and_login(client, "ws_rename@example.com")

    create_resp = await client.post(
        "/workspaces/",
        json={"name": "Old Name"},
        headers=auth_headers(token),
    )
    ws_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/workspaces/{ws_id}",
        json={"name": "New Name"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_update_workspace_description(client: AsyncClient):
    token = await register_and_login(client, "ws_update_desc@example.com")

    create_resp = await client.post(
        "/workspaces/",
        json={"name": "WS Desc Update", "description": "original"},
        headers=auth_headers(token),
    )
    ws_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/workspaces/{ws_id}",
        json={"description": "updated"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "WS Desc Update"
    assert data["description"] == "updated"


@pytest.mark.asyncio
async def test_update_workspace_forbidden(client: AsyncClient):
    token_a = await register_and_login(client, "ws_upd_a@example.com")
    token_b = await register_and_login(client, "ws_upd_b@example.com")

    create_resp = await client.post(
        "/workspaces/",
        json={"name": "A's WS"},
        headers=auth_headers(token_a),
    )
    ws_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/workspaces/{ws_id}",
        json={"name": "Hijacked"},
        headers=auth_headers(token_b),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Delete workspace
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_workspace(client: AsyncClient):
    token = await register_and_login(client, "ws_delete@example.com")

    create_resp = await client.post(
        "/workspaces/",
        json={"name": "Delete Me"},
        headers=auth_headers(token),
    )
    ws_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/workspaces/{ws_id}", headers=auth_headers(token))
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/workspaces/{ws_id}", headers=auth_headers(token))
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_workspace_not_found(client: AsyncClient):
    token = await register_and_login(client, "ws_del_notfound@example.com")

    import uuid
    fake_id = str(uuid.uuid4())
    resp = await client.delete(f"/workspaces/{fake_id}", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_workspace_forbidden(client: AsyncClient):
    token_a = await register_and_login(client, "ws_del_a@example.com")
    token_b = await register_and_login(client, "ws_del_b@example.com")

    create_resp = await client.post(
        "/workspaces/",
        json={"name": "A's WS to delete"},
        headers=auth_headers(token_a),
    )
    ws_id = create_resp.json()["id"]

    resp = await client.delete(f"/workspaces/{ws_id}", headers=auth_headers(token_b))
    assert resp.status_code == 403
