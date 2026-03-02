import uuid
from typing import Dict

import pytest
from httpx import AsyncClient

from app.services.horizontal_scaling import reset_horizontal_scaling_runtime_state


@pytest.fixture(autouse=True)
def reset_scaling_runtime():
    reset_horizontal_scaling_runtime_state()
    yield
    reset_horizontal_scaling_runtime_state()


async def register_and_login(
    client: AsyncClient,
    email: str,
    password: str = "testpass123",
) -> str:
    await client.post(
        "/auth/register",
        json={
            "email": email,
            "full_name": "Scaling Test User",
            "password": password,
        },
    )
    login_resp = await client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200, login_resp.text
    return login_resp.json()["access_token"]


def auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": "Bearer %s" % token}


async def create_workspace(
    client: AsyncClient,
    token: str,
    name: str = "Scaling Workspace",
) -> str:
    resp = await client.post(
        "/workspaces/",
        json={"name": name},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def create_model(
    client: AsyncClient,
    token: str,
    workspace_id: str,
    name: str = "Scaling Model",
) -> str:
    resp = await client.post(
        "/models",
        json={"name": name, "workspace_id": workspace_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_scaling_status_requires_auth(client: AsyncClient):
    response = await client.get("/observability/scaling/status")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_scaling_status_returns_runtime_metadata(client: AsyncClient):
    token = await register_and_login(client, "f077_status@example.com")

    response = await client.get(
        "/observability/scaling/status",
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["api_mode"] == "stateless"
    assert payload["state_backend"] in ("memory", "redis")
    assert payload["load_balancer_strategy"] != ""
    assert isinstance(payload["redis_configured"], bool)


@pytest.mark.asyncio
async def test_model_assignment_is_sticky_by_default(client: AsyncClient):
    token = await register_and_login(client, "f077_sticky@example.com")
    workspace_id = await create_workspace(client, token)
    model_id = await create_model(client, token, workspace_id)

    first = await client.get(
        "/observability/scaling/models/%s/assignment" % model_id,
        headers=auth_headers(token),
    )
    second = await client.get(
        "/observability/scaling/models/%s/assignment" % model_id,
        headers=auth_headers(token),
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["model_id"] == model_id
    assert second.json()["model_id"] == model_id
    assert first.json()["node_id"] == second.json()["node_id"]


@pytest.mark.asyncio
async def test_model_assignment_force_override(client: AsyncClient):
    token = await register_and_login(client, "f077_force_override@example.com")
    workspace_id = await create_workspace(client, token)
    model_id = await create_model(client, token, workspace_id)

    pinned = await client.put(
        "/observability/scaling/models/%s/assignment" % model_id,
        json={"node_id": "engine-node-a", "ttl_seconds": 120, "force": True},
        headers=auth_headers(token),
    )
    assert pinned.status_code == 200, pinned.text
    assert pinned.json()["node_id"] == "engine-node-a"

    sticky = await client.put(
        "/observability/scaling/models/%s/assignment" % model_id,
        json={"node_id": "engine-node-b", "ttl_seconds": 120, "force": False},
        headers=auth_headers(token),
    )
    assert sticky.status_code == 200, sticky.text
    assert sticky.json()["node_id"] == "engine-node-a"

    override = await client.put(
        "/observability/scaling/models/%s/assignment" % model_id,
        json={"node_id": "engine-node-b", "ttl_seconds": 120, "force": True},
        headers=auth_headers(token),
    )
    assert override.status_code == 200, override.text
    assert override.json()["node_id"] == "engine-node-b"


@pytest.mark.asyncio
async def test_model_assignment_not_found_when_auto_assign_disabled(client: AsyncClient):
    token = await register_and_login(client, "f077_auto_assign_false@example.com")
    workspace_id = await create_workspace(client, token)
    model_id = await create_model(client, token, workspace_id)

    response = await client.get(
        "/observability/scaling/models/%s/assignment?auto_assign=false" % model_id,
        headers=auth_headers(token),
    )
    assert response.status_code == 404
    assert "Model assignment not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_scaling_cache_set_and_get(client: AsyncClient):
    token = await register_and_login(client, "f077_cache@example.com")
    namespace = "module-%s" % uuid.uuid4().hex
    cache_key = "cell-%s" % uuid.uuid4().hex

    set_resp = await client.put(
        "/observability/scaling/cache/%s/%s" % (namespace, cache_key),
        json={"value": {"value": 42, "source": "test"}, "ttl_seconds": 120},
        headers=auth_headers(token),
    )
    assert set_resp.status_code == 200, set_resp.text

    get_resp = await client.get(
        "/observability/scaling/cache/%s/%s" % (namespace, cache_key),
        headers=auth_headers(token),
    )
    assert get_resp.status_code == 200, get_resp.text
    assert get_resp.json()["namespace"] == namespace
    assert get_resp.json()["key"] == cache_key
    assert get_resp.json()["value"]["value"] == 42


@pytest.mark.asyncio
async def test_scaling_cache_missing_returns_not_found(client: AsyncClient):
    token = await register_and_login(client, "f077_cache_missing@example.com")

    response = await client.get(
        "/observability/scaling/cache/missing/%s" % uuid.uuid4().hex,
        headers=auth_headers(token),
    )
    assert response.status_code == 404
    assert "Cache entry not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_scaling_event_publish_and_list(client: AsyncClient):
    token = await register_and_login(client, "f077_events@example.com")
    channel = "model-sync-%s" % uuid.uuid4().hex
    marker = uuid.uuid4().hex

    publish_resp = await client.post(
        "/observability/scaling/events/%s" % channel,
        json={
            "event_type": "model_rebalanced",
            "payload": {"marker": marker},
        },
        headers=auth_headers(token),
    )
    assert publish_resp.status_code == 201, publish_resp.text
    published = publish_resp.json()
    assert published["channel"] == channel
    assert published["event_type"] == "model_rebalanced"

    list_resp = await client.get(
        "/observability/scaling/events/%s?limit=10" % channel,
        headers=auth_headers(token),
    )
    assert list_resp.status_code == 200, list_resp.text
    events = list_resp.json()
    assert any(
        item["event_type"] == "model_rebalanced"
        and item["payload"].get("marker") == marker
        for item in events
    )


@pytest.mark.asyncio
async def test_scaling_kubernetes_manifest_endpoint(client: AsyncClient):
    token = await register_and_login(client, "f077_manifests@example.com")

    response = await client.get(
        "/observability/scaling/kubernetes/manifests",
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    manifests = response.json()["manifests"]
    assert len(manifests) >= 6

    names = {item["name"] for item in manifests}
    assert "api-deployment.yaml" in names
    assert "redis-deployment.yaml" in names
    assert "ingress.yaml" in names

    assert any("kind: Deployment" in item["content"] for item in manifests)
    assert any("sessionAffinity: ClientIP" in item["content"] for item in manifests)

