import uuid

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


async def create_comment(
    client: AsyncClient,
    token: str,
    model_id: str,
    target_type: str = "module",
    target_id: str = "mod-123",
    content: str = "This is a test comment",
    parent_id: str = None,
) -> dict:
    payload = {
        "model_id": model_id,
        "target_type": target_type,
        "target_id": target_id,
        "content": content,
    }
    if parent_id is not None:
        payload["parent_id"] = parent_id
    resp = await client.post(
        f"/models/{model_id}/comments",
        json=payload,
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Create comment tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_comment_on_module(client: AsyncClient):
    token = await register_and_login(client, "c_module@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await client.post(
        f"/models/{model_id}/comments",
        json={
            "model_id": model_id,
            "target_type": "module",
            "target_id": "mod-abc",
            "content": "Great module structure!",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["target_type"] == "module"
    assert data["target_id"] == "mod-abc"
    assert data["content"] == "Great module structure!"
    assert data["is_resolved"] is False
    assert data["parent_id"] is None
    assert "id" in data
    assert "created_at" in data
    assert "author_id" in data


@pytest.mark.asyncio
async def test_create_comment_on_line_item(client: AsyncClient):
    token = await register_and_login(client, "c_line_item@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await client.post(
        f"/models/{model_id}/comments",
        json={
            "model_id": model_id,
            "target_type": "line_item",
            "target_id": "li-xyz",
            "content": "Why is this formula wrong?",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["target_type"] == "line_item"
    assert data["target_id"] == "li-xyz"


@pytest.mark.asyncio
async def test_create_comment_on_cell(client: AsyncClient):
    token = await register_and_login(client, "c_cell@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await client.post(
        f"/models/{model_id}/comments",
        json={
            "model_id": model_id,
            "target_type": "cell",
            "target_id": "cell-row1-col2",
            "content": "Check this value.",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["target_type"] == "cell"
    assert data["target_id"] == "cell-row1-col2"


@pytest.mark.asyncio
async def test_create_comment_requires_auth(client: AsyncClient):
    fake_model_id = str(uuid.uuid4())
    resp = await client.post(
        f"/models/{fake_model_id}/comments",
        json={
            "model_id": fake_model_id,
            "target_type": "module",
            "target_id": "mod-1",
            "content": "No auth",
        },
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# List comments tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_comments_empty(client: AsyncClient):
    token = await register_and_login(client, "c_list_empty@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await client.get(
        f"/models/{model_id}/comments",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_comments_returns_created(client: AsyncClient):
    token = await register_and_login(client, "c_list_created@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    await create_comment(client, token, model_id, content="First comment")
    await create_comment(client, token, model_id, content="Second comment")

    resp = await client.get(
        f"/models/{model_id}/comments",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    contents = [c["content"] for c in resp.json()]
    assert "First comment" in contents
    assert "Second comment" in contents


@pytest.mark.asyncio
async def test_list_comments_filter_by_target_type(client: AsyncClient):
    token = await register_and_login(client, "c_filter_type@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    await create_comment(client, token, model_id, target_type="module", target_id="m1", content="Module comment")
    await create_comment(client, token, model_id, target_type="cell", target_id="c1", content="Cell comment")

    resp = await client.get(
        f"/models/{model_id}/comments?target_type=module",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["target_type"] == "module"


@pytest.mark.asyncio
async def test_list_comments_filter_by_target_id(client: AsyncClient):
    token = await register_and_login(client, "c_filter_id@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    await create_comment(client, token, model_id, target_id="target-A", content="Comment A")
    await create_comment(client, token, model_id, target_id="target-B", content="Comment B")

    resp = await client.get(
        f"/models/{model_id}/comments?target_id=target-A",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["target_id"] == "target-A"


@pytest.mark.asyncio
async def test_list_comments_requires_auth(client: AsyncClient):
    fake_model_id = str(uuid.uuid4())
    resp = await client.get(f"/models/{fake_model_id}/comments")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Thread / reply tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_reply_comment(client: AsyncClient):
    token = await register_and_login(client, "c_reply@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    parent = await create_comment(client, token, model_id, content="Parent comment")
    parent_id = parent["id"]

    resp = await client.post(
        f"/models/{model_id}/comments",
        json={
            "model_id": model_id,
            "target_type": "module",
            "target_id": "mod-1",
            "content": "This is a reply",
            "parent_id": parent_id,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["parent_id"] == parent_id
    assert data["content"] == "This is a reply"


@pytest.mark.asyncio
async def test_get_comment_thread(client: AsyncClient):
    token = await register_and_login(client, "c_thread@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    parent = await create_comment(client, token, model_id, content="Parent")
    parent_id = parent["id"]

    # Create two replies
    await create_comment(client, token, model_id, content="Reply 1", parent_id=parent_id)
    await create_comment(client, token, model_id, content="Reply 2", parent_id=parent_id)

    resp = await client.get(
        f"/comments/{parent_id}/thread",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    contents = [c["content"] for c in data]
    assert "Reply 1" in contents
    assert "Reply 2" in contents


@pytest.mark.asyncio
async def test_get_thread_empty(client: AsyncClient):
    token = await register_and_login(client, "c_thread_empty@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    parent = await create_comment(client, token, model_id, content="Lonely comment")
    parent_id = parent["id"]

    resp = await client.get(
        f"/comments/{parent_id}/thread",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_thread_nonexistent(client: AsyncClient):
    token = await register_and_login(client, "c_thread_nf@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.get(
        f"/comments/{fake_id}/thread",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Resolve / unresolve tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_comment(client: AsyncClient):
    token = await register_and_login(client, "c_resolve@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    comment = await create_comment(client, token, model_id, content="To resolve")
    comment_id = comment["id"]

    assert comment["is_resolved"] is False

    resp = await client.post(
        f"/comments/{comment_id}/resolve",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_resolved"] is True
    assert data["resolved_by"] is not None
    assert data["resolved_at"] is not None


@pytest.mark.asyncio
async def test_unresolve_comment(client: AsyncClient):
    token = await register_and_login(client, "c_unresolve@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    comment = await create_comment(client, token, model_id, content="Will unresolve")
    comment_id = comment["id"]

    # Resolve first
    await client.post(f"/comments/{comment_id}/resolve", headers=auth_headers(token))

    # Then unresolve
    resp = await client.post(
        f"/comments/{comment_id}/unresolve",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_resolved"] is False
    assert data["resolved_by"] is None
    assert data["resolved_at"] is None


@pytest.mark.asyncio
async def test_resolve_nonexistent_comment(client: AsyncClient):
    token = await register_and_login(client, "c_resolve_nf@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.post(
        f"/comments/{fake_id}/resolve",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Delete comment tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_comment_by_author(client: AsyncClient):
    token = await register_and_login(client, "c_delete_author@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    comment = await create_comment(client, token, model_id, content="Delete me")
    comment_id = comment["id"]

    resp = await client.delete(
        f"/comments/{comment_id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 204

    # Verify gone from list
    list_resp = await client.get(
        f"/models/{model_id}/comments",
        headers=auth_headers(token),
    )
    ids = [c["id"] for c in list_resp.json()]
    assert comment_id not in ids


@pytest.mark.asyncio
async def test_delete_comment_forbidden_for_non_author(client: AsyncClient):
    author_token = await register_and_login(client, "c_del_author@example.com")
    other_token = await register_and_login(client, "c_del_other@example.com")

    ws_id = await create_workspace(client, author_token)
    model_id = await create_model(client, author_token, ws_id)

    comment = await create_comment(client, author_token, model_id, content="Author's comment")
    comment_id = comment["id"]

    # Other user tries to delete
    resp = await client.delete(
        f"/comments/{comment_id}",
        headers=auth_headers(other_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_nonexistent_comment(client: AsyncClient):
    token = await register_and_login(client, "c_del_nf@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.delete(
        f"/comments/{fake_id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_comment_requires_auth(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    resp = await client.delete(f"/comments/{fake_id}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# @mention extraction and retrieval tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mention_extraction_creates_mention_record(client: AsyncClient):
    author_token = await register_and_login(client, "c_mention_author@example.com")
    mentioned_token = await register_and_login(client, "mentioned@example.com")  # noqa: F841

    ws_id = await create_workspace(client, author_token)
    model_id = await create_model(client, author_token, ws_id)

    comment = await create_comment(
        client,
        author_token,
        model_id,
        content="Hey @mentioned@example.com, check this out!",
    )
    assert len(comment["mention_user_ids"]) == 1


@pytest.mark.asyncio
async def test_mention_nonexistent_user_ignored(client: AsyncClient):
    token = await register_and_login(client, "c_mention_ghost@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    comment = await create_comment(
        client,
        token,
        model_id,
        content="Hey @nobody@ghost.invalid, are you there?",
    )
    # Ghost user doesn't exist so no mention should be stored
    assert comment["mention_user_ids"] == []


@pytest.mark.asyncio
async def test_get_mentions_for_current_user(client: AsyncClient):
    author_token = await register_and_login(client, "c_mget_author@example.com")
    user_token = await register_and_login(client, "c_mget_user@example.com")

    ws_id = await create_workspace(client, author_token)
    model_id = await create_model(client, author_token, ws_id)

    # Author mentions the user
    await create_comment(
        client,
        author_token,
        model_id,
        content="FYI @c_mget_user@example.com",
    )

    # User checks their mentions
    resp = await client.get(
        "/me/mentions",
        headers=auth_headers(user_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    contents = [c["content"] for c in data]
    assert any("c_mget_user@example.com" in c for c in contents)


@pytest.mark.asyncio
async def test_get_mentions_empty_for_unmentioned_user(client: AsyncClient):
    token = await register_and_login(client, "c_no_mention@example.com")

    resp = await client.get(
        "/me/mentions",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_mentions_requires_auth(client: AsyncClient):
    resp = await client.get("/me/mentions")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Author info in response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_comment_response_includes_author_info(client: AsyncClient):
    token = await register_and_login(client, "c_author_info@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    comment = await create_comment(client, token, model_id, content="Test author info")

    assert comment["author_email"] == "c_author_info@example.com"
    assert comment["author_name"] is not None


# ---------------------------------------------------------------------------
# Multiple mentions in one comment
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multiple_mentions_in_one_comment(client: AsyncClient):
    author_token = await register_and_login(client, "c_multi_author@example.com")
    await register_and_login(client, "user_one@example.com")
    await register_and_login(client, "user_two@example.com")

    ws_id = await create_workspace(client, author_token)
    model_id = await create_model(client, author_token, ws_id)

    comment = await create_comment(
        client,
        author_token,
        model_id,
        content="Hey @user_one@example.com and @user_two@example.com, look here!",
    )
    assert len(comment["mention_user_ids"]) == 2
