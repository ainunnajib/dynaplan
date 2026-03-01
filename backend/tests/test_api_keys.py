"""
Tests for F019: REST API for data integration — API key management and public API.

Covers:
- Create API key: returns dyp_ prefix, raw key shown once
- List API keys: raw key never shown
- Revoke API key
- Auth required for key management endpoints
- Public API: use API key in X-API-Key header
- Invalid key rejected (401)
- Revoked key rejected (401)
- Missing X-API-Key header → 401
- Scope checking: read vs write
- Admin scope grants all access
- Forbidden when scope missing
- Only owner can revoke their key
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
    assert resp.status_code == 200
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def api_key_headers(raw_key: str) -> dict:
    return {"X-API-Key": raw_key}


async def create_api_key(
    client: AsyncClient,
    token: str,
    name: str = "Test Key",
    scopes: list = None,
) -> dict:
    if scopes is None:
        scopes = ["read:models"]
    resp = await client.post(
        "/api-keys",
        json={"name": name, "scopes": scopes},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def create_workspace(client: AsyncClient, token: str, name: str = "WS") -> str:
    resp = await client.post(
        "/workspaces/",
        json={"name": name},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_model(
    client: AsyncClient, token: str, workspace_id: str, name: str = "Model"
) -> dict:
    resp = await client.post(
        "/models",
        json={"name": name, "workspace_id": workspace_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def create_module(
    client: AsyncClient, token: str, model_id: str, name: str = "Module"
) -> str:
    resp = await client.post(
        f"/models/{model_id}/modules",
        json={"name": name},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_line_item(
    client: AsyncClient, token: str, module_id: str, name: str = "Revenue"
) -> str:
    resp = await client.post(
        f"/modules/{module_id}/line-items",
        json={"name": name, "format": "number"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_dimension(
    client: AsyncClient, token: str, model_id: str, name: str = "Regions"
) -> str:
    resp = await client.post(
        f"/models/{model_id}/dimensions",
        json={"name": name, "dimension_type": "custom"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# API Key Creation Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_api_key_success(client: AsyncClient):
    token = await register_and_login(client, "ak_create@example.com")
    resp = await client.post(
        "/api-keys",
        json={"name": "My Integration Key", "scopes": ["read:models", "read:cells"]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Integration Key"
    assert "read:models" in data["scopes"]
    assert "read:cells" in data["scopes"]
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_api_key_dyp_prefix(client: AsyncClient):
    token = await register_and_login(client, "ak_prefix@example.com")
    data = await create_api_key(client, token, scopes=["read:models"])
    raw_key = data["raw_key"]
    assert raw_key.startswith("dyp_"), f"Expected key to start with 'dyp_', got: {raw_key}"
    # dyp_ + 64 hex chars (32 bytes as hex)
    suffix = raw_key[4:]
    assert len(suffix) == 64, f"Expected 64 hex chars after prefix, got {len(suffix)}"
    assert all(c in "0123456789abcdef" for c in suffix), "Suffix should be hex"


@pytest.mark.asyncio
async def test_create_api_key_raw_key_in_response(client: AsyncClient):
    """raw_key is included in the creation response."""
    token = await register_and_login(client, "ak_rawkey@example.com")
    resp = await client.post(
        "/api-keys",
        json={"name": "Key With Raw", "scopes": ["read:models"]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "raw_key" in data
    assert data["raw_key"] != ""


@pytest.mark.asyncio
async def test_create_api_key_no_hash_in_response(client: AsyncClient):
    """key_hash must never appear in API responses."""
    token = await register_and_login(client, "ak_nohash@example.com")
    resp = await client.post(
        "/api-keys",
        json={"name": "No Hash Key", "scopes": ["read:models"]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "key_hash" not in data


@pytest.mark.asyncio
async def test_create_api_key_all_scopes(client: AsyncClient):
    token = await register_and_login(client, "ak_allscopes@example.com")
    all_scopes = [
        "read:models", "write:models",
        "read:cells", "write:cells",
        "read:dimensions", "write:dimensions",
        "admin",
    ]
    data = await create_api_key(client, token, scopes=all_scopes)
    assert set(data["scopes"]) == set(all_scopes)


@pytest.mark.asyncio
async def test_create_api_key_invalid_scope(client: AsyncClient):
    token = await register_and_login(client, "ak_badscope@example.com")
    resp = await client.post(
        "/api-keys",
        json={"name": "Bad Scope Key", "scopes": ["read:models", "hack:everything"]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_api_key_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/api-keys",
        json={"name": "Unauth Key", "scopes": ["read:models"]},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# API Key List Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_api_keys_empty(client: AsyncClient):
    token = await register_and_login(client, "ak_list_empty@example.com")
    resp = await client.get("/api-keys", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_api_keys_returns_created(client: AsyncClient):
    token = await register_and_login(client, "ak_list_created@example.com")
    await create_api_key(client, token, name="Key One", scopes=["read:models"])
    await create_api_key(client, token, name="Key Two", scopes=["read:cells"])

    resp = await client.get("/api-keys", headers=auth_headers(token))
    assert resp.status_code == 200
    names = [k["name"] for k in resp.json()]
    assert "Key One" in names
    assert "Key Two" in names


@pytest.mark.asyncio
async def test_list_api_keys_no_raw_key(client: AsyncClient):
    """List endpoint must NOT return raw_key."""
    token = await register_and_login(client, "ak_list_noraw@example.com")
    await create_api_key(client, token, name="Listed Key", scopes=["read:models"])

    resp = await client.get("/api-keys", headers=auth_headers(token))
    assert resp.status_code == 200
    for key in resp.json():
        assert "raw_key" not in key
        assert "key_hash" not in key


@pytest.mark.asyncio
async def test_list_api_keys_requires_auth(client: AsyncClient):
    resp = await client.get("/api-keys")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_api_keys_isolated_per_user(client: AsyncClient):
    """User A's keys are not visible to User B."""
    token_a = await register_and_login(client, "ak_iso_a@example.com")
    token_b = await register_and_login(client, "ak_iso_b@example.com")

    await create_api_key(client, token_a, name="User A Key", scopes=["read:models"])

    resp = await client.get("/api-keys", headers=auth_headers(token_b))
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# API Key Revoke Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_revoke_api_key(client: AsyncClient):
    token = await register_and_login(client, "ak_revoke@example.com")
    key_data = await create_api_key(client, token, name="Revokable Key", scopes=["read:models"])
    key_id = key_data["id"]

    resp = await client.delete(f"/api-keys/{key_id}", headers=auth_headers(token))
    assert resp.status_code == 200

    # Key should now show as inactive in the list
    list_resp = await client.get("/api-keys", headers=auth_headers(token))
    key = next((k for k in list_resp.json() if k["id"] == key_id), None)
    assert key is not None
    assert key["is_active"] is False


