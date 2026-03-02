"""
Tests for Feature F039: Application Lifecycle Management (ALM).

Covers:
  - Environment CRUD (create, list, get, update, delete via 404)
  - Lock / unlock
  - Revision tags (create, list, duplicate name)
  - Promotion lifecycle (initiate, complete, fail)
  - Promotion history
  - Tag comparison
  - Auth required for all endpoints
  - 404 handling for missing resources
"""
import uuid

import pytest
from httpx import AsyncClient

# Import models so they are registered with Base.metadata before create_all.
from app.models.alm import (  # noqa: F401
    ALMEnvironment,
    PromotionRecord,
    RevisionTag,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def register_and_login(
    client: AsyncClient,
    email: str,
    password: str = "testpass123",
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


async def create_workspace(client: AsyncClient, token: str, name: str = "Test WS") -> str:
    resp = await client.post(
        "/workspaces/",
        json={"name": name},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_model(
    client: AsyncClient, token: str, workspace_id: str, name: str = "Test Model"
) -> str:
    resp = await client.post(
        "/models",
        json={"name": name, "workspace_id": workspace_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def setup_env(client: AsyncClient, email: str):
    """Register user, create workspace and model. Returns (token, model_id)."""
    token = await register_and_login(client, email)
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    return token, model_id


async def create_alm_environment(
    client: AsyncClient, token: str, model_id: str,
    env_type: str = "dev", name: str = "Development",
) -> dict:
    resp = await client.post(
        f"/models/{model_id}/environments",
        json={"env_type": env_type, "name": name},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def create_tag(
    client: AsyncClient, token: str, env_id: str,
    tag_name: str = "v1.0", snapshot_data: dict = None,
) -> dict:
    body = {"tag_name": tag_name}
    if snapshot_data is not None:
        body["snapshot_data"] = snapshot_data
    resp = await client.post(
        f"/environments/{env_id}/tags",
        json=body,
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def create_dimension(
    client: AsyncClient,
    token: str,
    model_id: str,
    name: str = "Products",
    dimension_type: str = "custom",
) -> dict:
    resp = await client.post(
        f"/models/{model_id}/dimensions",
        json={"name": name, "dimension_type": dimension_type},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def create_dimension_item(
    client: AsyncClient,
    token: str,
    dimension_id: str,
    name: str,
    code: str,
    parent_id: str = None,
    sort_order: int = 0,
) -> dict:
    body = {
        "name": name,
        "code": code,
        "sort_order": sort_order,
    }
    if parent_id is not None:
        body["parent_id"] = parent_id
    resp = await client.post(
        f"/dimensions/{dimension_id}/items",
        json=body,
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def create_module(
    client: AsyncClient,
    token: str,
    model_id: str,
    name: str = "Revenue",
) -> dict:
    resp = await client.post(
        f"/models/{model_id}/modules",
        json={"name": name},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def create_line_item(
    client: AsyncClient,
    token: str,
    module_id: str,
    name: str,
    applies_to_dimensions: list = None,
    formula: str = None,
) -> dict:
    body = {
        "name": name,
        "format": "number",
    }
    if applies_to_dimensions is not None:
        body["applies_to_dimensions"] = applies_to_dimensions
    if formula is not None:
        body["formula"] = formula
    resp = await client.post(
        f"/modules/{module_id}/line-items",
        json=body,
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def write_cell(
    client: AsyncClient,
    token: str,
    line_item_id: str,
    dimension_members: list,
    value,
) -> dict:
    resp = await client.post(
        "/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": dimension_members,
            "value": value,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    return resp.json()


# ---------------------------------------------------------------------------
# Environment CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_environment(client: AsyncClient):
    token, model_id = await setup_env(client, "alm1@test.com")
    env = await create_alm_environment(client, token, model_id)
    assert env["env_type"] == "dev"
    assert env["name"] == "Development"
    assert env["is_locked"] is False
    assert env["model_id"] == model_id


@pytest.mark.asyncio
async def test_create_environment_all_types(client: AsyncClient):
    token, model_id = await setup_env(client, "alm2@test.com")
    for env_type, name in [("dev", "Dev"), ("test", "Test"), ("prod", "Prod")]:
        env = await create_alm_environment(client, token, model_id, env_type, name)
        assert env["env_type"] == env_type


@pytest.mark.asyncio
async def test_list_environments(client: AsyncClient):
    token, model_id = await setup_env(client, "alm3@test.com")
    await create_alm_environment(client, token, model_id, "dev", "Dev")
    await create_alm_environment(client, token, model_id, "prod", "Prod")
    resp = await client.get(
        f"/models/{model_id}/environments",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    envs = resp.json()
    assert len(envs) == 2


@pytest.mark.asyncio
async def test_get_environment(client: AsyncClient):
    token, model_id = await setup_env(client, "alm4@test.com")
    env = await create_alm_environment(client, token, model_id)
    resp = await client.get(
        f"/environments/{env['id']}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == env["id"]


@pytest.mark.asyncio
async def test_get_environment_not_found(client: AsyncClient):
    token, _ = await setup_env(client, "alm5@test.com")
    resp = await client.get(
        f"/environments/{uuid.uuid4()}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_environment(client: AsyncClient):
    token, model_id = await setup_env(client, "alm6@test.com")
    env = await create_alm_environment(client, token, model_id)
    resp = await client.put(
        f"/environments/{env['id']}",
        json={"name": "Updated Dev", "description": "Updated desc"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Dev"
    assert resp.json()["description"] == "Updated desc"


@pytest.mark.asyncio
async def test_update_environment_not_found(client: AsyncClient):
    token, _ = await setup_env(client, "alm7@test.com")
    resp = await client.put(
        f"/environments/{uuid.uuid4()}",
        json={"name": "Nope"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_environment_with_source(client: AsyncClient):
    token, model_id = await setup_env(client, "alm8@test.com")
    dev_env = await create_alm_environment(client, token, model_id, "dev", "Dev")
    resp = await client.post(
        f"/models/{model_id}/environments",
        json={"env_type": "test", "name": "Test", "source_env_id": dev_env["id"]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    assert resp.json()["source_env_id"] == dev_env["id"]


@pytest.mark.asyncio
async def test_create_environment_model_not_found(client: AsyncClient):
    token, _ = await setup_env(client, "alm9@test.com")
    resp = await client.post(
        f"/models/{uuid.uuid4()}/environments",
        json={"env_type": "dev", "name": "Dev"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_environments_model_not_found(client: AsyncClient):
    token, _ = await setup_env(client, "alm10@test.com")
    resp = await client.get(
        f"/models/{uuid.uuid4()}/environments",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Lock / Unlock
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lock_environment(client: AsyncClient):
    token, model_id = await setup_env(client, "alm11@test.com")
    env = await create_alm_environment(client, token, model_id)
    assert env["is_locked"] is False
    resp = await client.put(
        f"/environments/{env['id']}/lock",
        json={"is_locked": True},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["is_locked"] is True


@pytest.mark.asyncio
async def test_unlock_environment(client: AsyncClient):
    token, model_id = await setup_env(client, "alm12@test.com")
    env = await create_alm_environment(client, token, model_id)
    # Lock first
    await client.put(
        f"/environments/{env['id']}/lock",
        json={"is_locked": True},
        headers=auth_headers(token),
    )
    # Unlock
    resp = await client.put(
        f"/environments/{env['id']}/lock",
        json={"is_locked": False},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["is_locked"] is False


@pytest.mark.asyncio
async def test_lock_not_found(client: AsyncClient):
    token, _ = await setup_env(client, "alm13@test.com")
    resp = await client.put(
        f"/environments/{uuid.uuid4()}/lock",
        json={"is_locked": True},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Revision Tags
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_revision_tag(client: AsyncClient):
    token, model_id = await setup_env(client, "alm14@test.com")
    env = await create_alm_environment(client, token, model_id)
    tag = await create_tag(client, token, env["id"], "v1.0", {"modules": ["mod1"]})
    assert tag["tag_name"] == "v1.0"
    assert tag["snapshot_data"]["modules"] == ["mod1"]
    assert tag["environment_id"] == env["id"]


@pytest.mark.asyncio
async def test_create_tag_no_snapshot(client: AsyncClient):
    token, model_id = await setup_env(client, "alm15@test.com")
    env = await create_alm_environment(client, token, model_id)
    tag = await create_tag(client, token, env["id"], "v0.1")
    assert tag["tag_name"] == "v0.1"
    snapshot_data = tag["snapshot_data"]
    assert isinstance(snapshot_data, dict)
    assert "dimensions" in snapshot_data
    assert "dimension_items" in snapshot_data
    assert "modules" in snapshot_data
    assert "line_items" in snapshot_data
    assert "cell_values" in snapshot_data


@pytest.mark.asyncio
async def test_list_revision_tags(client: AsyncClient):
    token, model_id = await setup_env(client, "alm16@test.com")
    env = await create_alm_environment(client, token, model_id)
    await create_tag(client, token, env["id"], "v1.0")
    await create_tag(client, token, env["id"], "v2.0")
    resp = await client.get(
        f"/environments/{env['id']}/tags",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    tags = resp.json()
    assert len(tags) == 2
    tag_names = [t["tag_name"] for t in tags]
    assert "v1.0" in tag_names
    assert "v2.0" in tag_names


@pytest.mark.asyncio
async def test_create_tag_env_not_found(client: AsyncClient):
    token, _ = await setup_env(client, "alm17@test.com")
    resp = await client.post(
        f"/environments/{uuid.uuid4()}/tags",
        json={"tag_name": "v1.0"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_tags_env_not_found(client: AsyncClient):
    token, _ = await setup_env(client, "alm18@test.com")
    resp = await client.get(
        f"/environments/{uuid.uuid4()}/tags",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_tag_with_description(client: AsyncClient):
    token, model_id = await setup_env(client, "alm19@test.com")
    env = await create_alm_environment(client, token, model_id)
    resp = await client.post(
        f"/environments/{env['id']}/tags",
        json={"tag_name": "v1.0", "description": "First release"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    assert resp.json()["description"] == "First release"


# ---------------------------------------------------------------------------
# Promotions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_initiate_promotion(client: AsyncClient):
    token, model_id = await setup_env(client, "alm20@test.com")
    dev = await create_alm_environment(client, token, model_id, "dev", "Dev")
    prod = await create_alm_environment(client, token, model_id, "prod", "Prod")
    tag = await create_tag(client, token, dev["id"], "v1.0")
    resp = await client.post(
        f"/environments/{dev['id']}/promote",
        json={"target_env_id": prod["id"], "revision_tag_id": tag["id"]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    promo = resp.json()
    assert promo["status"] == "pending"
    assert promo["source_env_id"] == dev["id"]
    assert promo["target_env_id"] == prod["id"]


@pytest.mark.asyncio
async def test_complete_promotion(client: AsyncClient):
    token, model_id = await setup_env(client, "alm21@test.com")
    dev = await create_alm_environment(client, token, model_id, "dev", "Dev")
    prod = await create_alm_environment(client, token, model_id, "prod", "Prod")
    tag = await create_tag(client, token, dev["id"], "v1.0")
    promo_resp = await client.post(
        f"/environments/{dev['id']}/promote",
        json={"target_env_id": prod["id"], "revision_tag_id": tag["id"]},
        headers=auth_headers(token),
    )
    promo_id = promo_resp.json()["id"]
    resp = await client.post(
        f"/promotions/{promo_id}/complete",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
    assert resp.json()["completed_at"] is not None


@pytest.mark.asyncio
async def test_fail_promotion(client: AsyncClient):
    token, model_id = await setup_env(client, "alm22@test.com")
    dev = await create_alm_environment(client, token, model_id, "dev", "Dev")
    prod = await create_alm_environment(client, token, model_id, "prod", "Prod")
    tag = await create_tag(client, token, dev["id"], "v1.0")
    promo_resp = await client.post(
        f"/environments/{dev['id']}/promote",
        json={"target_env_id": prod["id"], "revision_tag_id": tag["id"]},
        headers=auth_headers(token),
    )
    promo_id = promo_resp.json()["id"]
    resp = await client.post(
        f"/promotions/{promo_id}/fail",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "failed"


@pytest.mark.asyncio
async def test_complete_already_completed(client: AsyncClient):
    token, model_id = await setup_env(client, "alm23@test.com")
    dev = await create_alm_environment(client, token, model_id, "dev", "Dev")
    prod = await create_alm_environment(client, token, model_id, "prod", "Prod")
    tag = await create_tag(client, token, dev["id"], "v1.0")
    promo_resp = await client.post(
        f"/environments/{dev['id']}/promote",
        json={"target_env_id": prod["id"], "revision_tag_id": tag["id"]},
        headers=auth_headers(token),
    )
    promo_id = promo_resp.json()["id"]
    await client.post(f"/promotions/{promo_id}/complete", headers=auth_headers(token))
    resp = await client.post(f"/promotions/{promo_id}/complete", headers=auth_headers(token))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_fail_already_failed(client: AsyncClient):
    token, model_id = await setup_env(client, "alm24@test.com")
    dev = await create_alm_environment(client, token, model_id, "dev", "Dev")
    prod = await create_alm_environment(client, token, model_id, "prod", "Prod")
    tag = await create_tag(client, token, dev["id"], "v1.0")
    promo_resp = await client.post(
        f"/environments/{dev['id']}/promote",
        json={"target_env_id": prod["id"], "revision_tag_id": tag["id"]},
        headers=auth_headers(token),
    )
    promo_id = promo_resp.json()["id"]
    await client.post(f"/promotions/{promo_id}/fail", headers=auth_headers(token))
    resp = await client.post(f"/promotions/{promo_id}/fail", headers=auth_headers(token))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_promotions(client: AsyncClient):
    token, model_id = await setup_env(client, "alm25@test.com")
    dev = await create_alm_environment(client, token, model_id, "dev", "Dev")
    prod = await create_alm_environment(client, token, model_id, "prod", "Prod")
    tag = await create_tag(client, token, dev["id"], "v1.0")
    await client.post(
        f"/environments/{dev['id']}/promote",
        json={"target_env_id": prod["id"], "revision_tag_id": tag["id"]},
        headers=auth_headers(token),
    )
    resp = await client.get(
        f"/environments/{dev['id']}/promotions",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_get_promotion_detail(client: AsyncClient):
    token, model_id = await setup_env(client, "alm26@test.com")
    dev = await create_alm_environment(client, token, model_id, "dev", "Dev")
    prod = await create_alm_environment(client, token, model_id, "prod", "Prod")
    tag = await create_tag(client, token, dev["id"], "v1.0")
    promo_resp = await client.post(
        f"/environments/{dev['id']}/promote",
        json={"target_env_id": prod["id"], "revision_tag_id": tag["id"]},
        headers=auth_headers(token),
    )
    promo_id = promo_resp.json()["id"]
    resp = await client.get(
        f"/promotions/{promo_id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == promo_id


@pytest.mark.asyncio
async def test_get_promotion_not_found(client: AsyncClient):
    token, _ = await setup_env(client, "alm27@test.com")
    resp = await client.get(
        f"/promotions/{uuid.uuid4()}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_promote_source_not_found(client: AsyncClient):
    token, _ = await setup_env(client, "alm28@test.com")
    resp = await client.post(
        f"/environments/{uuid.uuid4()}/promote",
        json={"target_env_id": str(uuid.uuid4()), "revision_tag_id": str(uuid.uuid4())},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_promote_target_not_found(client: AsyncClient):
    token, model_id = await setup_env(client, "alm29@test.com")
    dev = await create_alm_environment(client, token, model_id, "dev", "Dev")
    tag = await create_tag(client, token, dev["id"], "v1.0")
    resp = await client.post(
        f"/environments/{dev['id']}/promote",
        json={"target_env_id": str(uuid.uuid4()), "revision_tag_id": tag["id"]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_promote_tag_not_found(client: AsyncClient):
    token, model_id = await setup_env(client, "alm30@test.com")
    dev = await create_alm_environment(client, token, model_id, "dev", "Dev")
    prod = await create_alm_environment(client, token, model_id, "prod", "Prod")
    resp = await client.post(
        f"/environments/{dev['id']}/promote",
        json={"target_env_id": prod["id"], "revision_tag_id": str(uuid.uuid4())},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_promotion_with_change_summary(client: AsyncClient):
    token, model_id = await setup_env(client, "alm31@test.com")
    dev = await create_alm_environment(client, token, model_id, "dev", "Dev")
    prod = await create_alm_environment(client, token, model_id, "prod", "Prod")
    tag = await create_tag(client, token, dev["id"], "v1.0")
    resp = await client.post(
        f"/environments/{dev['id']}/promote",
        json={
            "target_env_id": prod["id"],
            "revision_tag_id": tag["id"],
            "change_summary": {"added_modules": 3},
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    assert resp.json()["change_summary"]["added_modules"] == 3


@pytest.mark.asyncio
async def test_list_promotions_env_not_found(client: AsyncClient):
    token, _ = await setup_env(client, "alm32@test.com")
    resp = await client.get(
        f"/environments/{uuid.uuid4()}/promotions",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_complete_promotion_not_found(client: AsyncClient):
    token, _ = await setup_env(client, "alm33@test.com")
    resp = await client.post(
        f"/promotions/{uuid.uuid4()}/complete",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_fail_promotion_not_found(client: AsyncClient):
    token, _ = await setup_env(client, "alm34@test.com")
    resp = await client.post(
        f"/promotions/{uuid.uuid4()}/fail",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# F066 Promotion runtime
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_initiate_promotion_includes_structural_diff(client: AsyncClient):
    token = await register_and_login(client, "alm43@test.com")
    source_ws = await create_workspace(client, token, "Source WS")
    target_ws = await create_workspace(client, token, "Target WS")
    source_model_id = await create_model(client, token, source_ws, "Source Model")
    target_model_id = await create_model(client, token, target_ws, "Target Model")

    source_dim = await create_dimension(client, token, source_model_id, "Products")
    await create_dimension_item(
        client, token, source_dim["id"], name="Widget A", code="WA"
    )
    source_module = await create_module(client, token, source_model_id, "Revenue")
    await create_line_item(
        client,
        token,
        source_module["id"],
        name="Sales",
        applies_to_dimensions=[source_dim["id"]],
        formula="1+1",
    )

    source_env = await create_alm_environment(client, token, source_model_id, "dev", "Dev")
    target_env = await create_alm_environment(client, token, target_model_id, "prod", "Prod")
    tag = await create_tag(client, token, source_env["id"], "v1.0")

    resp = await client.post(
        f"/environments/{source_env['id']}/promote",
        json={
            "target_env_id": target_env["id"],
            "revision_tag_id": tag["id"],
            "merge_strategy": "additive",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    summary = resp.json()["change_summary"]
    assert summary["structural_diff"]["has_changes"] is True
    assert summary["structural_diff"]["dimensions"]["counts"]["added"] >= 1
    assert summary["structural_diff"]["modules"]["counts"]["added"] >= 1
    assert summary["structural_diff"]["line_items"]["counts"]["added"] >= 1
    assert summary["conflicts"]["has_conflicts"] is False


@pytest.mark.asyncio
async def test_complete_promotion_additive_applies_structures_and_cells(client: AsyncClient):
    token = await register_and_login(client, "alm44@test.com")
    source_ws = await create_workspace(client, token, "Source WS")
    target_ws = await create_workspace(client, token, "Target WS")
    source_model_id = await create_model(client, token, source_ws, "Source Model")
    target_model_id = await create_model(client, token, target_ws, "Target Model")

    source_dim = await create_dimension(client, token, source_model_id, "Products")
    source_item = await create_dimension_item(
        client, token, source_dim["id"], name="Widget A", code="WA"
    )
    source_module = await create_module(client, token, source_model_id, "Revenue")
    source_sales = await create_line_item(
        client,
        token,
        source_module["id"],
        name="Sales",
        applies_to_dimensions=[source_dim["id"]],
    )
    await write_cell(
        client,
        token,
        line_item_id=source_sales["id"],
        dimension_members=[source_item["id"]],
        value=123.0,
    )

    target_module = await create_module(client, token, target_model_id, "Revenue")
    await create_line_item(client, token, target_module["id"], name="Keep Existing")

    source_env = await create_alm_environment(client, token, source_model_id, "dev", "Dev")
    target_env = await create_alm_environment(client, token, target_model_id, "prod", "Prod")
    tag = await create_tag(client, token, source_env["id"], "v1.0")

    promote_resp = await client.post(
        f"/environments/{source_env['id']}/promote",
        json={
            "target_env_id": target_env["id"],
            "revision_tag_id": tag["id"],
            "merge_strategy": "additive",
        },
        headers=auth_headers(token),
    )
    assert promote_resp.status_code == 201
    promo_id = promote_resp.json()["id"]

    complete_resp = await client.post(
        f"/promotions/{promo_id}/complete",
        headers=auth_headers(token),
    )
    assert complete_resp.status_code == 200
    assert complete_resp.json()["status"] == "completed"

    line_items_resp = await client.get(
        f"/modules/{target_module['id']}/line-items",
        headers=auth_headers(token),
    )
    assert line_items_resp.status_code == 200
    line_items = line_items_resp.json()
    line_item_names = {line_item["name"] for line_item in line_items}
    assert "Keep Existing" in line_item_names
    assert "Sales" in line_item_names
    sales_line_item_id = next(
        line_item["id"] for line_item in line_items if line_item["name"] == "Sales"
    )

    cells_resp = await client.get(
        f"/modules/{target_module['id']}/cells",
        headers=auth_headers(token),
    )
    assert cells_resp.status_code == 200
    sales_cells = [
        cell for cell in cells_resp.json() if cell["line_item_id"] == sales_line_item_id
    ]
    assert len(sales_cells) == 1
    assert sales_cells[0]["value"] == 123.0

    target_dims_resp = await client.get(
        f"/models/{target_model_id}/dimensions",
        headers=auth_headers(token),
    )
    assert target_dims_resp.status_code == 200
    target_dim_names = {dimension["name"] for dimension in target_dims_resp.json()}
    assert "Products" in target_dim_names


@pytest.mark.asyncio
async def test_complete_promotion_replace_overwrites_target_structure(client: AsyncClient):
    token = await register_and_login(client, "alm45@test.com")
    source_ws = await create_workspace(client, token, "Source WS")
    target_ws = await create_workspace(client, token, "Target WS")
    source_model_id = await create_model(client, token, source_ws, "Source Model")
    target_model_id = await create_model(client, token, target_ws, "Target Model")

    source_module = await create_module(client, token, source_model_id, "Forecast")
    await create_line_item(client, token, source_module["id"], name="Revenue")
    await create_module(client, token, target_model_id, "Legacy")

    source_env = await create_alm_environment(client, token, source_model_id, "dev", "Dev")
    target_env = await create_alm_environment(client, token, target_model_id, "prod", "Prod")
    tag = await create_tag(client, token, source_env["id"], "v1.0")

    promote_resp = await client.post(
        f"/environments/{source_env['id']}/promote",
        json={
            "target_env_id": target_env["id"],
            "revision_tag_id": tag["id"],
            "merge_strategy": "replace",
        },
        headers=auth_headers(token),
    )
    assert promote_resp.status_code == 201
    promo_id = promote_resp.json()["id"]

    complete_resp = await client.post(
        f"/promotions/{promo_id}/complete",
        headers=auth_headers(token),
    )
    assert complete_resp.status_code == 200
    assert complete_resp.json()["status"] == "completed"

    modules_resp = await client.get(
        f"/models/{target_model_id}/modules",
        headers=auth_headers(token),
    )
    assert modules_resp.status_code == 200
    module_names = {module["name"] for module in modules_resp.json()}
    assert "Forecast" in module_names
    assert "Legacy" not in module_names


@pytest.mark.asyncio
async def test_manual_promotion_blocks_when_target_has_conflicts(client: AsyncClient):
    token = await register_and_login(client, "alm46@test.com")
    source_ws = await create_workspace(client, token, "Source WS")
    target_ws = await create_workspace(client, token, "Target WS")
    source_model_id = await create_model(client, token, source_ws, "Source Model")
    target_model_id = await create_model(client, token, target_ws, "Target Model")

    source_module = await create_module(client, token, source_model_id, "Revenue")
    await create_line_item(client, token, source_module["id"], name="Sales")

    source_env = await create_alm_environment(client, token, source_model_id, "dev", "Dev")
    target_env = await create_alm_environment(client, token, target_model_id, "prod", "Prod")
    tag_v1 = await create_tag(client, token, source_env["id"], "v1.0")

    first_promote_resp = await client.post(
        f"/environments/{source_env['id']}/promote",
        json={
            "target_env_id": target_env["id"],
            "revision_tag_id": tag_v1["id"],
            "merge_strategy": "replace",
        },
        headers=auth_headers(token),
    )
    assert first_promote_resp.status_code == 201
    first_promo_id = first_promote_resp.json()["id"]

    first_complete_resp = await client.post(
        f"/promotions/{first_promo_id}/complete",
        headers=auth_headers(token),
    )
    assert first_complete_resp.status_code == 200
    assert first_complete_resp.json()["status"] == "completed"

    await create_module(client, token, target_model_id, "Target Hotfix")
    tag_v2 = await create_tag(client, token, source_env["id"], "v2.0")

    second_promote_resp = await client.post(
        f"/environments/{source_env['id']}/promote",
        json={
            "target_env_id": target_env["id"],
            "revision_tag_id": tag_v2["id"],
            "merge_strategy": "manual",
        },
        headers=auth_headers(token),
    )
    assert second_promote_resp.status_code == 201
    second_promo = second_promote_resp.json()
    assert second_promo["change_summary"]["conflicts"]["has_conflicts"] is True

    blocked_complete_resp = await client.post(
        f"/promotions/{second_promo['id']}/complete",
        headers=auth_headers(token),
    )
    assert blocked_complete_resp.status_code == 400

    promotion_detail_resp = await client.get(
        f"/promotions/{second_promo['id']}",
        headers=auth_headers(token),
    )
    assert promotion_detail_resp.status_code == 200
    assert promotion_detail_resp.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_promotion_rollback_restores_target_on_failure(client: AsyncClient):
    token = await register_and_login(client, "alm47@test.com")
    source_ws = await create_workspace(client, token, "Source WS")
    target_ws = await create_workspace(client, token, "Target WS")
    source_model_id = await create_model(client, token, source_ws, "Source Model")
    target_model_id = await create_model(client, token, target_ws, "Target Model")

    await create_module(client, token, target_model_id, "Stable")

    source_env = await create_alm_environment(client, token, source_model_id, "dev", "Dev")
    target_env = await create_alm_environment(client, token, target_model_id, "prod", "Prod")
    broken_tag = await create_tag(
        client,
        token,
        source_env["id"],
        "broken",
        snapshot_data={
            "dimensions": [
                {
                    "id": str(uuid.uuid4()),
                    "name": "Broken Dimension",
                    "dimension_type": "invalid_dimension_type",
                    "max_items": None,
                }
            ],
            "dimension_items": [],
            "modules": [],
            "line_items": [],
            "cell_values": [],
        },
    )

    promote_resp = await client.post(
        f"/environments/{source_env['id']}/promote",
        json={
            "target_env_id": target_env["id"],
            "revision_tag_id": broken_tag["id"],
            "merge_strategy": "replace",
        },
        headers=auth_headers(token),
    )
    assert promote_resp.status_code == 201
    promo_id = promote_resp.json()["id"]

    complete_resp = await client.post(
        f"/promotions/{promo_id}/complete",
        headers=auth_headers(token),
    )
    assert complete_resp.status_code == 200
    complete_data = complete_resp.json()
    assert complete_data["status"] == "rolled_back"
    assert complete_data["change_summary"]["rollback"]["performed"] is True

    target_modules_resp = await client.get(
        f"/models/{target_model_id}/modules",
        headers=auth_headers(token),
    )
    assert target_modules_resp.status_code == 200
    module_names = [module["name"] for module in target_modules_resp.json()]
    assert module_names == ["Stable"]


# ---------------------------------------------------------------------------
# Tag comparison
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compare_tags_added(client: AsyncClient):
    token, model_id = await setup_env(client, "alm35@test.com")
    env = await create_alm_environment(client, token, model_id)
    tag1 = await create_tag(client, token, env["id"], "v1.0", {"modules": ["A"]})
    tag2 = await create_tag(client, token, env["id"], "v2.0", {"modules": ["A"], "lists": ["L1"]})
    resp = await client.get(
        f"/tags/{tag1['id']}/compare/{tag2['id']}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "lists" in data["added"]
    assert len(data["removed"]) == 0


@pytest.mark.asyncio
async def test_compare_tags_removed(client: AsyncClient):
    token, model_id = await setup_env(client, "alm36@test.com")
    env = await create_alm_environment(client, token, model_id)
    tag1 = await create_tag(client, token, env["id"], "v1.0", {"modules": ["A"], "extra": "x"})
    tag2 = await create_tag(client, token, env["id"], "v2.0", {"modules": ["A"]})
    resp = await client.get(
        f"/tags/{tag1['id']}/compare/{tag2['id']}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "extra" in data["removed"]


@pytest.mark.asyncio
async def test_compare_tags_modified(client: AsyncClient):
    token, model_id = await setup_env(client, "alm37@test.com")
    env = await create_alm_environment(client, token, model_id)
    tag1 = await create_tag(client, token, env["id"], "v1.0", {"modules": ["A"]})
    tag2 = await create_tag(client, token, env["id"], "v2.0", {"modules": ["A", "B"]})
    resp = await client.get(
        f"/tags/{tag1['id']}/compare/{tag2['id']}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "modules" in data["modified"]


@pytest.mark.asyncio
async def test_compare_tags_not_found_first(client: AsyncClient):
    token, model_id = await setup_env(client, "alm38@test.com")
    env = await create_alm_environment(client, token, model_id)
    tag2 = await create_tag(client, token, env["id"], "v2.0")
    resp = await client.get(
        f"/tags/{uuid.uuid4()}/compare/{tag2['id']}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_compare_tags_not_found_second(client: AsyncClient):
    token, model_id = await setup_env(client, "alm39@test.com")
    env = await create_alm_environment(client, token, model_id)
    tag1 = await create_tag(client, token, env["id"], "v1.0")
    resp = await client.get(
        f"/tags/{tag1['id']}/compare/{uuid.uuid4()}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_compare_identical_tags(client: AsyncClient):
    token, model_id = await setup_env(client, "alm40@test.com")
    env = await create_alm_environment(client, token, model_id)
    tag1 = await create_tag(client, token, env["id"], "v1.0", {"modules": ["A"]})
    tag2 = await create_tag(client, token, env["id"], "v2.0", {"modules": ["A"]})
    resp = await client.get(
        f"/tags/{tag1['id']}/compare/{tag2['id']}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["added"] == {}
    assert data["removed"] == {}
    assert data["modified"] == {}


# ---------------------------------------------------------------------------
# Auth required
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_env_no_auth(client: AsyncClient):
    token, model_id = await setup_env(client, "alm41@test.com")
    resp = await client.post(
        f"/models/{model_id}/environments",
        json={"env_type": "dev", "name": "Dev"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_env_no_auth(client: AsyncClient):
    token, model_id = await setup_env(client, "alm42@test.com")
    resp = await client.get(f"/models/{model_id}/environments")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_env_no_auth(client: AsyncClient):
    resp = await client.get(f"/environments/{uuid.uuid4()}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_tag_no_auth(client: AsyncClient):
    resp = await client.post(
        f"/environments/{uuid.uuid4()}/tags",
        json={"tag_name": "v1"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_promote_no_auth(client: AsyncClient):
    resp = await client.post(
        f"/environments/{uuid.uuid4()}/promote",
        json={"target_env_id": str(uuid.uuid4()), "revision_tag_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_compare_no_auth(client: AsyncClient):
    resp = await client.get(f"/tags/{uuid.uuid4()}/compare/{uuid.uuid4()}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_lock_no_auth(client: AsyncClient):
    resp = await client.put(
        f"/environments/{uuid.uuid4()}/lock",
        json={"is_locked": True},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_promotion_no_auth(client: AsyncClient):
    resp = await client.get(f"/promotions/{uuid.uuid4()}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_complete_promotion_no_auth(client: AsyncClient):
    resp = await client.post(f"/promotions/{uuid.uuid4()}/complete")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_fail_promotion_no_auth(client: AsyncClient):
    resp = await client.post(f"/promotions/{uuid.uuid4()}/fail")
    assert resp.status_code == 401
