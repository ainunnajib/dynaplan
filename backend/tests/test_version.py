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


async def create_version(
    client: AsyncClient,
    token: str,
    model_id: str,
    name: str = "Version 1",
    version_type: str = "forecast",
    is_default: bool = False,
    switchover_period: Optional[str] = None,
) -> dict:
    payload = {
        "name": name,
        "version_type": version_type,
        "is_default": is_default,
    }
    if switchover_period is not None:
        payload["switchover_period"] = switchover_period
    resp = await client.post(
        f"/models/{model_id}/versions",
        json=payload,
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def setup_model(client: AsyncClient, email: str) -> tuple:
    """Register user, create workspace + model. Returns (token, model_id)."""
    token = await register_and_login(client, email)
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    return token, model_id


# ---------------------------------------------------------------------------
# Create version
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_version_basic(client: AsyncClient):
    token, model_id = await setup_model(client, "v_create@example.com")

    resp = await client.post(
        f"/models/{model_id}/versions",
        json={"name": "Actuals 2024", "version_type": "actuals"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Actuals 2024"
    assert data["version_type"] == "actuals"
    assert data["model_id"] == model_id
    assert data["is_default"] is False
    assert data["switchover_period"] is None
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_version_all_types(client: AsyncClient):
    token, model_id = await setup_model(client, "v_types@example.com")

    for vtype in ("actuals", "forecast", "budget", "scenario"):
        resp = await client.post(
            f"/models/{model_id}/versions",
            json={"name": f"Version {vtype}", "version_type": vtype},
            headers=auth_headers(token),
        )
        assert resp.status_code == 201, f"Failed for type {vtype}: {resp.text}"
        assert resp.json()["version_type"] == vtype


@pytest.mark.asyncio
async def test_create_version_with_switchover(client: AsyncClient):
    token, model_id = await setup_model(client, "v_switchover@example.com")

    resp = await client.post(
        f"/models/{model_id}/versions",
        json={
            "name": "Rolling Forecast",
            "version_type": "forecast",
            "switchover_period": "2024-03",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    assert resp.json()["switchover_period"] == "2024-03"


@pytest.mark.asyncio
async def test_create_version_as_default(client: AsyncClient):
    token, model_id = await setup_model(client, "v_default_create@example.com")

    resp = await client.post(
        f"/models/{model_id}/versions",
        json={"name": "Budget 2024", "version_type": "budget", "is_default": True},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    assert resp.json()["is_default"] is True


@pytest.mark.asyncio
async def test_create_version_requires_auth(client: AsyncClient):
    token, model_id = await setup_model(client, "v_auth@example.com")

    resp = await client.post(
        f"/models/{model_id}/versions",
        json={"name": "No Auth"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# List versions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_versions_empty(client: AsyncClient):
    token, model_id = await setup_model(client, "v_list_empty@example.com")

    resp = await client.get(f"/models/{model_id}/versions", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_versions_multiple(client: AsyncClient):
    token, model_id = await setup_model(client, "v_list_many@example.com")

    await create_version(client, token, model_id, name="Actuals", version_type="actuals")
    await create_version(client, token, model_id, name="Forecast", version_type="forecast")
    await create_version(client, token, model_id, name="Budget", version_type="budget")

    resp = await client.get(f"/models/{model_id}/versions", headers=auth_headers(token))
    assert resp.status_code == 200
    names = [v["name"] for v in resp.json()]
    assert "Actuals" in names
    assert "Forecast" in names
    assert "Budget" in names


@pytest.mark.asyncio
async def test_list_versions_requires_auth(client: AsyncClient):
    token, model_id = await setup_model(client, "v_list_auth@example.com")

    resp = await client.get(f"/models/{model_id}/versions")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Get single version
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_version(client: AsyncClient):
    token, model_id = await setup_model(client, "v_get@example.com")
    created = await create_version(client, token, model_id, name="Get Me")

    resp = await client.get(f"/versions/{created['id']}", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["name"] == "Get Me"
    assert resp.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_get_version_not_found(client: AsyncClient):
    token, _ = await setup_model(client, "v_get_404@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.get(f"/versions/{fake_id}", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_version_requires_auth(client: AsyncClient):
    token, model_id = await setup_model(client, "v_get_auth@example.com")
    created = await create_version(client, token, model_id, name="Auth Test")

    resp = await client.get(f"/versions/{created['id']}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Update version
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_version_name(client: AsyncClient):
    token, model_id = await setup_model(client, "v_update@example.com")
    created = await create_version(client, token, model_id, name="Old Name")

    resp = await client.patch(
        f"/versions/{created['id']}",
        json={"name": "New Name"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_update_version_type(client: AsyncClient):
    token, model_id = await setup_model(client, "v_update_type@example.com")
    created = await create_version(client, token, model_id, name="Type Change", version_type="forecast")

    resp = await client.patch(
        f"/versions/{created['id']}",
        json={"version_type": "actuals"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["version_type"] == "actuals"


@pytest.mark.asyncio
async def test_update_version_switchover_period(client: AsyncClient):
    token, model_id = await setup_model(client, "v_update_switch@example.com")
    created = await create_version(client, token, model_id, name="Rolling")

    resp = await client.patch(
        f"/versions/{created['id']}",
        json={"switchover_period": "2024-06"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["switchover_period"] == "2024-06"


@pytest.mark.asyncio
async def test_update_version_requires_auth(client: AsyncClient):
    token, model_id = await setup_model(client, "v_update_auth@example.com")
    created = await create_version(client, token, model_id, name="Update Auth")

    resp = await client.patch(f"/versions/{created['id']}", json={"name": "Fail"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Delete version
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_version(client: AsyncClient):
    token, model_id = await setup_model(client, "v_delete@example.com")
    created = await create_version(client, token, model_id, name="Delete Me")

    del_resp = await client.delete(f"/versions/{created['id']}", headers=auth_headers(token))
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/versions/{created['id']}", headers=auth_headers(token))
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_version_not_found(client: AsyncClient):
    token, _ = await setup_model(client, "v_delete_404@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.delete(f"/versions/{fake_id}", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_version_requires_auth(client: AsyncClient):
    token, model_id = await setup_model(client, "v_delete_auth@example.com")
    created = await create_version(client, token, model_id, name="Delete Auth")

    resp = await client.delete(f"/versions/{created['id']}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Unique name per model
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_duplicate_name_same_model_rejected(client: AsyncClient):
    token, model_id = await setup_model(client, "v_unique@example.com")

    await create_version(client, token, model_id, name="Duplicate Name")

    resp = await client.post(
        f"/models/{model_id}/versions",
        json={"name": "Duplicate Name", "version_type": "budget"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_same_name_different_models_allowed(client: AsyncClient):
    token, model_id_1 = await setup_model(client, "v_same_name_1@example.com")
    ws_id = await create_workspace(
        client,
        token,
        name="WS2",
    )
    model_id_2 = await create_model(client, token, ws_id, name="Model 2")

    await create_version(client, token, model_id_1, name="Shared Name")
    resp = await client.post(
        f"/models/{model_id_2}/versions",
        json={"name": "Shared Name", "version_type": "actuals"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Set default version
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_default_version(client: AsyncClient):
    token, model_id = await setup_model(client, "v_set_default@example.com")
    v = await create_version(client, token, model_id, name="Make Default")

    resp = await client.post(
        f"/versions/{v['id']}/set-default",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["is_default"] is True
    assert resp.json()["id"] == v["id"]


@pytest.mark.asyncio
async def test_only_one_default_per_model(client: AsyncClient):
    token, model_id = await setup_model(client, "v_one_default@example.com")

    v1 = await create_version(client, token, model_id, name="First", is_default=True)
    v2 = await create_version(client, token, model_id, name="Second")

    # Set second as default
    resp = await client.post(
        f"/versions/{v2['id']}/set-default",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["is_default"] is True

    # First should no longer be default
    get_v1 = await client.get(f"/versions/{v1['id']}", headers=auth_headers(token))
    assert get_v1.status_code == 200
    assert get_v1.json()["is_default"] is False


@pytest.mark.asyncio
async def test_set_default_not_found(client: AsyncClient):
    token, _ = await setup_model(client, "v_default_404@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.post(f"/versions/{fake_id}/set-default", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_set_default_requires_auth(client: AsyncClient):
    token, model_id = await setup_model(client, "v_default_auth@example.com")
    v = await create_version(client, token, model_id, name="Auth Default")

    resp = await client.post(f"/versions/{v['id']}/set-default")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_creating_with_is_default_true_unsets_previous(client: AsyncClient):
    token, model_id = await setup_model(client, "v_create_default@example.com")

    v1 = await create_version(client, token, model_id, name="First Default", is_default=True)
    assert v1["is_default"] is True

    v2 = await create_version(client, token, model_id, name="Second Default", is_default=True)
    assert v2["is_default"] is True

    # First must be unset
    get_v1 = await client.get(f"/versions/{v1['id']}", headers=auth_headers(token))
    assert get_v1.json()["is_default"] is False


# ---------------------------------------------------------------------------
# Compare versions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compare_versions_no_cells(client: AsyncClient):
    """Compare two versions when there are no cells: expect empty cells list."""
    token, model_id = await setup_model(client, "v_compare_empty@example.com")

    v_a = await create_version(client, token, model_id, name="Version A")
    v_b = await create_version(client, token, model_id, name="Version B")

    # Create a module and line item to get a real line_item_id
    module_resp = await client.post(
        f"/models/{model_id}/modules",
        json={"name": "Revenue"},
        headers=auth_headers(token),
    )
    assert module_resp.status_code == 201
    module_id = module_resp.json()["id"]

    li_resp = await client.post(
        f"/modules/{module_id}/line-items",
        json={"name": "Revenue Item", "format": "number"},
        headers=auth_headers(token),
    )
    assert li_resp.status_code == 201
    line_item_id = li_resp.json()["id"]

    resp = await client.post(
        "/versions/compare",
        json={
            "version_id_a": v_a["id"],
            "version_id_b": v_b["id"],
            "line_item_id": line_item_id,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["version_id_a"] == v_a["id"]
    assert data["version_id_b"] == v_b["id"]
    assert data["version_name_a"] == "Version A"
    assert data["version_name_b"] == "Version B"
    assert data["line_item_id"] == line_item_id
    assert data["cells"] == []


@pytest.mark.asyncio
async def test_compare_versions_not_found(client: AsyncClient):
    token, model_id = await setup_model(client, "v_compare_404@example.com")

    fake_a = str(uuid.uuid4())
    fake_b = str(uuid.uuid4())
    fake_li = str(uuid.uuid4())

    resp = await client.post(
        "/versions/compare",
        json={
            "version_id_a": fake_a,
            "version_id_b": fake_b,
            "line_item_id": fake_li,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_compare_versions_requires_auth(client: AsyncClient):
    token, model_id = await setup_model(client, "v_compare_auth@example.com")

    v_a = await create_version(client, token, model_id, name="VA")
    v_b = await create_version(client, token, model_id, name="VB")

    resp = await client.post(
        "/versions/compare",
        json={
            "version_id_a": v_a["id"],
            "version_id_b": v_b["id"],
            "line_item_id": str(uuid.uuid4()),
        },
    )
    assert resp.status_code == 401
