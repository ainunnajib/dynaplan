"""Tests for F027 — What-if analysis."""

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
) -> dict:
    resp = await client.post(
        f"/models/{model_id}/versions",
        json={"name": name, "version_type": version_type},
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


async def create_scenario(
    client: AsyncClient,
    token: str,
    model_id: str,
    name: str = "Test Scenario",
    description: Optional[str] = None,
    base_version_id: Optional[str] = None,
) -> dict:
    payload: dict = {"name": name}
    if description is not None:
        payload["description"] = description
    if base_version_id is not None:
        payload["base_version_id"] = base_version_id
    resp = await client.post(
        f"/models/{model_id}/scenarios",
        json=payload,
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def add_assumption(
    client: AsyncClient,
    token: str,
    scenario_id: str,
    line_item_id: str,
    dimension_key: str,
    modified_value: str,
    note: Optional[str] = None,
) -> dict:
    payload: dict = {
        "line_item_id": line_item_id,
        "dimension_key": dimension_key,
        "modified_value": modified_value,
    }
    if note is not None:
        payload["note"] = note
    resp = await client.post(
        f"/scenarios/{scenario_id}/assumptions",
        json=payload,
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Scenario CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_scenario_basic(client: AsyncClient):
    token, model_id = await setup_model(client, "wi_create@example.com")

    resp = await client.post(
        f"/models/{model_id}/scenarios",
        json={"name": "My What-if"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My What-if"
    assert data["model_id"] == model_id
    assert data["is_active"] is True
    assert data["assumption_count"] == 0
    assert data["description"] is None
    assert data["base_version_id"] is None
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_scenario_with_description_and_base_version(client: AsyncClient):
    token, model_id = await setup_model(client, "wi_create_full@example.com")
    version = await create_version(client, token, model_id, name="Base Version")

    resp = await client.post(
        f"/models/{model_id}/scenarios",
        json={
            "name": "Revenue Downside",
            "description": "10% revenue reduction",
            "base_version_id": version["id"],
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Revenue Downside"
    assert data["description"] == "10% revenue reduction"
    assert data["base_version_id"] == version["id"]


@pytest.mark.asyncio
async def test_create_scenario_requires_auth(client: AsyncClient):
    token, model_id = await setup_model(client, "wi_create_auth@example.com")

    resp = await client.post(
        f"/models/{model_id}/scenarios",
        json={"name": "No Auth"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_scenarios_empty(client: AsyncClient):
    token, model_id = await setup_model(client, "wi_list_empty@example.com")

    resp = await client.get(f"/models/{model_id}/scenarios", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_scenarios_multiple(client: AsyncClient):
    token, model_id = await setup_model(client, "wi_list_many@example.com")

    await create_scenario(client, token, model_id, name="Upside Case")
    await create_scenario(client, token, model_id, name="Downside Case")

    resp = await client.get(f"/models/{model_id}/scenarios", headers=auth_headers(token))
    assert resp.status_code == 200
    names = [s["name"] for s in resp.json()]
    assert "Upside Case" in names
    assert "Downside Case" in names


@pytest.mark.asyncio
async def test_list_scenarios_requires_auth(client: AsyncClient):
    token, model_id = await setup_model(client, "wi_list_auth@example.com")

    resp = await client.get(f"/models/{model_id}/scenarios")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_scenario(client: AsyncClient):
    token, model_id = await setup_model(client, "wi_get@example.com")
    created = await create_scenario(client, token, model_id, name="Get Me")

    resp = await client.get(f"/scenarios/{created['id']}", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["name"] == "Get Me"
    assert resp.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_get_scenario_not_found(client: AsyncClient):
    token, _ = await setup_model(client, "wi_get_404@example.com")

    resp = await client.get(f"/scenarios/{uuid.uuid4()}", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_scenario_requires_auth(client: AsyncClient):
    token, model_id = await setup_model(client, "wi_get_auth@example.com")
    created = await create_scenario(client, token, model_id)

    resp = await client.get(f"/scenarios/{created['id']}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_scenario_soft_delete(client: AsyncClient):
    token, model_id = await setup_model(client, "wi_delete@example.com")
    created = await create_scenario(client, token, model_id, name="Delete Me")

    del_resp = await client.delete(f"/scenarios/{created['id']}", headers=auth_headers(token))
    assert del_resp.status_code == 204

    # Soft deleted — get still returns 200 but is_active is False
    get_resp = await client.get(f"/scenarios/{created['id']}", headers=auth_headers(token))
    assert get_resp.status_code == 200
    assert get_resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_delete_scenario_not_in_list(client: AsyncClient):
    """After soft delete, scenario no longer appears in list."""
    token, model_id = await setup_model(client, "wi_delete_list@example.com")
    created = await create_scenario(client, token, model_id, name="Invisible")

    await client.delete(f"/scenarios/{created['id']}", headers=auth_headers(token))

    list_resp = await client.get(f"/models/{model_id}/scenarios", headers=auth_headers(token))
    assert list_resp.status_code == 200
    ids = [s["id"] for s in list_resp.json()]
    assert created["id"] not in ids


@pytest.mark.asyncio
async def test_delete_scenario_not_found(client: AsyncClient):
    token, _ = await setup_model(client, "wi_delete_404@example.com")

    resp = await client.delete(f"/scenarios/{uuid.uuid4()}", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_scenario_requires_auth(client: AsyncClient):
    token, model_id = await setup_model(client, "wi_delete_auth@example.com")
    created = await create_scenario(client, token, model_id)

    resp = await client.delete(f"/scenarios/{created['id']}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Assumption CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_assumption(client: AsyncClient):
    token, model_id = await setup_model(client, "wi_assume@example.com")
    scenario = await create_scenario(client, token, model_id)
    line_item_id = str(uuid.uuid4())
    dim_key = "dim1|dim2"

    resp = await client.post(
        f"/scenarios/{scenario['id']}/assumptions",
        json={
            "line_item_id": line_item_id,
            "dimension_key": dim_key,
            "modified_value": "500.0",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["scenario_id"] == scenario["id"]
    assert data["line_item_id"] == line_item_id
    assert data["dimension_key"] == dim_key
    assert data["modified_value"] == "500.0"
    assert "id" in data


@pytest.mark.asyncio
async def test_add_assumption_with_note(client: AsyncClient):
    token, model_id = await setup_model(client, "wi_assume_note@example.com")
    scenario = await create_scenario(client, token, model_id)

    resp = await client.post(
        f"/scenarios/{scenario['id']}/assumptions",
        json={
            "line_item_id": str(uuid.uuid4()),
            "dimension_key": "key1",
            "modified_value": "100",
            "note": "Market downturn assumption",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    assert resp.json()["note"] == "Market downturn assumption"


@pytest.mark.asyncio
async def test_add_assumption_requires_auth(client: AsyncClient):
    token, model_id = await setup_model(client, "wi_assume_auth@example.com")
    scenario = await create_scenario(client, token, model_id)

    resp = await client.post(
        f"/scenarios/{scenario['id']}/assumptions",
        json={
            "line_item_id": str(uuid.uuid4()),
            "dimension_key": "key1",
            "modified_value": "100",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_add_assumption_scenario_not_found(client: AsyncClient):
    token, _ = await setup_model(client, "wi_assume_404@example.com")

    resp = await client.post(
        f"/scenarios/{uuid.uuid4()}/assumptions",
        json={
            "line_item_id": str(uuid.uuid4()),
            "dimension_key": "key1",
            "modified_value": "100",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_assumptions(client: AsyncClient):
    token, model_id = await setup_model(client, "wi_list_assume@example.com")
    scenario = await create_scenario(client, token, model_id)

    li1 = str(uuid.uuid4())
    li2 = str(uuid.uuid4())
    await add_assumption(client, token, scenario["id"], li1, "k1", "10")
    await add_assumption(client, token, scenario["id"], li2, "k2", "20")

    resp = await client.get(
        f"/scenarios/{scenario['id']}/assumptions",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_list_assumptions_empty(client: AsyncClient):
    token, model_id = await setup_model(client, "wi_list_assume_empty@example.com")
    scenario = await create_scenario(client, token, model_id)

    resp = await client.get(
        f"/scenarios/{scenario['id']}/assumptions",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_assumptions_requires_auth(client: AsyncClient):
    token, model_id = await setup_model(client, "wi_list_assume_auth@example.com")
    scenario = await create_scenario(client, token, model_id)

    resp = await client.get(f"/scenarios/{scenario['id']}/assumptions")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_remove_assumption(client: AsyncClient):
    token, model_id = await setup_model(client, "wi_remove_assume@example.com")
    scenario = await create_scenario(client, token, model_id)
    assumption = await add_assumption(
        client, token, scenario["id"], str(uuid.uuid4()), "k1", "99"
    )

    del_resp = await client.delete(
        f"/assumptions/{assumption['id']}",
        headers=auth_headers(token),
    )
    assert del_resp.status_code == 204

    # Verify gone from list
    list_resp = await client.get(
        f"/scenarios/{scenario['id']}/assumptions",
        headers=auth_headers(token),
    )
    assert list_resp.status_code == 200
    assert list_resp.json() == []


@pytest.mark.asyncio
async def test_remove_assumption_not_found(client: AsyncClient):
    token, _ = await setup_model(client, "wi_remove_assume_404@example.com")

    resp = await client.delete(
        f"/assumptions/{uuid.uuid4()}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_remove_assumption_requires_auth(client: AsyncClient):
    token, model_id = await setup_model(client, "wi_remove_assume_auth@example.com")
    scenario = await create_scenario(client, token, model_id)
    assumption = await add_assumption(
        client, token, scenario["id"], str(uuid.uuid4()), "k1", "99"
    )

    resp = await client.delete(f"/assumptions/{assumption['id']}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_multiple_assumptions_on_same_scenario(client: AsyncClient):
    token, model_id = await setup_model(client, "wi_multi_assume@example.com")
    scenario = await create_scenario(client, token, model_id)

    line_items = [str(uuid.uuid4()) for _ in range(5)]
    for i, li in enumerate(line_items):
        await add_assumption(client, token, scenario["id"], li, f"key{i}", str(i * 10))

    resp = await client.get(
        f"/scenarios/{scenario['id']}/assumptions",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 5

    # Check assumption_count in scenario response
    get_resp = await client.get(f"/scenarios/{scenario['id']}", headers=auth_headers(token))
    assert get_resp.json()["assumption_count"] == 5


# ---------------------------------------------------------------------------
# Evaluate scenario
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_evaluate_scenario_no_assumptions(client: AsyncClient):
    """Scenario with no assumptions and no base version returns empty cells."""
    token, model_id = await setup_model(client, "wi_eval_empty@example.com")
    scenario = await create_scenario(client, token, model_id)

    resp = await client.get(
        f"/scenarios/{scenario['id']}/evaluate",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["scenario_id"] == scenario["id"]
    assert data["cells"] == []


@pytest.mark.asyncio
async def test_evaluate_scenario_with_assumptions_no_base(client: AsyncClient):
    """Without a base version, evaluate returns only the assumption cells marked as modified."""
    token, model_id = await setup_model(client, "wi_eval_nobase@example.com")
    scenario = await create_scenario(client, token, model_id)

    li1 = str(uuid.uuid4())
    li2 = str(uuid.uuid4())
    await add_assumption(client, token, scenario["id"], li1, "k1", "100")
    await add_assumption(client, token, scenario["id"], li2, "k2", "200")

    resp = await client.get(
        f"/scenarios/{scenario['id']}/evaluate",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["cells"]) == 2
    for cell in data["cells"]:
        assert cell["is_modified"] is True


@pytest.mark.asyncio
async def test_evaluate_scenario_not_found(client: AsyncClient):
    token, _ = await setup_model(client, "wi_eval_404@example.com")

    resp = await client.get(
        f"/scenarios/{uuid.uuid4()}/evaluate",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_evaluate_scenario_requires_auth(client: AsyncClient):
    token, model_id = await setup_model(client, "wi_eval_auth@example.com")
    scenario = await create_scenario(client, token, model_id)

    resp = await client.get(f"/scenarios/{scenario['id']}/evaluate")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Compare to base
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compare_to_base_no_assumptions(client: AsyncClient):
    token, model_id = await setup_model(client, "wi_compare_empty@example.com")
    version = await create_version(client, token, model_id)
    scenario = await create_scenario(
        client, token, model_id, base_version_id=version["id"]
    )

    resp = await client.get(
        f"/scenarios/{scenario['id']}/compare",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["scenario_id"] == scenario["id"]
    assert data["diffs"] == []


@pytest.mark.asyncio
async def test_compare_to_base_shows_diffs(client: AsyncClient):
    token, model_id = await setup_model(client, "wi_compare_diffs@example.com")
    version = await create_version(client, token, model_id)
    scenario = await create_scenario(
        client, token, model_id, base_version_id=version["id"]
    )

    li = str(uuid.uuid4())
    await add_assumption(client, token, scenario["id"], li, "k1", "999")

    resp = await client.get(
        f"/scenarios/{scenario['id']}/compare",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["diffs"]) == 1
    diff = data["diffs"][0]
    assert diff["line_item_id"] == li
    assert diff["dimension_key"] == "k1"
    assert diff["modified_value"] == "999"


@pytest.mark.asyncio
async def test_compare_requires_auth(client: AsyncClient):
    token, model_id = await setup_model(client, "wi_compare_auth@example.com")
    scenario = await create_scenario(client, token, model_id)

    resp = await client.get(f"/scenarios/{scenario['id']}/compare")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_compare_not_found(client: AsyncClient):
    token, _ = await setup_model(client, "wi_compare_404@example.com")

    resp = await client.get(
        f"/scenarios/{uuid.uuid4()}/compare",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Promote scenario
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_promote_scenario(client: AsyncClient):
    """Promote writes assumptions into target version cells."""
    token, model_id = await setup_model(client, "wi_promote@example.com")
    base_ver = await create_version(client, token, model_id, name="Base")
    target_ver = await create_version(client, token, model_id, name="Target")
    scenario = await create_scenario(
        client, token, model_id, base_version_id=base_ver["id"]
    )

    li = str(uuid.uuid4())
    # dimension_key contains the base version id to simulate a real cell key
    dim_key = f"{base_ver['id']}|dim_item_1"
    await add_assumption(client, token, scenario["id"], li, dim_key, "42.0")

    resp = await client.post(
        f"/scenarios/{scenario['id']}/promote",
        params={"target_version_id": target_ver["id"]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["promoted_cells"] == 1


@pytest.mark.asyncio
async def test_promote_scenario_not_found(client: AsyncClient):
    token, model_id = await setup_model(client, "wi_promote_404@example.com")
    target_ver = await create_version(client, token, model_id, name="Target")

    resp = await client.post(
        f"/scenarios/{uuid.uuid4()}/promote",
        params={"target_version_id": target_ver["id"]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_promote_scenario_requires_auth(client: AsyncClient):
    token, model_id = await setup_model(client, "wi_promote_auth@example.com")
    scenario = await create_scenario(client, token, model_id)
    target_ver = await create_version(client, token, model_id, name="Target")

    resp = await client.post(
        f"/scenarios/{scenario['id']}/promote",
        params={"target_version_id": target_ver["id"]},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_promote_no_assumptions_returns_zero(client: AsyncClient):
    token, model_id = await setup_model(client, "wi_promote_zero@example.com")
    scenario = await create_scenario(client, token, model_id)
    target_ver = await create_version(client, token, model_id, name="Target")

    resp = await client.post(
        f"/scenarios/{scenario['id']}/promote",
        params={"target_version_id": target_ver["id"]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["promoted_cells"] == 0
