"""
Tests for Feature F044: Large model engine profiles (Classic and Polaris-like).

Covers:
  - Engine profile CRUD (create/upsert, get, delete)
  - Profile metrics recording and listing
  - Guidance rules CRUD (create, list all, list by type, delete)
  - Model evaluation against guidance rules
  - Profile recommendation engine
  - Auth required for all endpoints
"""
import uuid

import pytest
from httpx import AsyncClient

# Import models so they are registered with Base.metadata before create_all.
from app.models.engine_profile import (  # noqa: F401
    EngineProfile,
    EngineProfileMetric,
    ModelDesignGuidance,
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


async def create_profile(
    client: AsyncClient,
    token: str,
    model_id: str,
    profile_type: str = "classic",
    **kwargs,
) -> dict:
    payload = {"profile_type": profile_type, **kwargs}
    resp = await client.post(
        f"/models/{model_id}/engine-profile",
        json=payload,
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def create_guidance_rule(
    client: AsyncClient,
    token: str,
    profile_type: str = "classic",
    rule_code: str = "max_dimensions_classic",
    severity: str = "warning",
    title: str = "Dimension limit",
    description: str = "Too many dimensions",
    threshold_value: float = None,
) -> dict:
    payload = {
        "profile_type": profile_type,
        "rule_code": rule_code,
        "severity": severity,
        "title": title,
        "description": description,
    }
    if threshold_value is not None:
        payload["threshold_value"] = threshold_value
    resp = await client.post(
        "/engine-guidance",
        json=payload,
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Engine profile CRUD tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_engine_profile(client: AsyncClient):
    token, model_id = await setup_env(client, "ep1@test.com")
    profile = await create_profile(client, token, model_id)
    assert profile["profile_type"] == "classic"
    assert profile["model_id"] == model_id
    assert profile["max_cells"] == 10_000_000
    assert profile["sparse_optimization"] is False


@pytest.mark.asyncio
async def test_create_polaris_profile(client: AsyncClient):
    token, model_id = await setup_env(client, "ep2@test.com")
    profile = await create_profile(
        client, token, model_id,
        profile_type="polaris",
        sparse_optimization=True,
        parallel_calc=True,
        max_cells=500_000_000,
    )
    assert profile["profile_type"] == "polaris"
    assert profile["sparse_optimization"] is True
    assert profile["parallel_calc"] is True
    assert profile["max_cells"] == 500_000_000


@pytest.mark.asyncio
async def test_get_engine_profile(client: AsyncClient):
    token, model_id = await setup_env(client, "ep3@test.com")
    await create_profile(client, token, model_id)
    resp = await client.get(
        f"/models/{model_id}/engine-profile",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["profile_type"] == "classic"


@pytest.mark.asyncio
async def test_get_profile_not_found(client: AsyncClient):
    token, model_id = await setup_env(client, "ep4@test.com")
    resp = await client.get(
        f"/models/{model_id}/engine-profile",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upsert_engine_profile(client: AsyncClient):
    """Setting profile again should update, not create duplicate."""
    token, model_id = await setup_env(client, "ep5@test.com")
    p1 = await create_profile(client, token, model_id, profile_type="classic")
    p2 = await create_profile(client, token, model_id, profile_type="polaris", max_cells=999)
    assert p1["id"] == p2["id"]
    assert p2["profile_type"] == "polaris"
    assert p2["max_cells"] == 999


@pytest.mark.asyncio
async def test_delete_engine_profile(client: AsyncClient):
    token, model_id = await setup_env(client, "ep6@test.com")
    await create_profile(client, token, model_id)
    resp = await client.delete(
        f"/models/{model_id}/engine-profile",
        headers=auth_headers(token),
    )
    assert resp.status_code == 204
    resp2 = await client.get(
        f"/models/{model_id}/engine-profile",
        headers=auth_headers(token),
    )
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_delete_profile_not_found(client: AsyncClient):
    token, model_id = await setup_env(client, "ep7@test.com")
    resp = await client.delete(
        f"/models/{model_id}/engine-profile",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_profile_model_not_found(client: AsyncClient):
    token = await register_and_login(client, "ep8@test.com")
    fake_id = str(uuid.uuid4())
    resp = await client.post(
        f"/models/{fake_id}/engine-profile",
        json={"profile_type": "classic"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_profile_with_settings(client: AsyncClient):
    token, model_id = await setup_env(client, "ep9@test.com")
    settings = {"chunk_size": 1024, "compression": "lz4"}
    profile = await create_profile(client, token, model_id, settings=settings)
    assert profile["settings"] == settings


# ---------------------------------------------------------------------------
# Metrics tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_metric(client: AsyncClient):
    token, model_id = await setup_env(client, "met1@test.com")
    await create_profile(client, token, model_id)
    resp = await client.post(
        f"/models/{model_id}/engine-profile/metrics",
        json={"metric_name": "calc_time_ms", "metric_value": 1234.5},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["metric_name"] == "calc_time_ms"
    assert data["metric_value"] == 1234.5


@pytest.mark.asyncio
async def test_record_metric_with_metadata(client: AsyncClient):
    token, model_id = await setup_env(client, "met2@test.com")
    await create_profile(client, token, model_id)
    resp = await client.post(
        f"/models/{model_id}/engine-profile/metrics",
        json={
            "metric_name": "memory_usage_mb",
            "metric_value": 2048.0,
            "metadata": {"module": "Revenue"},
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    assert resp.json()["metadata_json"] == {"module": "Revenue"}


@pytest.mark.asyncio
async def test_list_metrics(client: AsyncClient):
    token, model_id = await setup_env(client, "met3@test.com")
    await create_profile(client, token, model_id)
    await client.post(
        f"/models/{model_id}/engine-profile/metrics",
        json={"metric_name": "calc_time_ms", "metric_value": 100},
        headers=auth_headers(token),
    )
    await client.post(
        f"/models/{model_id}/engine-profile/metrics",
        json={"metric_name": "calc_time_ms", "metric_value": 200},
        headers=auth_headers(token),
    )
    resp = await client.get(
        f"/models/{model_id}/engine-profile/metrics",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_metrics_no_profile(client: AsyncClient):
    token, model_id = await setup_env(client, "met4@test.com")
    resp = await client.post(
        f"/models/{model_id}/engine-profile/metrics",
        json={"metric_name": "calc_time_ms", "metric_value": 100},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_metrics_no_profile(client: AsyncClient):
    token, model_id = await setup_env(client, "met5@test.com")
    resp = await client.get(
        f"/models/{model_id}/engine-profile/metrics",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Guidance rules tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_guidance_rule(client: AsyncClient):
    token = await register_and_login(client, "guid1@test.com")
    rule = await create_guidance_rule(
        client, token,
        threshold_value=20.0,
    )
    assert rule["rule_code"] == "max_dimensions_classic"
    assert rule["severity"] == "warning"
    assert rule["threshold_value"] == 20.0


@pytest.mark.asyncio
async def test_list_all_guidance(client: AsyncClient):
    token = await register_and_login(client, "guid2@test.com")
    await create_guidance_rule(client, token, rule_code="rule_a")
    await create_guidance_rule(
        client, token, profile_type="polaris", rule_code="rule_b"
    )
    resp = await client.get("/engine-guidance", headers=auth_headers(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_list_guidance_by_type(client: AsyncClient):
    token = await register_and_login(client, "guid3@test.com")
    await create_guidance_rule(client, token, rule_code="rule_c")
    await create_guidance_rule(
        client, token, profile_type="polaris", rule_code="rule_d"
    )
    resp = await client.get(
        "/engine-guidance/classic", headers=auth_headers(token)
    )
    assert resp.status_code == 200
    rules = resp.json()
    assert len(rules) == 1
    assert rules[0]["profile_type"] == "classic"


@pytest.mark.asyncio
async def test_delete_guidance_rule(client: AsyncClient):
    token = await register_and_login(client, "guid4@test.com")
    rule = await create_guidance_rule(client, token, rule_code="rule_e")
    resp = await client.delete(
        f"/engine-guidance/{rule['id']}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 204
    resp2 = await client.get("/engine-guidance", headers=auth_headers(token))
    assert len(resp2.json()) == 0


@pytest.mark.asyncio
async def test_delete_guidance_not_found(client: AsyncClient):
    token = await register_and_login(client, "guid5@test.com")
    resp = await client.delete(
        f"/engine-guidance/{uuid.uuid4()}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_guidance_without_threshold(client: AsyncClient):
    token = await register_and_login(client, "guid6@test.com")
    rule = await create_guidance_rule(
        client, token, rule_code="rule_info",
        severity="info", title="Best practice",
        description="Use sparse optimization for large models",
    )
    assert rule["threshold_value"] is None
    assert rule["severity"] == "info"


# ---------------------------------------------------------------------------
# Evaluation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evaluate_passes(client: AsyncClient):
    token, model_id = await setup_env(client, "eval1@test.com")
    await create_profile(client, token, model_id)
    await create_guidance_rule(
        client, token,
        rule_code="max_dimension_count",
        threshold_value=20.0,
    )
    resp = await client.get(
        f"/models/{model_id}/engine-profile/evaluate",
        params={"dimension_count": 5, "cell_estimate": 1000, "line_item_count": 10},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["passed"] is True
    assert len(data["violations"]) == 0


@pytest.mark.asyncio
async def test_evaluate_with_violations(client: AsyncClient):
    token, model_id = await setup_env(client, "eval2@test.com")
    await create_profile(client, token, model_id)
    await create_guidance_rule(
        client, token,
        rule_code="max_dimension_limit",
        severity="error",
        title="Too many dimensions",
        description="Classic profile supports at most 20 dimensions",
        threshold_value=20.0,
    )
    resp = await client.get(
        f"/models/{model_id}/engine-profile/evaluate",
        params={"dimension_count": 25, "cell_estimate": 100, "line_item_count": 5},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["passed"] is False
    assert len(data["violations"]) == 1
    assert data["violations"][0]["actual_value"] == 25.0


@pytest.mark.asyncio
async def test_evaluate_no_profile(client: AsyncClient):
    token, model_id = await setup_env(client, "eval3@test.com")
    resp = await client.get(
        f"/models/{model_id}/engine-profile/evaluate",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Recommendation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recommend_classic(client: AsyncClient):
    token, model_id = await setup_env(client, "rec1@test.com")
    resp = await client.get(
        f"/models/{model_id}/engine-profile/recommend",
        params={"dimension_count": 5, "cell_estimate": 1000, "sparsity_ratio": 0.1},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["recommended_profile"] == "classic"
    assert data["model_id"] == model_id


@pytest.mark.asyncio
async def test_recommend_polaris_high_dimensions(client: AsyncClient):
    token, model_id = await setup_env(client, "rec2@test.com")
    resp = await client.get(
        f"/models/{model_id}/engine-profile/recommend",
        params={"dimension_count": 15, "cell_estimate": 1000, "sparsity_ratio": 0.1},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["recommended_profile"] == "polaris"


@pytest.mark.asyncio
async def test_recommend_polaris_high_cells(client: AsyncClient):
    token, model_id = await setup_env(client, "rec3@test.com")
    resp = await client.get(
        f"/models/{model_id}/engine-profile/recommend",
        params={"dimension_count": 5, "cell_estimate": 100_000_000, "sparsity_ratio": 0.1},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["recommended_profile"] == "polaris"


@pytest.mark.asyncio
async def test_recommend_polaris_high_sparsity(client: AsyncClient):
    token, model_id = await setup_env(client, "rec4@test.com")
    resp = await client.get(
        f"/models/{model_id}/engine-profile/recommend",
        params={"dimension_count": 5, "cell_estimate": 1000, "sparsity_ratio": 0.7},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["recommended_profile"] == "polaris"


@pytest.mark.asyncio
async def test_recommend_model_not_found(client: AsyncClient):
    token = await register_and_login(client, "rec5@test.com")
    resp = await client.get(
        f"/models/{uuid.uuid4()}/engine-profile/recommend",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_profile_requires_auth(client: AsyncClient):
    token, model_id = await setup_env(client, "auth1@test.com")
    resp = await client.get(f"/models/{model_id}/engine-profile")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_metrics_requires_auth(client: AsyncClient):
    token, model_id = await setup_env(client, "auth2@test.com")
    resp = await client.get(f"/models/{model_id}/engine-profile/metrics")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_guidance_requires_auth(client: AsyncClient):
    resp = await client.get("/engine-guidance")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_evaluate_requires_auth(client: AsyncClient):
    token, model_id = await setup_env(client, "auth3@test.com")
    resp = await client.get(f"/models/{model_id}/engine-profile/evaluate")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_recommend_requires_auth(client: AsyncClient):
    token, model_id = await setup_env(client, "auth4@test.com")
    resp = await client.get(f"/models/{model_id}/engine-profile/recommend")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Backpressure tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.backpressure
async def test_metric_ingest_backpressure(client: AsyncClient):
    token, model_id = await setup_env(client, "ep_bp_metrics@test.com")
    await create_profile(client, token, model_id, profile_type="polaris")

    metric_count = 120
    for idx in range(metric_count):
        resp = await client.post(
            f"/models/{model_id}/engine-profile/metrics",
            json={
                "metric_name": "calc_time_ms",
                "metric_value": float(idx),
                "metadata": {"batch": "bp"},
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 201

    list_resp = await client.get(
        f"/models/{model_id}/engine-profile/metrics",
        headers=auth_headers(token),
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == metric_count


@pytest.mark.asyncio
@pytest.mark.backpressure
async def test_evaluate_with_many_guidance_rules_backpressure(client: AsyncClient):
    token, model_id = await setup_env(client, "ep_bp_eval@test.com")
    await create_profile(client, token, model_id, profile_type="classic")

    rule_count = 60
    for idx in range(rule_count):
        await create_guidance_rule(
            client,
            token,
            profile_type="classic",
            rule_code=f"max_dimension_rule_{idx}",
            severity="warning",
            title=f"Rule {idx}",
            description="Dimension threshold",
            threshold_value=10.0,
        )

    evaluate_resp = await client.get(
        f"/models/{model_id}/engine-profile/evaluate",
        params={"dimension_count": 25, "cell_estimate": 1000, "line_item_count": 10},
        headers=auth_headers(token),
    )
    assert evaluate_resp.status_code == 200
    body = evaluate_resp.json()
    assert body["passed"] is False
    assert len(body["violations"]) == rule_count
