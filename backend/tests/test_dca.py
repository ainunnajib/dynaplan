"""
Tests for F035: Selective access and Dynamic Cell Access (DCA).
"""
import uuid

import pytest
from httpx import AsyncClient

# Import DCA models so their tables are registered with Base.metadata
# before conftest's setup_database fixture creates all tables.
import app.models.dca  # noqa: F401



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


async def create_workspace(client: AsyncClient, token: str, name: str = "DCA Test WS") -> str:
    resp = await client.post(
        "/workspaces/",
        json={"name": name},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_model(
    client: AsyncClient, token: str, workspace_id: str, name: str = "DCA Test Model"
) -> str:
    resp = await client.post(
        "/models",
        json={"name": name, "workspace_id": workspace_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_dimension(
    client: AsyncClient, token: str, model_id: str, name: str = "Products"
) -> str:
    resp = await client.post(
        f"/models/{model_id}/dimensions",
        json={"name": name, "dimension_type": "custom"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_dimension_item(
    client: AsyncClient, token: str, dimension_id: str, name: str, code: str
) -> str:
    resp = await client.post(
        f"/dimensions/{dimension_id}/items",
        json={"name": name, "code": code},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_module(
    client: AsyncClient, token: str, model_id: str, name: str = "Sales Module"
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
    fmt: str = "number",
) -> str:
    resp = await client.post(
        f"/modules/{module_id}/line-items",
        json={"name": name, "format": fmt},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def set_cell_value(
    client: AsyncClient,
    token: str,
    line_item_id: str,
    dimension_key: str,
    value_boolean: bool,
) -> None:
    """Write a boolean cell value. dimension_key is a pipe-separated string of UUIDs."""
    dimension_members = [mid for mid in dimension_key.split("|") if mid.strip()]
    resp = await client.post(
        "/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": dimension_members,
            "value": value_boolean,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code in (200, 201), f"set_cell_value failed: {resp.status_code} {resp.text}"


async def get_user_id(client: AsyncClient, token: str) -> str:
    resp = await client.get("/auth/me", headers=auth_headers(token))
    assert resp.status_code == 200
    return resp.json()["id"]


async def scaffold(client: AsyncClient):
    """Create a complete scaffold: owner, workspace, model, dimension, items, module, line items."""
    owner_token = await register_and_login(client, "dca_owner@example.com")
    ws_id = await create_workspace(client, owner_token)
    model_id = await create_model(client, owner_token, ws_id)
    dim_id = await create_dimension(client, owner_token, model_id)
    item1_id = await create_dimension_item(client, owner_token, dim_id, "Product A", "PA")
    item2_id = await create_dimension_item(client, owner_token, dim_id, "Product B", "PB")
    mod_id = await create_module(client, owner_token, model_id)
    li_id = await create_line_item(client, owner_token, mod_id, "Revenue", "number")
    read_driver_id = await create_line_item(client, owner_token, mod_id, "ReadDriver", "boolean")
    write_driver_id = await create_line_item(client, owner_token, mod_id, "WriteDriver", "boolean")
    owner_id = await get_user_id(client, owner_token)

    return {
        "owner_token": owner_token,
        "owner_id": owner_id,
        "ws_id": ws_id,
        "model_id": model_id,
        "dim_id": dim_id,
        "item1_id": item1_id,
        "item2_id": item2_id,
        "mod_id": mod_id,
        "li_id": li_id,
        "read_driver_id": read_driver_id,
        "write_driver_id": write_driver_id,
    }


# ===========================================================================
# Selective Access Rules — CRUD
# ===========================================================================

@pytest.mark.asyncio
async def test_create_selective_access_rule(client: AsyncClient):
    """Owner can create a selective access rule."""
    s = await scaffold(client)
    resp = await client.post(
        f"/models/{s['model_id']}/selective-access",
        json={"name": "Product Access", "dimension_id": s["dim_id"]},
        headers=auth_headers(s["owner_token"]),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Product Access"
    assert data["dimension_id"] == s["dim_id"]
    assert data["model_id"] == s["model_id"]
    assert "id" in data


@pytest.mark.asyncio
async def test_create_selective_access_rule_with_description(client: AsyncClient):
    """Rule can have an optional description."""
    s = await scaffold(client)
    resp = await client.post(
        f"/models/{s['model_id']}/selective-access",
        json={
            "name": "Region Access",
            "dimension_id": s["dim_id"],
            "description": "Controls access by region",
        },
        headers=auth_headers(s["owner_token"]),
    )
    assert resp.status_code == 201
    assert resp.json()["description"] == "Controls access by region"


@pytest.mark.asyncio
async def test_create_selective_access_rule_requires_auth(client: AsyncClient):
    """Creating a rule requires authentication."""
    fake_model_id = str(uuid.uuid4())
    resp = await client.post(
        f"/models/{fake_model_id}/selective-access",
        json={"name": "Test", "dimension_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_selective_access_rule_nonexistent_model(client: AsyncClient):
    """Creating a rule on a nonexistent model returns 404."""
    token = await register_and_login(client, "dca_rule404@example.com")
    fake_model_id = str(uuid.uuid4())
    resp = await client.post(
        f"/models/{fake_model_id}/selective-access",
        json={"name": "Test", "dimension_id": str(uuid.uuid4())},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_selective_access_rule_non_owner_forbidden(client: AsyncClient):
    """Non-owner cannot create selective access rules."""
    s = await scaffold(client)
    other_token = await register_and_login(client, "dca_nonowner@example.com")
    resp = await client.post(
        f"/models/{s['model_id']}/selective-access",
        json={"name": "Test", "dimension_id": s["dim_id"]},
        headers=auth_headers(other_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_selective_access_rules(client: AsyncClient):
    """Owner can list selective access rules for a model."""
    s = await scaffold(client)
    # Create two rules
    await client.post(
        f"/models/{s['model_id']}/selective-access",
        json={"name": "Rule 1", "dimension_id": s["dim_id"]},
        headers=auth_headers(s["owner_token"]),
    )
    await client.post(
        f"/models/{s['model_id']}/selective-access",
        json={"name": "Rule 2", "dimension_id": s["dim_id"]},
        headers=auth_headers(s["owner_token"]),
    )

    resp = await client.get(
        f"/models/{s['model_id']}/selective-access",
        headers=auth_headers(s["owner_token"]),
    )
    assert resp.status_code == 200
    rules = resp.json()
    assert len(rules) == 2
    names = {r["name"] for r in rules}
    assert names == {"Rule 1", "Rule 2"}


@pytest.mark.asyncio
async def test_list_selective_access_rules_empty(client: AsyncClient):
    """Listing rules on a model with none returns empty list."""
    s = await scaffold(client)
    resp = await client.get(
        f"/models/{s['model_id']}/selective-access",
        headers=auth_headers(s["owner_token"]),
    )
    assert resp.status_code == 200
    assert resp.json() == []


# ===========================================================================
# Selective Access Grants — CRUD
# ===========================================================================

@pytest.mark.asyncio
async def test_add_grant_to_rule(client: AsyncClient):
    """Owner can add a grant to a selective access rule."""
    s = await scaffold(client)
    rule_resp = await client.post(
        f"/models/{s['model_id']}/selective-access",
        json={"name": "Product Access", "dimension_id": s["dim_id"]},
        headers=auth_headers(s["owner_token"]),
    )
    rule_id = rule_resp.json()["id"]

    resp = await client.post(
        f"/selective-access/{rule_id}/grants",
        json={
            "user_id": s["owner_id"],
            "dimension_item_id": s["item1_id"],
            "access_level": "write",
        },
        headers=auth_headers(s["owner_token"]),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["rule_id"] == rule_id
    assert data["user_id"] == s["owner_id"]
    assert data["dimension_item_id"] == s["item1_id"]
    assert data["access_level"] == "write"


@pytest.mark.asyncio
async def test_add_grant_read_access(client: AsyncClient):
    """Grant with read-only access level."""
    s = await scaffold(client)
    rule_resp = await client.post(
        f"/models/{s['model_id']}/selective-access",
        json={"name": "Read Rule", "dimension_id": s["dim_id"]},
        headers=auth_headers(s["owner_token"]),
    )
    rule_id = rule_resp.json()["id"]

    resp = await client.post(
        f"/selective-access/{rule_id}/grants",
        json={
            "user_id": s["owner_id"],
            "dimension_item_id": s["item1_id"],
            "access_level": "read",
        },
        headers=auth_headers(s["owner_token"]),
    )
    assert resp.status_code == 201
    assert resp.json()["access_level"] == "read"


@pytest.mark.asyncio
async def test_add_grant_none_access(client: AsyncClient):
    """Grant with none access denies all access."""
    s = await scaffold(client)
    rule_resp = await client.post(
        f"/models/{s['model_id']}/selective-access",
        json={"name": "None Rule", "dimension_id": s["dim_id"]},
        headers=auth_headers(s["owner_token"]),
    )
    rule_id = rule_resp.json()["id"]

    resp = await client.post(
        f"/selective-access/{rule_id}/grants",
        json={
            "user_id": s["owner_id"],
            "dimension_item_id": s["item1_id"],
            "access_level": "none",
        },
        headers=auth_headers(s["owner_token"]),
    )
    assert resp.status_code == 201
    assert resp.json()["access_level"] == "none"


@pytest.mark.asyncio
async def test_add_grant_nonexistent_rule(client: AsyncClient):
    """Adding a grant to a nonexistent rule returns 404."""
    s = await scaffold(client)
    fake_rule_id = str(uuid.uuid4())
    resp = await client.post(
        f"/selective-access/{fake_rule_id}/grants",
        json={
            "user_id": s["owner_id"],
            "dimension_item_id": s["item1_id"],
            "access_level": "read",
        },
        headers=auth_headers(s["owner_token"]),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_add_grant_requires_auth(client: AsyncClient):
    """Adding a grant requires authentication."""
    fake_rule_id = str(uuid.uuid4())
    resp = await client.post(
        f"/selective-access/{fake_rule_id}/grants",
        json={
            "user_id": str(uuid.uuid4()),
            "dimension_item_id": str(uuid.uuid4()),
            "access_level": "read",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_grants_for_rule(client: AsyncClient):
    """Owner can list all grants for a rule."""
    s = await scaffold(client)
    rule_resp = await client.post(
        f"/models/{s['model_id']}/selective-access",
        json={"name": "Multi Grant Rule", "dimension_id": s["dim_id"]},
        headers=auth_headers(s["owner_token"]),
    )
    rule_id = rule_resp.json()["id"]

    # Add two grants
    await client.post(
        f"/selective-access/{rule_id}/grants",
        json={
            "user_id": s["owner_id"],
            "dimension_item_id": s["item1_id"],
            "access_level": "write",
        },
        headers=auth_headers(s["owner_token"]),
    )
    await client.post(
        f"/selective-access/{rule_id}/grants",
        json={
            "user_id": s["owner_id"],
            "dimension_item_id": s["item2_id"],
            "access_level": "read",
        },
        headers=auth_headers(s["owner_token"]),
    )

    resp = await client.get(
        f"/selective-access/{rule_id}/grants",
        headers=auth_headers(s["owner_token"]),
    )
    assert resp.status_code == 200
    grants = resp.json()
    assert len(grants) == 2


@pytest.mark.asyncio
async def test_remove_grant(client: AsyncClient):
    """Owner can remove a grant."""
    s = await scaffold(client)
    rule_resp = await client.post(
        f"/models/{s['model_id']}/selective-access",
        json={"name": "Remove Grant Rule", "dimension_id": s["dim_id"]},
        headers=auth_headers(s["owner_token"]),
    )
    rule_id = rule_resp.json()["id"]

    grant_resp = await client.post(
        f"/selective-access/{rule_id}/grants",
        json={
            "user_id": s["owner_id"],
            "dimension_item_id": s["item1_id"],
            "access_level": "write",
        },
        headers=auth_headers(s["owner_token"]),
    )
    grant_id = grant_resp.json()["id"]

    resp = await client.delete(
        f"/selective-access/{rule_id}/grants/{grant_id}",
        headers=auth_headers(s["owner_token"]),
    )
    assert resp.status_code == 204

    # Verify removal
    list_resp = await client.get(
        f"/selective-access/{rule_id}/grants",
        headers=auth_headers(s["owner_token"]),
    )
    assert len(list_resp.json()) == 0


@pytest.mark.asyncio
async def test_remove_nonexistent_grant(client: AsyncClient):
    """Removing a nonexistent grant returns 404."""
    s = await scaffold(client)
    rule_resp = await client.post(
        f"/models/{s['model_id']}/selective-access",
        json={"name": "NoGrant Rule", "dimension_id": s["dim_id"]},
        headers=auth_headers(s["owner_token"]),
    )
    rule_id = rule_resp.json()["id"]
    fake_grant_id = str(uuid.uuid4())

    resp = await client.delete(
        f"/selective-access/{rule_id}/grants/{fake_grant_id}",
        headers=auth_headers(s["owner_token"]),
    )
    assert resp.status_code == 404


# ===========================================================================
# DCA Config — CRUD
# ===========================================================================

@pytest.mark.asyncio
async def test_create_dca_config(client: AsyncClient):
    """Can create a DCA config for a line item."""
    s = await scaffold(client)
    resp = await client.post(
        f"/line-items/{s['li_id']}/dca",
        json={
            "read_driver_line_item_id": s["read_driver_id"],
            "write_driver_line_item_id": s["write_driver_id"],
        },
        headers=auth_headers(s["owner_token"]),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["line_item_id"] == s["li_id"]
    assert data["read_driver_line_item_id"] == s["read_driver_id"]
    assert data["write_driver_line_item_id"] == s["write_driver_id"]


@pytest.mark.asyncio
async def test_create_dca_config_write_driver_only(client: AsyncClient):
    """DCA config with only write driver, no read driver."""
    s = await scaffold(client)
    resp = await client.post(
        f"/line-items/{s['li_id']}/dca",
        json={"write_driver_line_item_id": s["write_driver_id"]},
        headers=auth_headers(s["owner_token"]),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["read_driver_line_item_id"] is None
    assert data["write_driver_line_item_id"] == s["write_driver_id"]


@pytest.mark.asyncio
async def test_create_dca_config_requires_auth(client: AsyncClient):
    """DCA config requires auth."""
    fake_li_id = str(uuid.uuid4())
    resp = await client.post(
        f"/line-items/{fake_li_id}/dca",
        json={},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_dca_config(client: AsyncClient):
    """Can retrieve DCA config for a line item."""
    s = await scaffold(client)
    await client.post(
        f"/line-items/{s['li_id']}/dca",
        json={"read_driver_line_item_id": s["read_driver_id"]},
        headers=auth_headers(s["owner_token"]),
    )

    resp = await client.get(
        f"/line-items/{s['li_id']}/dca",
        headers=auth_headers(s["owner_token"]),
    )
    assert resp.status_code == 200
    assert resp.json()["read_driver_line_item_id"] == s["read_driver_id"]


@pytest.mark.asyncio
async def test_get_dca_config_not_found(client: AsyncClient):
    """Getting DCA config for a line item without one returns 404."""
    s = await scaffold(client)
    resp = await client.get(
        f"/line-items/{s['li_id']}/dca",
        headers=auth_headers(s["owner_token"]),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_dca_config(client: AsyncClient):
    """Can delete DCA config for a line item."""
    s = await scaffold(client)
    await client.post(
        f"/line-items/{s['li_id']}/dca",
        json={"read_driver_line_item_id": s["read_driver_id"]},
        headers=auth_headers(s["owner_token"]),
    )

    resp = await client.delete(
        f"/line-items/{s['li_id']}/dca",
        headers=auth_headers(s["owner_token"]),
    )
    assert resp.status_code == 204

    # Verify deletion
    get_resp = await client.get(
        f"/line-items/{s['li_id']}/dca",
        headers=auth_headers(s["owner_token"]),
    )
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_dca_config_not_found(client: AsyncClient):
    """Deleting DCA config that doesn't exist returns 404."""
    s = await scaffold(client)
    resp = await client.delete(
        f"/line-items/{s['li_id']}/dca",
        headers=auth_headers(s["owner_token"]),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_dca_config_via_create(client: AsyncClient):
    """Creating DCA config for a line item that already has one updates it."""
    s = await scaffold(client)
    # Create initial config with read driver
    await client.post(
        f"/line-items/{s['li_id']}/dca",
        json={"read_driver_line_item_id": s["read_driver_id"]},
        headers=auth_headers(s["owner_token"]),
    )
    # Update with write driver
    resp = await client.post(
        f"/line-items/{s['li_id']}/dca",
        json={"write_driver_line_item_id": s["write_driver_id"]},
        headers=auth_headers(s["owner_token"]),
    )
    assert resp.status_code == 201
    data = resp.json()
    # Read driver should be cleared, write driver set
    assert data["read_driver_line_item_id"] is None
    assert data["write_driver_line_item_id"] == s["write_driver_id"]


# ===========================================================================
# Cell Access Check — access-check endpoint
# ===========================================================================

@pytest.mark.asyncio
async def test_cell_access_check_no_restrictions(client: AsyncClient):
    """Without any rules or DCA config, full access is granted."""
    s = await scaffold(client)
    dimension_key = s["item1_id"]

    resp = await client.get(
        "/cells/access-check",
        params={"line_item_id": s["li_id"], "dimension_key": dimension_key},
        headers=auth_headers(s["owner_token"]),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["can_read"] is True
    assert data["can_write"] is True
    assert "Full access granted" in data["reason"]


@pytest.mark.asyncio
async def test_cell_access_check_requires_auth(client: AsyncClient):
    """Access check requires authentication."""
    resp = await client.get(
        "/cells/access-check",
        params={"line_item_id": str(uuid.uuid4()), "dimension_key": "test"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_cell_access_selective_read_only(client: AsyncClient):
    """Selective access grant with read-only restricts write access."""
    s = await scaffold(client)
    # Create rule and grant read-only access to item1
    rule_resp = await client.post(
        f"/models/{s['model_id']}/selective-access",
        json={"name": "Read Only Rule", "dimension_id": s["dim_id"]},
        headers=auth_headers(s["owner_token"]),
    )
    rule_id = rule_resp.json()["id"]

    await client.post(
        f"/selective-access/{rule_id}/grants",
        json={
            "user_id": s["owner_id"],
            "dimension_item_id": s["item1_id"],
            "access_level": "read",
        },
        headers=auth_headers(s["owner_token"]),
    )

    resp = await client.get(
        "/cells/access-check",
        params={"line_item_id": s["li_id"], "dimension_key": s["item1_id"]},
        headers=auth_headers(s["owner_token"]),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["can_read"] is True
    assert data["can_write"] is False
    assert "read-only" in data["reason"]


@pytest.mark.asyncio
async def test_cell_access_selective_none(client: AsyncClient):
    """Selective access grant with none denies all access."""
    s = await scaffold(client)
    rule_resp = await client.post(
        f"/models/{s['model_id']}/selective-access",
        json={"name": "None Rule", "dimension_id": s["dim_id"]},
        headers=auth_headers(s["owner_token"]),
    )
    rule_id = rule_resp.json()["id"]

    await client.post(
        f"/selective-access/{rule_id}/grants",
        json={
            "user_id": s["owner_id"],
            "dimension_item_id": s["item1_id"],
            "access_level": "none",
        },
        headers=auth_headers(s["owner_token"]),
    )

    resp = await client.get(
        "/cells/access-check",
        params={"line_item_id": s["li_id"], "dimension_key": s["item1_id"]},
        headers=auth_headers(s["owner_token"]),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["can_read"] is False
    assert data["can_write"] is False


@pytest.mark.asyncio
async def test_cell_access_selective_write(client: AsyncClient):
    """Selective access grant with write allows full read+write."""
    s = await scaffold(client)
    rule_resp = await client.post(
        f"/models/{s['model_id']}/selective-access",
        json={"name": "Write Rule", "dimension_id": s["dim_id"]},
        headers=auth_headers(s["owner_token"]),
    )
    rule_id = rule_resp.json()["id"]

    await client.post(
        f"/selective-access/{rule_id}/grants",
        json={
            "user_id": s["owner_id"],
            "dimension_item_id": s["item1_id"],
            "access_level": "write",
        },
        headers=auth_headers(s["owner_token"]),
    )

    resp = await client.get(
        "/cells/access-check",
        params={"line_item_id": s["li_id"], "dimension_key": s["item1_id"]},
        headers=auth_headers(s["owner_token"]),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["can_read"] is True
    assert data["can_write"] is True


# ===========================================================================
# DCA Driver — Access Check
# ===========================================================================

@pytest.mark.asyncio
async def test_dca_read_driver_false_denies_all(client: AsyncClient):
    """When read driver evaluates to False, both read and write are denied."""
    s = await scaffold(client)
    dimension_key = s["item1_id"]

    # Set up DCA with read driver
    await client.post(
        f"/line-items/{s['li_id']}/dca",
        json={"read_driver_line_item_id": s["read_driver_id"]},
        headers=auth_headers(s["owner_token"]),
    )

    # Set the read driver cell value to False
    await set_cell_value(
        client, s["owner_token"], s["read_driver_id"], dimension_key, False
    )

    resp = await client.get(
        "/cells/access-check",
        params={"line_item_id": s["li_id"], "dimension_key": dimension_key},
        headers=auth_headers(s["owner_token"]),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["can_read"] is False
    assert data["can_write"] is False
    assert "read driver" in data["reason"].lower()


@pytest.mark.asyncio
async def test_dca_write_driver_false_denies_write(client: AsyncClient):
    """When write driver evaluates to False, write is denied but read is allowed."""
    s = await scaffold(client)
    dimension_key = s["item1_id"]

    # Set up DCA with write driver only
    await client.post(
        f"/line-items/{s['li_id']}/dca",
        json={"write_driver_line_item_id": s["write_driver_id"]},
        headers=auth_headers(s["owner_token"]),
    )

    # Set the write driver cell value to False
    await set_cell_value(
        client, s["owner_token"], s["write_driver_id"], dimension_key, False
    )

    resp = await client.get(
        "/cells/access-check",
        params={"line_item_id": s["li_id"], "dimension_key": dimension_key},
        headers=auth_headers(s["owner_token"]),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["can_read"] is True
    assert data["can_write"] is False
    assert "write driver" in data["reason"].lower()


@pytest.mark.asyncio
async def test_dca_drivers_true_allows_all(client: AsyncClient):
    """When both drivers evaluate to True, full access is granted."""
    s = await scaffold(client)
    dimension_key = s["item1_id"]

    # Set up DCA with both drivers
    await client.post(
        f"/line-items/{s['li_id']}/dca",
        json={
            "read_driver_line_item_id": s["read_driver_id"],
            "write_driver_line_item_id": s["write_driver_id"],
        },
        headers=auth_headers(s["owner_token"]),
    )

    # Set both driver cell values to True
    await set_cell_value(
        client, s["owner_token"], s["read_driver_id"], dimension_key, True
    )
    await set_cell_value(
        client, s["owner_token"], s["write_driver_id"], dimension_key, True
    )

    resp = await client.get(
        "/cells/access-check",
        params={"line_item_id": s["li_id"], "dimension_key": dimension_key},
        headers=auth_headers(s["owner_token"]),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["can_read"] is True
    assert data["can_write"] is True


# ===========================================================================
# Combined: Selective Access + DCA
# ===========================================================================

@pytest.mark.asyncio
async def test_combined_selective_write_and_dca_write_driver_false(client: AsyncClient):
    """Selective access grants write but DCA write driver denies it."""
    s = await scaffold(client)
    dimension_key = s["item1_id"]

    # Selective access: write
    rule_resp = await client.post(
        f"/models/{s['model_id']}/selective-access",
        json={"name": "Combined Rule", "dimension_id": s["dim_id"]},
        headers=auth_headers(s["owner_token"]),
    )
    rule_id = rule_resp.json()["id"]
    await client.post(
        f"/selective-access/{rule_id}/grants",
        json={
            "user_id": s["owner_id"],
            "dimension_item_id": s["item1_id"],
            "access_level": "write",
        },
        headers=auth_headers(s["owner_token"]),
    )

    # DCA: write driver = False
    await client.post(
        f"/line-items/{s['li_id']}/dca",
        json={"write_driver_line_item_id": s["write_driver_id"]},
        headers=auth_headers(s["owner_token"]),
    )
    await set_cell_value(
        client, s["owner_token"], s["write_driver_id"], dimension_key, False
    )

    resp = await client.get(
        "/cells/access-check",
        params={"line_item_id": s["li_id"], "dimension_key": dimension_key},
        headers=auth_headers(s["owner_token"]),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["can_read"] is True
    assert data["can_write"] is False


@pytest.mark.asyncio
async def test_combined_selective_none_overrides_dca(client: AsyncClient):
    """Selective access 'none' denies even when DCA drivers are True."""
    s = await scaffold(client)
    dimension_key = s["item1_id"]

    # Selective access: none
    rule_resp = await client.post(
        f"/models/{s['model_id']}/selective-access",
        json={"name": "Block Rule", "dimension_id": s["dim_id"]},
        headers=auth_headers(s["owner_token"]),
    )
    rule_id = rule_resp.json()["id"]
    await client.post(
        f"/selective-access/{rule_id}/grants",
        json={
            "user_id": s["owner_id"],
            "dimension_item_id": s["item1_id"],
            "access_level": "none",
        },
        headers=auth_headers(s["owner_token"]),
    )

    # DCA: both drivers True
    await client.post(
        f"/line-items/{s['li_id']}/dca",
        json={
            "read_driver_line_item_id": s["read_driver_id"],
            "write_driver_line_item_id": s["write_driver_id"],
        },
        headers=auth_headers(s["owner_token"]),
    )
    await set_cell_value(
        client, s["owner_token"], s["read_driver_id"], dimension_key, True
    )
    await set_cell_value(
        client, s["owner_token"], s["write_driver_id"], dimension_key, True
    )

    resp = await client.get(
        "/cells/access-check",
        params={"line_item_id": s["li_id"], "dimension_key": dimension_key},
        headers=auth_headers(s["owner_token"]),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["can_read"] is False
    assert data["can_write"] is False


@pytest.mark.asyncio
async def test_dca_no_cell_value_defaults_to_true(client: AsyncClient):
    """When no driver cell value exists, access defaults to allowed."""
    s = await scaffold(client)
    dimension_key = s["item1_id"]

    # DCA with read driver but no cell value set for it
    await client.post(
        f"/line-items/{s['li_id']}/dca",
        json={"read_driver_line_item_id": s["read_driver_id"]},
        headers=auth_headers(s["owner_token"]),
    )

    resp = await client.get(
        "/cells/access-check",
        params={"line_item_id": s["li_id"], "dimension_key": dimension_key},
        headers=auth_headers(s["owner_token"]),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["can_read"] is True
    assert data["can_write"] is True
