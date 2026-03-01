"""
Tests for F043: SCIM user provisioning.

Covers:
- SCIM config CRUD (create, get, update)
- Config requires auth
- Config duplicate prevention (409)
- SCIM bearer token authentication for v2 endpoints
- Invalid/missing token returns 401
- User CRUD via SCIM v2 (list, get, create, update, patch/deactivate)
- User create duplicate returns 409
- User not found returns 404
- Group CRUD via SCIM v2 (list, get, create, update, delete)
- Group not found returns 404
- Group membership (add/remove members via PUT)
- Deactivation via PATCH
- Provisioning logs are recorded and retrievable
- SCIM list response format (totalResults, Resources, etc.)
- Filter users by userName
"""
import uuid

import pytest
from httpx import AsyncClient


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
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def scim_headers(scim_token: str) -> dict:
    return {"Authorization": f"Bearer {scim_token}"}


async def create_workspace(client: AsyncClient, token: str, name: str = "Test WS") -> str:
    resp = await client.post(
        "/workspaces/",
        json={"name": name},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


SCIM_TOKEN = "test-scim-bearer-token-12345"


async def setup_scim(client: AsyncClient, email: str = "scim_owner@example.com"):
    """Register user, create workspace, configure SCIM. Returns (jwt_token, workspace_id, scim_token)."""
    token = await register_and_login(client, email)
    ws_id = await create_workspace(client, token)
    resp = await client.post(
        f"/workspaces/{ws_id}/scim/config",
        json={"bearer_token": SCIM_TOKEN, "base_url": "http://test"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201, resp.text
    return token, ws_id, SCIM_TOKEN


# ---------------------------------------------------------------------------
# 1. SCIM Config CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_scim_config(client: AsyncClient):
    token = await register_and_login(client, "scim_cfg_create@example.com")
    ws_id = await create_workspace(client, token)

    resp = await client.post(
        f"/workspaces/{ws_id}/scim/config",
        json={"bearer_token": "my-token", "base_url": "http://test"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["workspace_id"] == ws_id
    assert data["is_enabled"] is True
    assert data["base_url"] == "http://test"
    assert "bearer_token" not in data
    assert "bearer_token_hash" not in data
    assert "id" in data


@pytest.mark.asyncio
async def test_get_scim_config(client: AsyncClient):
    token = await register_and_login(client, "scim_cfg_get@example.com")
    ws_id = await create_workspace(client, token)
    await client.post(
        f"/workspaces/{ws_id}/scim/config",
        json={"bearer_token": "tok", "base_url": "http://test"},
        headers=auth_headers(token),
    )

    resp = await client.get(
        f"/workspaces/{ws_id}/scim/config",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["workspace_id"] == ws_id
    assert data["is_enabled"] is True


@pytest.mark.asyncio
async def test_get_scim_config_not_found(client: AsyncClient):
    token = await register_and_login(client, "scim_cfg_404@example.com")
    ws_id = await create_workspace(client, token)

    resp = await client.get(
        f"/workspaces/{ws_id}/scim/config",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_scim_config(client: AsyncClient):
    token = await register_and_login(client, "scim_cfg_update@example.com")
    ws_id = await create_workspace(client, token)
    await client.post(
        f"/workspaces/{ws_id}/scim/config",
        json={"bearer_token": "tok", "base_url": "http://test"},
        headers=auth_headers(token),
    )

    resp = await client.put(
        f"/workspaces/{ws_id}/scim/config",
        json={"is_enabled": False, "base_url": "http://updated"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_enabled"] is False
    assert data["base_url"] == "http://updated"


@pytest.mark.asyncio
async def test_create_scim_config_duplicate(client: AsyncClient):
    token = await register_and_login(client, "scim_cfg_dup@example.com")
    ws_id = await create_workspace(client, token)

    resp1 = await client.post(
        f"/workspaces/{ws_id}/scim/config",
        json={"bearer_token": "tok1", "base_url": "http://test"},
        headers=auth_headers(token),
    )
    assert resp1.status_code == 201

    resp2 = await client.post(
        f"/workspaces/{ws_id}/scim/config",
        json={"bearer_token": "tok2", "base_url": "http://test"},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_create_scim_config_requires_auth(client: AsyncClient):
    fake_ws_id = str(uuid.uuid4())
    resp = await client.post(
        f"/workspaces/{fake_ws_id}/scim/config",
        json={"bearer_token": "tok", "base_url": "http://test"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 2. SCIM bearer token auth
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scim_v2_missing_token(client: AsyncClient):
    resp = await client.get("/scim/v2/Users")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_scim_v2_invalid_token(client: AsyncClient):
    resp = await client.get(
        "/scim/v2/Users",
        headers=scim_headers("bad-token"),
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_scim_v2_valid_token(client: AsyncClient):
    _, _, scim_tok = await setup_scim(client, "scim_auth_ok@example.com")
    resp = await client.get(
        "/scim/v2/Users",
        headers=scim_headers(scim_tok),
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 3. SCIM v2 User CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scim_list_users(client: AsyncClient):
    _, _, scim_tok = await setup_scim(client, "scim_list_u@example.com")
    resp = await client.get(
        "/scim/v2/Users",
        headers=scim_headers(scim_tok),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "totalResults" in data
    assert "Resources" in data
    assert data["schemas"] == ["urn:ietf:params:scim:api:messages:2.0:ListResponse"]


@pytest.mark.asyncio
async def test_scim_create_user(client: AsyncClient):
    _, _, scim_tok = await setup_scim(client, "scim_create_u@example.com")
    resp = await client.post(
        "/scim/v2/Users",
        json={
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": "alice@corp.com",
            "displayName": "Alice Smith",
            "active": True,
        },
        headers=scim_headers(scim_tok),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["userName"] == "alice@corp.com"
    assert data["displayName"] == "Alice Smith"
    assert data["active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_scim_create_user_duplicate(client: AsyncClient):
    _, _, scim_tok = await setup_scim(client, "scim_dup_u@example.com")
    payload = {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "userName": "dup@corp.com",
        "displayName": "Dup User",
    }
    resp1 = await client.post("/scim/v2/Users", json=payload, headers=scim_headers(scim_tok))
    assert resp1.status_code == 201

    resp2 = await client.post("/scim/v2/Users", json=payload, headers=scim_headers(scim_tok))
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_scim_get_user(client: AsyncClient):
    _, _, scim_tok = await setup_scim(client, "scim_get_u@example.com")
    create_resp = await client.post(
        "/scim/v2/Users",
        json={"userName": "getme@corp.com", "displayName": "Get Me"},
        headers=scim_headers(scim_tok),
    )
    user_id = create_resp.json()["id"]

    resp = await client.get(
        f"/scim/v2/Users/{user_id}",
        headers=scim_headers(scim_tok),
    )
    assert resp.status_code == 200
    assert resp.json()["userName"] == "getme@corp.com"


@pytest.mark.asyncio
async def test_scim_get_user_not_found(client: AsyncClient):
    _, _, scim_tok = await setup_scim(client, "scim_get_u404@example.com")
    fake_id = str(uuid.uuid4())
    resp = await client.get(
        f"/scim/v2/Users/{fake_id}",
        headers=scim_headers(scim_tok),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_scim_update_user(client: AsyncClient):
    _, _, scim_tok = await setup_scim(client, "scim_upd_u@example.com")
    create_resp = await client.post(
        "/scim/v2/Users",
        json={"userName": "updme@corp.com", "displayName": "Old Name"},
        headers=scim_headers(scim_tok),
    )
    user_id = create_resp.json()["id"]

    resp = await client.put(
        f"/scim/v2/Users/{user_id}",
        json={
            "userName": "updme@corp.com",
            "displayName": "New Name",
            "active": True,
        },
        headers=scim_headers(scim_tok),
    )
    assert resp.status_code == 200
    assert resp.json()["displayName"] == "New Name"


@pytest.mark.asyncio
async def test_scim_patch_deactivate_user(client: AsyncClient):
    _, _, scim_tok = await setup_scim(client, "scim_deact_u@example.com")
    create_resp = await client.post(
        "/scim/v2/Users",
        json={"userName": "deact@corp.com", "displayName": "Deact User"},
        headers=scim_headers(scim_tok),
    )
    user_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/scim/v2/Users/{user_id}",
        json={
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [
                {"op": "replace", "path": "active", "value": False},
            ],
        },
        headers=scim_headers(scim_tok),
    )
    assert resp.status_code == 200
    assert resp.json()["active"] is False


@pytest.mark.asyncio
async def test_scim_patch_user_not_found(client: AsyncClient):
    _, _, scim_tok = await setup_scim(client, "scim_patch404@example.com")
    fake_id = str(uuid.uuid4())
    resp = await client.patch(
        f"/scim/v2/Users/{fake_id}",
        json={
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [{"op": "replace", "path": "active", "value": False}],
        },
        headers=scim_headers(scim_tok),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_scim_filter_users_by_username(client: AsyncClient):
    _, _, scim_tok = await setup_scim(client, "scim_filter@example.com")
    await client.post(
        "/scim/v2/Users",
        json={"userName": "findme@corp.com", "displayName": "Find Me"},
        headers=scim_headers(scim_tok),
    )

    resp = await client.get(
        '/scim/v2/Users?filter=userName eq "findme@corp.com"',
        headers=scim_headers(scim_tok),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["totalResults"] >= 1
    usernames = [r["userName"] for r in data["Resources"]]
    assert "findme@corp.com" in usernames


# ---------------------------------------------------------------------------
# 4. SCIM v2 Group CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scim_create_group(client: AsyncClient):
    _, _, scim_tok = await setup_scim(client, "scim_cg@example.com")
    resp = await client.post(
        "/scim/v2/Groups",
        json={
            "displayName": "Engineering",
            "externalId": "eng-001",
        },
        headers=scim_headers(scim_tok),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["displayName"] == "Engineering"
    assert data["externalId"] == "eng-001"
    assert "id" in data


@pytest.mark.asyncio
async def test_scim_list_groups(client: AsyncClient):
    _, _, scim_tok = await setup_scim(client, "scim_lg@example.com")
    await client.post(
        "/scim/v2/Groups",
        json={"displayName": "GroupA"},
        headers=scim_headers(scim_tok),
    )

    resp = await client.get(
        "/scim/v2/Groups",
        headers=scim_headers(scim_tok),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["totalResults"] >= 1
    assert len(data["Resources"]) >= 1


@pytest.mark.asyncio
async def test_scim_get_group(client: AsyncClient):
    _, _, scim_tok = await setup_scim(client, "scim_gg@example.com")
    create_resp = await client.post(
        "/scim/v2/Groups",
        json={"displayName": "GetGroup"},
        headers=scim_headers(scim_tok),
    )
    group_id = create_resp.json()["id"]

    resp = await client.get(
        f"/scim/v2/Groups/{group_id}",
        headers=scim_headers(scim_tok),
    )
    assert resp.status_code == 200
    assert resp.json()["displayName"] == "GetGroup"


@pytest.mark.asyncio
async def test_scim_get_group_not_found(client: AsyncClient):
    _, _, scim_tok = await setup_scim(client, "scim_gg404@example.com")
    fake_id = str(uuid.uuid4())
    resp = await client.get(
        f"/scim/v2/Groups/{fake_id}",
        headers=scim_headers(scim_tok),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_scim_update_group(client: AsyncClient):
    _, _, scim_tok = await setup_scim(client, "scim_ug@example.com")
    create_resp = await client.post(
        "/scim/v2/Groups",
        json={"displayName": "OldGroup"},
        headers=scim_headers(scim_tok),
    )
    group_id = create_resp.json()["id"]

    resp = await client.put(
        f"/scim/v2/Groups/{group_id}",
        json={"displayName": "NewGroup"},
        headers=scim_headers(scim_tok),
    )
    assert resp.status_code == 200
    assert resp.json()["displayName"] == "NewGroup"


@pytest.mark.asyncio
async def test_scim_delete_group(client: AsyncClient):
    _, _, scim_tok = await setup_scim(client, "scim_dg@example.com")
    create_resp = await client.post(
        "/scim/v2/Groups",
        json={"displayName": "DelGroup"},
        headers=scim_headers(scim_tok),
    )
    group_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/scim/v2/Groups/{group_id}",
        headers=scim_headers(scim_tok),
    )
    assert del_resp.status_code == 204

    get_resp = await client.get(
        f"/scim/v2/Groups/{group_id}",
        headers=scim_headers(scim_tok),
    )
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_scim_delete_group_not_found(client: AsyncClient):
    _, _, scim_tok = await setup_scim(client, "scim_dg404@example.com")
    fake_id = str(uuid.uuid4())
    resp = await client.delete(
        f"/scim/v2/Groups/{fake_id}",
        headers=scim_headers(scim_tok),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 5. Group membership
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scim_group_with_members(client: AsyncClient):
    _, _, scim_tok = await setup_scim(client, "scim_mem@example.com")

    # Create a user
    user_resp = await client.post(
        "/scim/v2/Users",
        json={"userName": "member@corp.com", "displayName": "Member User"},
        headers=scim_headers(scim_tok),
    )
    user_id = user_resp.json()["id"]

    # Create group with member
    group_resp = await client.post(
        "/scim/v2/Groups",
        json={
            "displayName": "TeamX",
            "members": [{"value": user_id}],
        },
        headers=scim_headers(scim_tok),
    )
    assert group_resp.status_code == 201
    data = group_resp.json()
    assert len(data["members"]) == 1
    assert data["members"][0]["value"] == user_id


@pytest.mark.asyncio
async def test_scim_update_group_members(client: AsyncClient):
    _, _, scim_tok = await setup_scim(client, "scim_upmem@example.com")

    # Create two users
    u1_resp = await client.post(
        "/scim/v2/Users",
        json={"userName": "u1mem@corp.com", "displayName": "User 1"},
        headers=scim_headers(scim_tok),
    )
    u2_resp = await client.post(
        "/scim/v2/Users",
        json={"userName": "u2mem@corp.com", "displayName": "User 2"},
        headers=scim_headers(scim_tok),
    )
    u1_id = u1_resp.json()["id"]
    u2_id = u2_resp.json()["id"]

    # Create group with u1
    group_resp = await client.post(
        "/scim/v2/Groups",
        json={"displayName": "TeamY", "members": [{"value": u1_id}]},
        headers=scim_headers(scim_tok),
    )
    group_id = group_resp.json()["id"]

    # Update group to have only u2
    upd_resp = await client.put(
        f"/scim/v2/Groups/{group_id}",
        json={"displayName": "TeamY", "members": [{"value": u2_id}]},
        headers=scim_headers(scim_tok),
    )
    assert upd_resp.status_code == 200
    members = upd_resp.json()["members"]
    assert len(members) == 1
    assert members[0]["value"] == u2_id


# ---------------------------------------------------------------------------
# 6. Provisioning Logs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scim_provisioning_logs(client: AsyncClient):
    jwt_token, ws_id, scim_tok = await setup_scim(client, "scim_log@example.com")

    # Create a user to generate a log entry
    await client.post(
        "/scim/v2/Users",
        json={"userName": "loguser@corp.com", "displayName": "Log User"},
        headers=scim_headers(scim_tok),
    )

    resp = await client.get(
        f"/workspaces/{ws_id}/scim/logs",
        headers=auth_headers(jwt_token),
    )
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) >= 1
    assert logs[0]["operation"] == "create_user"
    assert logs[0]["status"] == "success"
    assert logs[0]["resource_type"] == "User"


@pytest.mark.asyncio
async def test_scim_provisioning_logs_require_auth(client: AsyncClient):
    fake_ws_id = str(uuid.uuid4())
    resp = await client.get(f"/workspaces/{fake_ws_id}/scim/logs")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_scim_deactivation_logged(client: AsyncClient):
    jwt_token, ws_id, scim_tok = await setup_scim(client, "scim_deactlog@example.com")

    # Create and deactivate user
    create_resp = await client.post(
        "/scim/v2/Users",
        json={"userName": "deactlog@corp.com", "displayName": "Deact Log"},
        headers=scim_headers(scim_tok),
    )
    user_id = create_resp.json()["id"]

    await client.patch(
        f"/scim/v2/Users/{user_id}",
        json={
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [{"op": "replace", "path": "active", "value": False}],
        },
        headers=scim_headers(scim_tok),
    )

    resp = await client.get(
        f"/workspaces/{ws_id}/scim/logs",
        headers=auth_headers(jwt_token),
    )
    logs = resp.json()
    operations = [l["operation"] for l in logs]
    assert "deactivate_user" in operations


@pytest.mark.asyncio
async def test_scim_group_operations_logged(client: AsyncClient):
    jwt_token, ws_id, scim_tok = await setup_scim(client, "scim_grplog@example.com")

    # Create group
    create_resp = await client.post(
        "/scim/v2/Groups",
        json={"displayName": "LogGroup"},
        headers=scim_headers(scim_tok),
    )
    group_id = create_resp.json()["id"]

    # Delete group
    await client.delete(
        f"/scim/v2/Groups/{group_id}",
        headers=scim_headers(scim_tok),
    )

    resp = await client.get(
        f"/workspaces/{ws_id}/scim/logs",
        headers=auth_headers(jwt_token),
    )
    logs = resp.json()
    operations = [l["operation"] for l in logs]
    assert "create_group" in operations
    assert "delete_group" in operations


# ---------------------------------------------------------------------------
# 7. SCIM response format validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scim_user_resource_format(client: AsyncClient):
    _, _, scim_tok = await setup_scim(client, "scim_fmt@example.com")
    create_resp = await client.post(
        "/scim/v2/Users",
        json={"userName": "fmtuser@corp.com", "displayName": "Format User"},
        headers=scim_headers(scim_tok),
    )
    assert create_resp.status_code == 201
    data = create_resp.json()
    assert data["schemas"] == ["urn:ietf:params:scim:schemas:core:2.0:User"]
    assert "meta" in data
    assert data["meta"]["resourceType"] == "User"
    assert "/scim/v2/Users/" in data["meta"]["location"]


@pytest.mark.asyncio
async def test_scim_group_resource_format(client: AsyncClient):
    _, _, scim_tok = await setup_scim(client, "scim_gfmt@example.com")
    create_resp = await client.post(
        "/scim/v2/Groups",
        json={"displayName": "FmtGroup"},
        headers=scim_headers(scim_tok),
    )
    assert create_resp.status_code == 201
    data = create_resp.json()
    assert data["schemas"] == ["urn:ietf:params:scim:schemas:core:2.0:Group"]
    assert "meta" in data
    assert data["meta"]["resourceType"] == "Group"
    assert "/scim/v2/Groups/" in data["meta"]["location"]
