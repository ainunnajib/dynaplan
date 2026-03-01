"""
Tests for F028: Role-based access control.
"""
import uuid
from typing import Optional

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def register_and_login(
    client: AsyncClient,
    email: str,
    password: str = "testpass123",
    full_name: str = "Test User",
) -> str:
    await client.post("/auth/register", json={
        "email": email,
        "full_name": full_name,
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


async def create_model(
    client: AsyncClient,
    token: str,
    workspace_id: str,
    name: str = "Test Model",
) -> str:
    resp = await client.post(
        "/models",
        json={"name": name, "workspace_id": workspace_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Workspace Members — Add
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_workspace_member(client: AsyncClient):
    """Owner can add a member to their workspace."""
    owner_token = await register_and_login(client, "rbac_owner1@example.com")
    member_token = await register_and_login(client, "rbac_member1@example.com")

    ws_id = await create_workspace(client, owner_token)

    resp = await client.post(
        f"/workspaces/{ws_id}/members",
        json={"user_email": "rbac_member1@example.com", "role": "editor"},
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "rbac_member1@example.com"
    assert data["role"] == "editor"
    assert "user_id" in data
    assert "full_name" in data


@pytest.mark.asyncio
async def test_add_workspace_member_requires_auth(client: AsyncClient):
    """Adding a member requires authentication."""
    fake_ws_id = str(uuid.uuid4())
    resp = await client.post(
        f"/workspaces/{fake_ws_id}/members",
        json={"user_email": "someone@example.com", "role": "viewer"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_add_workspace_member_nonexistent_workspace(client: AsyncClient):
    """Adding a member to a nonexistent workspace returns 404."""
    token = await register_and_login(client, "rbac_ws404@example.com")
    fake_ws_id = str(uuid.uuid4())

    resp = await client.post(
        f"/workspaces/{fake_ws_id}/members",
        json={"user_email": "rbac_ws404@example.com", "role": "viewer"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_add_workspace_member_nonexistent_user(client: AsyncClient):
    """Adding a nonexistent user returns 404."""
    token = await register_and_login(client, "rbac_addnx@example.com")
    ws_id = await create_workspace(client, token)

    resp = await client.post(
        f"/workspaces/{ws_id}/members",
        json={"user_email": "doesnotexist@example.com", "role": "viewer"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_add_workspace_member_unauthorized(client: AsyncClient):
    """Non-admin cannot add members."""
    owner_token = await register_and_login(client, "rbac_owner_deny@example.com")
    viewer_token = await register_and_login(client, "rbac_viewer_deny@example.com")
    other_token = await register_and_login(client, "rbac_other_deny@example.com")

    ws_id = await create_workspace(client, owner_token)
    # Add viewer_deny as a viewer
    await client.post(
        f"/workspaces/{ws_id}/members",
        json={"user_email": "rbac_viewer_deny@example.com", "role": "viewer"},
        headers=auth_headers(owner_token),
    )

    # Viewer tries to add another member — should be forbidden
    resp = await client.post(
        f"/workspaces/{ws_id}/members",
        json={"user_email": "rbac_other_deny@example.com", "role": "viewer"},
        headers=auth_headers(viewer_token),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Workspace Members — List
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_workspace_members(client: AsyncClient):
    """Owner can list all workspace members."""
    owner_token = await register_and_login(client, "rbac_list_owner@example.com")
    mem1_token = await register_and_login(client, "rbac_list_m1@example.com")
    mem2_token = await register_and_login(client, "rbac_list_m2@example.com")

    ws_id = await create_workspace(client, owner_token)
    await client.post(
        f"/workspaces/{ws_id}/members",
        json={"user_email": "rbac_list_m1@example.com", "role": "editor"},
        headers=auth_headers(owner_token),
    )
    await client.post(
        f"/workspaces/{ws_id}/members",
        json={"user_email": "rbac_list_m2@example.com", "role": "viewer"},
        headers=auth_headers(owner_token),
    )

    resp = await client.get(
        f"/workspaces/{ws_id}/members",
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 200
    emails = [m["email"] for m in resp.json()]
    assert "rbac_list_m1@example.com" in emails
    assert "rbac_list_m2@example.com" in emails


@pytest.mark.asyncio
async def test_list_workspace_members_nonexistent_workspace(client: AsyncClient):
    """Listing members for a nonexistent workspace returns 404."""
    token = await register_and_login(client, "rbac_listws404@example.com")
    fake_ws_id = str(uuid.uuid4())

    resp = await client.get(
        f"/workspaces/{fake_ws_id}/members",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Workspace Members — Update role
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_workspace_member_role(client: AsyncClient):
    """Owner can change a member's role."""
    owner_token = await register_and_login(client, "rbac_upd_owner@example.com")
    mem_token = await register_and_login(client, "rbac_upd_mem@example.com")

    ws_id = await create_workspace(client, owner_token)
    add_resp = await client.post(
        f"/workspaces/{ws_id}/members",
        json={"user_email": "rbac_upd_mem@example.com", "role": "viewer"},
        headers=auth_headers(owner_token),
    )
    user_id = add_resp.json()["user_id"]

    resp = await client.patch(
        f"/workspaces/{ws_id}/members/{user_id}",
        json={"role": "editor"},
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "editor"


@pytest.mark.asyncio
async def test_update_workspace_member_role_duplicate_add(client: AsyncClient):
    """Adding the same member twice updates their role."""
    owner_token = await register_and_login(client, "rbac_dup_owner@example.com")
    mem_token = await register_and_login(client, "rbac_dup_mem@example.com")

    ws_id = await create_workspace(client, owner_token)
    await client.post(
        f"/workspaces/{ws_id}/members",
        json={"user_email": "rbac_dup_mem@example.com", "role": "viewer"},
        headers=auth_headers(owner_token),
    )
    # Add same user again with a different role
    resp = await client.post(
        f"/workspaces/{ws_id}/members",
        json={"user_email": "rbac_dup_mem@example.com", "role": "admin"},
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "admin"


# ---------------------------------------------------------------------------
# Workspace Members — Remove
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_remove_workspace_member(client: AsyncClient):
    """Owner can remove a member."""
    owner_token = await register_and_login(client, "rbac_rem_owner@example.com")
    mem_token = await register_and_login(client, "rbac_rem_mem@example.com")

    ws_id = await create_workspace(client, owner_token)
    add_resp = await client.post(
        f"/workspaces/{ws_id}/members",
        json={"user_email": "rbac_rem_mem@example.com", "role": "viewer"},
        headers=auth_headers(owner_token),
    )
    user_id = add_resp.json()["user_id"]

    resp = await client.delete(
        f"/workspaces/{ws_id}/members/{user_id}",
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 204

    # Should no longer appear in member list
    list_resp = await client.get(
        f"/workspaces/{ws_id}/members",
        headers=auth_headers(owner_token),
    )
    emails = [m["email"] for m in list_resp.json()]
    assert "rbac_rem_mem@example.com" not in emails


@pytest.mark.asyncio
async def test_cannot_remove_workspace_owner(client: AsyncClient):
    """The workspace owner cannot be removed from their workspace."""
    owner_token = await register_and_login(client, "rbac_noremove_owner@example.com")
    # Get owner's user_id from /auth/me
    me_resp = await client.get("/auth/me", headers=auth_headers(owner_token))
    owner_user_id = me_resp.json()["id"]

    ws_id = await create_workspace(client, owner_token)

    resp = await client.delete(
        f"/workspaces/{ws_id}/members/{owner_user_id}",
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_remove_nonexistent_member(client: AsyncClient):
    """Removing a nonexistent member returns 404."""
    owner_token = await register_and_login(client, "rbac_remnx_owner@example.com")
    ws_id = await create_workspace(client, owner_token)
    fake_user_id = str(uuid.uuid4())

    resp = await client.delete(
        f"/workspaces/{ws_id}/members/{fake_user_id}",
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Workspace Role Hierarchy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_can_add_members(client: AsyncClient):
    """A workspace admin can add new members."""
    owner_token = await register_and_login(client, "rbac_hierarch_owner@example.com")
    admin_token = await register_and_login(client, "rbac_hierarch_admin@example.com")
    new_mem_token = await register_and_login(client, "rbac_hierarch_new@example.com")

    ws_id = await create_workspace(client, owner_token)
    # Owner grants admin role to admin_token user
    await client.post(
        f"/workspaces/{ws_id}/members",
        json={"user_email": "rbac_hierarch_admin@example.com", "role": "admin"},
        headers=auth_headers(owner_token),
    )

    # Admin adds a new member
    resp = await client.post(
        f"/workspaces/{ws_id}/members",
        json={"user_email": "rbac_hierarch_new@example.com", "role": "viewer"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Model Access — Set
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_model_access(client: AsyncClient):
    """Model owner can set access for another user."""
    owner_token = await register_and_login(client, "rbac_maccess_owner@example.com")
    user_token = await register_and_login(client, "rbac_maccess_user@example.com")

    ws_id = await create_workspace(client, owner_token)
    model_id = await create_model(client, owner_token, ws_id)

    resp = await client.post(
        f"/models/{model_id}/access",
        json={"user_email": "rbac_maccess_user@example.com", "permission": "view_only"},
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "rbac_maccess_user@example.com"
    assert data["permission"] == "view_only"


@pytest.mark.asyncio
async def test_set_model_access_requires_auth(client: AsyncClient):
    """Setting model access requires authentication."""
    fake_model_id = str(uuid.uuid4())
    resp = await client.post(
        f"/models/{fake_model_id}/access",
        json={"user_email": "someone@example.com", "permission": "view_only"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_set_model_access_nonexistent_model(client: AsyncClient):
    """Setting access on a nonexistent model returns 404."""
    token = await register_and_login(client, "rbac_model404@example.com")
    fake_model_id = str(uuid.uuid4())

    resp = await client.post(
        f"/models/{fake_model_id}/access",
        json={"user_email": "rbac_model404@example.com", "permission": "view_only"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_set_model_access_nonexistent_user(client: AsyncClient):
    """Setting access for nonexistent user returns 404."""
    token = await register_and_login(client, "rbac_mnxuser@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await client.post(
        f"/models/{model_id}/access",
        json={"user_email": "doesnotexist999@example.com", "permission": "view_only"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Model Access — List
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_model_access(client: AsyncClient):
    """Owner can list all model access rules."""
    owner_token = await register_and_login(client, "rbac_mlist_owner@example.com")
    user1_token = await register_and_login(client, "rbac_mlist_u1@example.com")
    user2_token = await register_and_login(client, "rbac_mlist_u2@example.com")

    ws_id = await create_workspace(client, owner_token)
    model_id = await create_model(client, owner_token, ws_id)

    await client.post(
        f"/models/{model_id}/access",
        json={"user_email": "rbac_mlist_u1@example.com", "permission": "view_only"},
        headers=auth_headers(owner_token),
    )
    await client.post(
        f"/models/{model_id}/access",
        json={"user_email": "rbac_mlist_u2@example.com", "permission": "edit_data"},
        headers=auth_headers(owner_token),
    )

    resp = await client.get(
        f"/models/{model_id}/access",
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 200
    emails = [a["email"] for a in resp.json()]
    assert "rbac_mlist_u1@example.com" in emails
    assert "rbac_mlist_u2@example.com" in emails


# ---------------------------------------------------------------------------
# Model Access — Remove
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_remove_model_access(client: AsyncClient):
    """Owner can remove model access for a user."""
    owner_token = await register_and_login(client, "rbac_mrem_owner@example.com")
    user_token = await register_and_login(client, "rbac_mrem_user@example.com")

    ws_id = await create_workspace(client, owner_token)
    model_id = await create_model(client, owner_token, ws_id)

    add_resp = await client.post(
        f"/models/{model_id}/access",
        json={"user_email": "rbac_mrem_user@example.com", "permission": "view_only"},
        headers=auth_headers(owner_token),
    )
    user_id = add_resp.json()["user_id"]

    resp = await client.delete(
        f"/models/{model_id}/access/{user_id}",
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 204

    # Verify it's removed
    list_resp = await client.get(
        f"/models/{model_id}/access",
        headers=auth_headers(owner_token),
    )
    emails = [a["email"] for a in list_resp.json()]
    assert "rbac_mrem_user@example.com" not in emails


@pytest.mark.asyncio
async def test_remove_model_access_not_found(client: AsyncClient):
    """Removing nonexistent access returns 404."""
    token = await register_and_login(client, "rbac_mrem404_owner@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    fake_user_id = str(uuid.uuid4())

    resp = await client.delete(
        f"/models/{model_id}/access/{fake_user_id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Model Permission Logic
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_model_access_changes_permission(client: AsyncClient):
    """Setting access for the same user twice updates their permission."""
    owner_token = await register_and_login(client, "rbac_mperm_owner@example.com")
    user_token = await register_and_login(client, "rbac_mperm_user@example.com")

    ws_id = await create_workspace(client, owner_token)
    model_id = await create_model(client, owner_token, ws_id)

    await client.post(
        f"/models/{model_id}/access",
        json={"user_email": "rbac_mperm_user@example.com", "permission": "view_only"},
        headers=auth_headers(owner_token),
    )
    # Update to higher permission
    resp = await client.post(
        f"/models/{model_id}/access",
        json={"user_email": "rbac_mperm_user@example.com", "permission": "full_access"},
        headers=auth_headers(owner_token),
    )
    assert resp.status_code == 201
    assert resp.json()["permission"] == "full_access"


# ---------------------------------------------------------------------------
# Dimension Member Access
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_dimension_access(client: AsyncClient):
    """Owner can set dimension member access."""
    token = await register_and_login(client, "rbac_dimset@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dimension_id = str(uuid.uuid4())
    member_ids = [str(uuid.uuid4()), str(uuid.uuid4())]

    resp = await client.post(
        f"/models/{model_id}/dimension-access",
        json={"dimension_id": dimension_id, "allowed_member_ids": member_ids},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["dimension_id"] == dimension_id
    assert set(data["allowed_member_ids"]) == set(member_ids)


@pytest.mark.asyncio
async def test_get_dimension_access(client: AsyncClient):
    """Owner can retrieve dimension access for a user."""
    token = await register_and_login(client, "rbac_dimget@example.com")
    me_resp = await client.get("/auth/me", headers=auth_headers(token))
    user_id = me_resp.json()["id"]

    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dimension_id = str(uuid.uuid4())
    member_ids = [str(uuid.uuid4())]

    await client.post(
        f"/models/{model_id}/dimension-access",
        json={"dimension_id": dimension_id, "allowed_member_ids": member_ids},
        headers=auth_headers(token),
    )

    resp = await client.get(
        f"/models/{model_id}/dimension-access/{user_id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 1
    dim_ids = [d["dimension_id"] for d in resp.json()]
    assert dimension_id in dim_ids


@pytest.mark.asyncio
async def test_set_dimension_access_nonexistent_model(client: AsyncClient):
    """Setting dimension access on nonexistent model returns 404."""
    token = await register_and_login(client, "rbac_dim404@example.com")
    fake_model_id = str(uuid.uuid4())

    resp = await client.post(
        f"/models/{fake_model_id}/dimension-access",
        json={"dimension_id": str(uuid.uuid4()), "allowed_member_ids": []},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Current user permissions endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_my_permissions_no_params(client: AsyncClient):
    """Without query params, returns null permissions."""
    token = await register_and_login(client, "rbac_myperm@example.com")

    resp = await client.get("/me/permissions", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["workspace_role"] is None
    assert data["model_permission"] is None


@pytest.mark.asyncio
async def test_my_permissions_workspace(client: AsyncClient):
    """Returns owner role for the workspace owner."""
    token = await register_and_login(client, "rbac_myperm_ws@example.com")
    ws_id = await create_workspace(client, token)

    resp = await client.get(
        "/me/permissions",
        params={"workspace_id": ws_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["workspace_role"] == "owner"


@pytest.mark.asyncio
async def test_my_permissions_model(client: AsyncClient):
    """Returns the correct model permission for the user."""
    owner_token = await register_and_login(client, "rbac_myperm_model_owner@example.com")
    user_token = await register_and_login(client, "rbac_myperm_model_user@example.com")

    ws_id = await create_workspace(client, owner_token)
    model_id = await create_model(client, owner_token, ws_id)

    await client.post(
        f"/models/{model_id}/access",
        json={"user_email": "rbac_myperm_model_user@example.com", "permission": "edit_data"},
        headers=auth_headers(owner_token),
    )

    resp = await client.get(
        "/me/permissions",
        params={"model_id": model_id},
        headers=auth_headers(user_token),
    )
    assert resp.status_code == 200
    assert resp.json()["model_permission"] == "edit_data"


@pytest.mark.asyncio
async def test_my_permissions_requires_auth(client: AsyncClient):
    """The permissions endpoint requires authentication."""
    resp = await client.get("/me/permissions")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_my_permissions_workspace_not_found(client: AsyncClient):
    """Providing a nonexistent workspace_id returns 404."""
    token = await register_and_login(client, "rbac_myperm_404ws@example.com")
    fake_ws_id = str(uuid.uuid4())

    resp = await client.get(
        "/me/permissions",
        params={"workspace_id": fake_ws_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_member_can_see_workspace_role(client: AsyncClient):
    """A member can see their own workspace role via /me/permissions."""
    owner_token = await register_and_login(client, "rbac_mem_role_owner@example.com")
    mem_token = await register_and_login(client, "rbac_mem_role_mem@example.com")

    ws_id = await create_workspace(client, owner_token)
    await client.post(
        f"/workspaces/{ws_id}/members",
        json={"user_email": "rbac_mem_role_mem@example.com", "role": "editor"},
        headers=auth_headers(owner_token),
    )

    resp = await client.get(
        "/me/permissions",
        params={"workspace_id": ws_id},
        headers=auth_headers(mem_token),
    )
    assert resp.status_code == 200
    assert resp.json()["workspace_role"] == "editor"
