"""
Tests for F017: Dashboard publishing & sharing.

Covers:
- Publish / unpublish
- Share / unshare by email
- List shared-with-me
- Access checks (owner, shared, published, denied)
- Context filters (save and retrieve)
- Auth guard on every endpoint
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
    await client.post(
        "/auth/register",
        json={"email": email, "full_name": "Test User", "password": password},
    )
    resp = await client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def create_workspace(client: AsyncClient, token: str, name: str = "WS") -> str:
    resp = await client.post(
        "/workspaces/",
        json={"name": name},
        headers=auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def create_model(
    client: AsyncClient, token: str, workspace_id: str, name: str = "Model"
) -> str:
    resp = await client.post(
        "/models",
        json={"name": name, "workspace_id": workspace_id},
        headers=auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def create_dashboard(
    client: AsyncClient, token: str, model_id: str, name: str = "Dash"
) -> str:
    resp = await client.post(
        f"/models/{model_id}/dashboards",
        json={"name": name},
        headers=auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Test: publish / unpublish
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_dashboard(client: AsyncClient):
    token = await register_and_login(client, "pub_pub@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dash_id = await create_dashboard(client, token, model_id)

    resp = await client.post(f"/dashboards/{dash_id}/publish", headers=auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_published"] is True
    assert data["id"] == dash_id


@pytest.mark.asyncio
async def test_unpublish_dashboard(client: AsyncClient):
    token = await register_and_login(client, "pub_unpub@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dash_id = await create_dashboard(client, token, model_id)

    # Publish first
    await client.post(f"/dashboards/{dash_id}/publish", headers=auth(token))

    resp = await client.post(f"/dashboards/{dash_id}/unpublish", headers=auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_published"] is False


@pytest.mark.asyncio
async def test_publish_requires_auth(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    resp = await client.post(f"/dashboards/{fake_id}/publish")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_publish_requires_ownership(client: AsyncClient):
    token_a = await register_and_login(client, "pub_own_a@example.com")
    token_b = await register_and_login(client, "pub_own_b@example.com")

    ws_id = await create_workspace(client, token_a)
    model_id = await create_model(client, token_a, ws_id)
    dash_id = await create_dashboard(client, token_a, model_id)

    # User B cannot publish A's dashboard
    resp = await client.post(f"/dashboards/{dash_id}/publish", headers=auth(token_b))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_publish_nonexistent_dashboard(client: AsyncClient):
    token = await register_and_login(client, "pub_noexist@example.com")
    fake_id = str(uuid.uuid4())
    resp = await client.post(f"/dashboards/{fake_id}/publish", headers=auth(token))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test: share / unshare
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_share_dashboard(client: AsyncClient):
    token_a = await register_and_login(client, "share_a@example.com")
    await register_and_login(client, "share_b@example.com")  # registers user B

    ws_id = await create_workspace(client, token_a)
    model_id = await create_model(client, token_a, ws_id)
    dash_id = await create_dashboard(client, token_a, model_id)

    resp = await client.post(
        f"/dashboards/{dash_id}/share",
        json={"user_email": "share_b@example.com", "permission": "view"},
        headers=auth(token_a),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["permission"] == "view"
    assert data["dashboard_id"] == dash_id


@pytest.mark.asyncio
async def test_share_dashboard_edit_permission(client: AsyncClient):
    token_a = await register_and_login(client, "share_edit_a@example.com")
    await register_and_login(client, "share_edit_b@example.com")

    ws_id = await create_workspace(client, token_a)
    model_id = await create_model(client, token_a, ws_id)
    dash_id = await create_dashboard(client, token_a, model_id)

    resp = await client.post(
        f"/dashboards/{dash_id}/share",
        json={"user_email": "share_edit_b@example.com", "permission": "edit"},
        headers=auth(token_a),
    )
    assert resp.status_code == 201
    assert resp.json()["permission"] == "edit"


@pytest.mark.asyncio
async def test_share_nonexistent_user(client: AsyncClient):
    token = await register_and_login(client, "share_nouser@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dash_id = await create_dashboard(client, token, model_id)

    resp = await client.post(
        f"/dashboards/{dash_id}/share",
        json={"user_email": "nobody@example.com", "permission": "view"},
        headers=auth(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_share_with_self_rejected(client: AsyncClient):
    token = await register_and_login(client, "share_self@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dash_id = await create_dashboard(client, token, model_id)

    resp = await client.post(
        f"/dashboards/{dash_id}/share",
        json={"user_email": "share_self@example.com", "permission": "view"},
        headers=auth(token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_unshare_dashboard(client: AsyncClient):
    token_a = await register_and_login(client, "unshare_a@example.com")
    token_b = await register_and_login(client, "unshare_b@example.com")

    ws_id = await create_workspace(client, token_a)
    model_id = await create_model(client, token_a, ws_id)
    dash_id = await create_dashboard(client, token_a, model_id)

    # Share first
    share_resp = await client.post(
        f"/dashboards/{dash_id}/share",
        json={"user_email": "unshare_b@example.com", "permission": "view"},
        headers=auth(token_a),
    )
    assert share_resp.status_code == 201
    shared_user_id = share_resp.json()["shared_with_user_id"]

    # Verify B can see it in shared-with-me
    me_resp = await client.get("/dashboards/shared-with-me", headers=auth(token_b))
    assert me_resp.status_code == 200
    assert any(d["id"] == dash_id for d in me_resp.json())

    # Now unshare
    del_resp = await client.delete(
        f"/dashboards/{dash_id}/share/{shared_user_id}",
        headers=auth(token_a),
    )
    assert del_resp.status_code == 204

    # Verify it's gone
    me_resp2 = await client.get("/dashboards/shared-with-me", headers=auth(token_b))
    assert me_resp2.status_code == 200
    assert not any(d["id"] == dash_id for d in me_resp2.json())


@pytest.mark.asyncio
async def test_unshare_nonexistent(client: AsyncClient):
    token = await register_and_login(client, "unshare_noexist@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dash_id = await create_dashboard(client, token, model_id)

    fake_user_id = str(uuid.uuid4())
    resp = await client.delete(
        f"/dashboards/{dash_id}/share/{fake_user_id}", headers=auth(token)
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test: shared-with-me list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shared_with_me_empty(client: AsyncClient):
    token = await register_and_login(client, "shared_me_empty@example.com")
    resp = await client.get("/dashboards/shared-with-me", headers=auth(token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_shared_with_me_requires_auth(client: AsyncClient):
    resp = await client.get("/dashboards/shared-with-me")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Test: context filters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_and_get_context_filters(client: AsyncClient):
    token = await register_and_login(client, "ctx_filter@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dash_id = await create_dashboard(client, token, model_id)

    dim_id = str(uuid.uuid4())
    member_id_1 = str(uuid.uuid4())
    member_id_2 = str(uuid.uuid4())

    save_resp = await client.post(
        f"/dashboards/{dash_id}/context-filters",
        json={
            "filters": [
                {
                    "dimension_id": dim_id,
                    "selected_member_ids": [member_id_1, member_id_2],
                    "label": "Region",
                }
            ]
        },
        headers=auth(token),
    )
    assert save_resp.status_code == 200
    saved = save_resp.json()
    assert len(saved) == 1
    assert saved[0]["label"] == "Region"
    assert saved[0]["dimension_id"] == dim_id

    get_resp = await client.get(
        f"/dashboards/{dash_id}/context-filters", headers=auth(token)
    )
    assert get_resp.status_code == 200
    filters = get_resp.json()
    assert len(filters) == 1
    assert filters[0]["label"] == "Region"


@pytest.mark.asyncio
async def test_save_context_filters_replaces_existing(client: AsyncClient):
    token = await register_and_login(client, "ctx_replace@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dash_id = await create_dashboard(client, token, model_id)

    dim_id = str(uuid.uuid4())
    new_dim_id = str(uuid.uuid4())

    # Save initial filters
    await client.post(
        f"/dashboards/{dash_id}/context-filters",
        json={"filters": [{"dimension_id": dim_id, "selected_member_ids": [], "label": "Old"}]},
        headers=auth(token),
    )

    # Replace with new filters
    save_resp = await client.post(
        f"/dashboards/{dash_id}/context-filters",
        json={"filters": [{"dimension_id": new_dim_id, "selected_member_ids": [], "label": "New"}]},
        headers=auth(token),
    )
    assert save_resp.status_code == 200

    get_resp = await client.get(
        f"/dashboards/{dash_id}/context-filters", headers=auth(token)
    )
    assert get_resp.status_code == 200
    filters = get_resp.json()
    assert len(filters) == 1
    assert filters[0]["label"] == "New"
    assert filters[0]["dimension_id"] == new_dim_id


@pytest.mark.asyncio
async def test_context_filters_forbidden_for_non_member(client: AsyncClient):
    token_a = await register_and_login(client, "ctx_owner@example.com")
    token_b = await register_and_login(client, "ctx_outsider@example.com")

    ws_id = await create_workspace(client, token_a)
    model_id = await create_model(client, token_a, ws_id)
    dash_id = await create_dashboard(client, token_a, model_id)

    # User B has no access
    resp = await client.get(
        f"/dashboards/{dash_id}/context-filters", headers=auth(token_b)
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_context_filters_accessible_after_share(client: AsyncClient):
    token_a = await register_and_login(client, "ctx_share_a@example.com")
    token_b = await register_and_login(client, "ctx_share_b@example.com")

    ws_id = await create_workspace(client, token_a)
    model_id = await create_model(client, token_a, ws_id)
    dash_id = await create_dashboard(client, token_a, model_id)

    # Share with B
    await client.post(
        f"/dashboards/{dash_id}/share",
        json={"user_email": "ctx_share_b@example.com", "permission": "view"},
        headers=auth(token_a),
    )

    # B can now read context filters
    resp = await client.get(
        f"/dashboards/{dash_id}/context-filters", headers=auth(token_b)
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_context_filters_accessible_when_published(client: AsyncClient):
    token_a = await register_and_login(client, "ctx_pub_a@example.com")
    token_b = await register_and_login(client, "ctx_pub_b@example.com")

    ws_id = await create_workspace(client, token_a)
    model_id = await create_model(client, token_a, ws_id)
    dash_id = await create_dashboard(client, token_a, model_id)

    # Publish dashboard
    await client.post(f"/dashboards/{dash_id}/publish", headers=auth(token_a))

    # Any authenticated user can access context filters of a published dashboard
    resp = await client.get(
        f"/dashboards/{dash_id}/context-filters", headers=auth(token_b)
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_context_filters_requires_auth(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/dashboards/{fake_id}/context-filters")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_save_context_filters_requires_auth(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    resp = await client.post(
        f"/dashboards/{fake_id}/context-filters",
        json={"filters": []},
    )
    assert resp.status_code == 401