@pytest.mark.asyncio
async def test_revoke_nonexistent_key(client: AsyncClient):
    token = await register_and_login(client, "ak_revoke_404@example.com")
    fake_id = str(uuid.uuid4())
    resp = await client.delete(f"/api-keys/{fake_id}", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_revoke_other_users_key_forbidden(client: AsyncClient):
    token_a = await register_and_login(client, "ak_rev_a@example.com")
    token_b = await register_and_login(client, "ak_rev_b@example.com")

    key_data = await create_api_key(client, token_a, name="User A Key", scopes=["read:models"])
    key_id = key_data["id"]

    resp = await client.delete(f"/api-keys/{key_id}", headers=auth_headers(token_b))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_revoke_requires_auth(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    resp = await client.delete(f"/api-keys/{fake_id}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Public API — Authentication Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_public_api_missing_header_returns_401(client: AsyncClient):
    """No X-API-Key header → 401."""
    token = await register_and_login(client, "pub_noheader@example.com")
    ws_id = await create_workspace(client, token)
    resp = await client.get(f"/api/v1/models?workspace_id={ws_id}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_public_api_invalid_key_returns_401(client: AsyncClient):
    """Wrong API key → 401."""
    token = await register_and_login(client, "pub_badkey@example.com")
    ws_id = await create_workspace(client, token)
    resp = await client.get(
        f"/api/v1/models?workspace_id={ws_id}",
        headers={"X-API-Key": "dyp_notavalidkey"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_public_api_revoked_key_returns_401(client: AsyncClient):
    """Revoked key is rejected with 401."""
    token = await register_and_login(client, "pub_revoked@example.com")
    ws_id = await create_workspace(client, token)
    key_data = await create_api_key(client, token, name="Will Be Revoked", scopes=["read:models"])
    raw_key = key_data["raw_key"]
    key_id = key_data["id"]

    # Confirm the key works before revoking
    resp = await client.get(
        f"/api/v1/models?workspace_id={ws_id}",
        headers=api_key_headers(raw_key),
    )
    assert resp.status_code == 200

    # Revoke the key
    await client.delete(f"/api-keys/{key_id}", headers=auth_headers(token))

    # Now it should be rejected
    resp = await client.get(
        f"/api/v1/models?workspace_id={ws_id}",
        headers=api_key_headers(raw_key),
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Public API — Models
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_public_list_models(client: AsyncClient):
    token = await register_and_login(client, "pub_list_models@example.com")
    ws_id = await create_workspace(client, token)
    await create_model(client, token, ws_id, name="API Model")

    key_data = await create_api_key(client, token, name="Read Models Key", scopes=["read:models"])
    raw_key = key_data["raw_key"]

    resp = await client.get(
        f"/api/v1/models?workspace_id={ws_id}",
        headers=api_key_headers(raw_key),
    )
    assert resp.status_code == 200
    names = [m["name"] for m in resp.json()]
    assert "API Model" in names


@pytest.mark.asyncio
async def test_public_get_model(client: AsyncClient):
    token = await register_and_login(client, "pub_get_model@example.com")
    ws_id = await create_workspace(client, token)
    model_data = await create_model(client, token, ws_id, name="Specific Model")
    model_id = model_data["id"]

    key_data = await create_api_key(client, token, name="Read Key", scopes=["read:models"])
    raw_key = key_data["raw_key"]

    resp = await client.get(f"/api/v1/models/{model_id}", headers=api_key_headers(raw_key))
    assert resp.status_code == 200
    assert resp.json()["name"] == "Specific Model"


@pytest.mark.asyncio
async def test_public_get_model_not_found(client: AsyncClient):
    token = await register_and_login(client, "pub_model_404@example.com")
    key_data = await create_api_key(client, token, name="Read Key", scopes=["read:models"])
    raw_key = key_data["raw_key"]

    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/models/{fake_id}", headers=api_key_headers(raw_key))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Public API — Dimensions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_public_list_dimensions(client: AsyncClient):
    token = await register_and_login(client, "pub_dims@example.com")
    ws_id = await create_workspace(client, token)
    model_data = await create_model(client, token, ws_id)
    model_id = model_data["id"]
    await create_dimension(client, token, model_id, name="Territories")

    key_data = await create_api_key(client, token, name="Dims Key", scopes=["read:dimensions"])
    raw_key = key_data["raw_key"]

    resp = await client.get(
        f"/api/v1/models/{model_id}/dimensions",
        headers=api_key_headers(raw_key),
    )
    assert resp.status_code == 200
    names = [d["name"] for d in resp.json()]
    assert "Territories" in names


# ---------------------------------------------------------------------------
# Public API — Cells
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_public_write_and_query_cells(client: AsyncClient):
    token = await register_and_login(client, "pub_cells@example.com")
    ws_id = await create_workspace(client, token)
    model_id = (await create_model(client, token, ws_id))["id"]
    module_id = await create_module(client, token, model_id)
    line_item_id = await create_line_item(client, token, module_id)
    member_id = str(uuid.uuid4())

    write_key_data = await create_api_key(
        client, token, name="Write Cells Key", scopes=["write:cells"]
    )
    write_raw_key = write_key_data["raw_key"]

    read_key_data = await create_api_key(
        client, token, name="Read Cells Key", scopes=["read:cells"]
    )
    read_raw_key = read_key_data["raw_key"]

    # Write a cell via public API
    write_resp = await client.post(
        "/api/v1/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": [member_id],
            "value": 42.5,
        },
        headers=api_key_headers(write_raw_key),
    )
    assert write_resp.status_code == 200
    assert write_resp.json()["value"] == 42.5

    # Query cells via public API
    query_resp = await client.post(
        "/api/v1/cells/query",
        json={"line_item_id": line_item_id},
        headers=api_key_headers(read_raw_key),
    )
    assert query_resp.status_code == 200
    cells = query_resp.json()
    assert len(cells) == 1
    assert cells[0]["value"] == 42.5


@pytest.mark.asyncio
async def test_public_bulk_write_cells(client: AsyncClient):
    token = await register_and_login(client, "pub_bulk_cells@example.com")
    ws_id = await create_workspace(client, token)
    model_id = (await create_model(client, token, ws_id))["id"]
    module_id = await create_module(client, token, model_id)
    line_item_id = await create_line_item(client, token, module_id)
    m1 = str(uuid.uuid4())
    m2 = str(uuid.uuid4())

    key_data = await create_api_key(
        client, token, name="Write Key", scopes=["write:cells"]
    )
    raw_key = key_data["raw_key"]

    resp = await client.post(
        "/api/v1/cells/bulk",
        json={
            "cells": [
                {"line_item_id": line_item_id, "dimension_members": [m1], "value": 10},
                {"line_item_id": line_item_id, "dimension_members": [m2], "value": 20},
            ]
        },
        headers=api_key_headers(raw_key),
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
@pytest.mark.backpressure
async def test_public_bulk_write_large_payload_backpressure(client: AsyncClient):
    """Public bulk-write endpoint should handle high-volume integration payloads."""
    token = await register_and_login(client, "pub_bulk_pressure@example.com")
    ws_id = await create_workspace(client, token)
    model_id = (await create_model(client, token, ws_id))["id"]
    module_id = await create_module(client, token, model_id)
    line_item_id = await create_line_item(client, token, module_id)

    write_key = await create_api_key(
        client, token, name="Write Pressure Key", scopes=["write:cells"]
    )
    read_key = await create_api_key(
        client, token, name="Read Pressure Key", scopes=["read:cells"]
    )

    dims = [str(uuid.uuid4()) for _ in range(220)]
    write_resp = await client.post(
        "/api/v1/cells/bulk",
        json={
            "cells": [
                {
                    "line_item_id": line_item_id,
                    "dimension_members": [dim],
                    "value": float(i),
                }
                for i, dim in enumerate(dims)
            ]
        },
        headers=api_key_headers(write_key["raw_key"]),
    )
    assert write_resp.status_code == 200
    assert len(write_resp.json()) == 220

    query_resp = await client.post(
        "/api/v1/cells/query",
        json={"line_item_id": line_item_id},
        headers=api_key_headers(read_key["raw_key"]),
    )
    assert query_resp.status_code == 200
    assert len(query_resp.json()) == 220


@pytest.mark.asyncio
@pytest.mark.backpressure
async def test_public_bulk_write_repeated_bursts_last_write_wins(client: AsyncClient):
    """Repeated burst writes through the public API remain one-row-per-intersection."""
    token = await register_and_login(client, "pub_bulk_bursts@example.com")
    ws_id = await create_workspace(client, token)
    model_id = (await create_model(client, token, ws_id))["id"]
    module_id = await create_module(client, token, model_id)
    line_item_id = await create_line_item(client, token, module_id)

    write_key = await create_api_key(
        client, token, name="Write Burst Key", scopes=["write:cells"]
    )
    read_key = await create_api_key(
        client, token, name="Read Burst Key", scopes=["read:cells"]
    )

    dims = [str(uuid.uuid4()) for _ in range(90)]
    burst_count = 3
    for burst in range(burst_count):
        resp = await client.post(
            "/api/v1/cells/bulk",
            json={
                "cells": [
                    {
                        "line_item_id": line_item_id,
                        "dimension_members": [dim],
                        "value": float(burst * 1000 + i),
                    }
                    for i, dim in enumerate(dims)
                ]
            },
            headers=api_key_headers(write_key["raw_key"]),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == len(dims)

    query_resp = await client.post(
        "/api/v1/cells/query",
        json={"line_item_id": line_item_id},
        headers=api_key_headers(read_key["raw_key"]),
    )
    assert query_resp.status_code == 200
    rows = query_resp.json()
    assert len(rows) == len(dims)

    values_by_key = {row["dimension_key"]: row["value"] for row in rows}
    for i, dim in enumerate(dims):
        assert values_by_key[dim] == float((burst_count - 1) * 1000 + i)


# ---------------------------------------------------------------------------
# Scope Enforcement Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_read_scope_cannot_write_cells(client: AsyncClient):
    """A key with only read:cells scope is rejected for write:cells endpoints."""
    token = await register_and_login(client, "scope_read_write@example.com")
    key_data = await create_api_key(client, token, name="Read Only Key", scopes=["read:cells"])
    raw_key = key_data["raw_key"]
    line_item_id = str(uuid.uuid4())
    member_id = str(uuid.uuid4())

    resp = await client.post(
        "/api/v1/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": [member_id],
            "value": 99,
        },
        headers=api_key_headers(raw_key),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_write_scope_cannot_read_models(client: AsyncClient):
    """A key with only write:cells scope cannot access read:models endpoints."""
    token = await register_and_login(client, "scope_write_noread@example.com")
    ws_id = await create_workspace(client, token)
    key_data = await create_api_key(client, token, name="Write Only Key", scopes=["write:cells"])
    raw_key = key_data["raw_key"]

    resp = await client.get(
        f"/api/v1/models?workspace_id={ws_id}",
        headers=api_key_headers(raw_key),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_scope_grants_all_access(client: AsyncClient):
    """A key with admin scope can access any endpoint."""
    token = await register_and_login(client, "scope_admin@example.com")
    ws_id = await create_workspace(client, token)
    await create_model(client, token, ws_id, name="Admin Accessible Model")

    key_data = await create_api_key(client, token, name="Admin Key", scopes=["admin"])
    raw_key = key_data["raw_key"]

    # Can list models (normally requires read:models)
    resp = await client.get(
        f"/api/v1/models?workspace_id={ws_id}",
        headers=api_key_headers(raw_key),
    )
    assert resp.status_code == 200

    # Can write cells (normally requires write:cells)
    line_item_id = str(uuid.uuid4())
    member_id = str(uuid.uuid4())
    resp = await client.post(
        "/api/v1/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": [member_id],
            "value": 1,
        },
        headers=api_key_headers(raw_key),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_missing_dimensions_scope_returns_403(client: AsyncClient):
    """A key with read:models but not read:dimensions is forbidden on dimensions endpoint."""
    token = await register_and_login(client, "scope_nodim@example.com")
    ws_id = await create_workspace(client, token)
    model_data = await create_model(client, token, ws_id)
    model_id = model_data["id"]

    key_data = await create_api_key(client, token, name="No Dims Key", scopes=["read:models"])
    raw_key = key_data["raw_key"]

    resp = await client.get(
        f"/api/v1/models/{model_id}/dimensions",
        headers=api_key_headers(raw_key),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_two_unique_keys_have_different_values(client: AsyncClient):
    """Two separately generated keys should be distinct."""
    token = await register_and_login(client, "unique_keys@example.com")
    key1 = await create_api_key(client, token, name="Key 1", scopes=["read:models"])
    key2 = await create_api_key(client, token, name="Key 2", scopes=["read:models"])
    assert key1["raw_key"] != key2["raw_key"]
    assert key1["id"] != key2["id"]
