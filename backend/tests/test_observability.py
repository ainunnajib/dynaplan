import uuid

import pytest
from httpx import AsyncClient

from app.core.database import get_db as original_get_db
from app.main import app
from app.models.pipeline import StepLogStatus
from app.services.observability import api_metrics_collector
from app.services.pipeline import get_run_by_id, update_step_log_status


@pytest.fixture(autouse=True)
def reset_observability_collector():
    api_metrics_collector.reset()
    yield
    api_metrics_collector.reset()


async def register_and_login(
    client: AsyncClient,
    email: str,
    password: str = "testpass123",
) -> str:
    await client.post(
        "/auth/register",
        json={
            "email": email,
            "full_name": "Test User",
            "password": password,
        },
    )
    resp = await client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": "Bearer %s" % token}


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


async def setup_env(client: AsyncClient, email: str):
    token = await register_and_login(client, email)
    workspace_id = await create_workspace(client, token)
    model_id = await create_model(client, token, workspace_id)
    return token, model_id


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_prometheus_format(client: AsyncClient):
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")

    body = response.text
    assert "dynaplan_api_requests_total" in body
    assert "dynaplan_api_request_latency_seconds_bucket" in body
    assert "dynaplan_cloudworks_run_success_rate" in body
    assert "dynaplan_health_status" in body


@pytest.mark.asyncio
async def test_observability_dashboard_requires_auth(client: AsyncClient):
    response = await client.get("/observability/dashboard")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_observability_dashboard_returns_engine_metrics_for_model(client: AsyncClient):
    token, model_id = await setup_env(client, "obs_engine@example.com")

    profile_resp = await client.post(
        f"/models/{model_id}/engine-profile",
        json={"profile_type": "classic"},
        headers=auth_headers(token),
    )
    assert profile_resp.status_code == 201

    metric_resp_1 = await client.post(
        f"/models/{model_id}/engine-profile/metrics",
        json={"metric_name": "calc_time_ms", "metric_value": 100.0},
        headers=auth_headers(token),
    )
    metric_resp_2 = await client.post(
        f"/models/{model_id}/engine-profile/metrics",
        json={"metric_name": "calc_time_ms", "metric_value": 200.0},
        headers=auth_headers(token),
    )
    memory_metric_resp = await client.post(
        f"/models/{model_id}/engine-profile/metrics",
        json={"metric_name": "memory_usage_mb", "metric_value": 512.0},
        headers=auth_headers(token),
    )
    assert metric_resp_1.status_code == 201
    assert metric_resp_2.status_code == 201
    assert memory_metric_resp.status_code == 201

    dashboard_resp = await client.get(
        f"/observability/dashboard?model_id={model_id}",
        headers=auth_headers(token),
    )
    assert dashboard_resp.status_code == 200

    payload = dashboard_resp.json()
    assert payload["engine"]["tracked_models"] == 1

    engine_model = payload["engine"]["models"][0]
    assert engine_model["model_id"] == model_id
    assert engine_model["calc_time_ms_avg"] == pytest.approx(150.0)
    assert engine_model["calc_time_ms_latest"] in (100.0, 200.0)
    assert engine_model["memory_usage_mb"] == pytest.approx(512.0)


@pytest.mark.asyncio
async def test_observability_dashboard_reports_active_users(client: AsyncClient):
    token, model_id = await setup_env(client, "obs_active_users@example.com")

    presence_resp = await client.post(
        f"/models/{model_id}/presence",
        json={"model_id": model_id},
        headers=auth_headers(token),
    )
    assert presence_resp.status_code == 201

    dashboard_resp = await client.get(
        f"/observability/dashboard?model_id={model_id}",
        headers=auth_headers(token),
    )
    assert dashboard_resp.status_code == 200
    assert dashboard_resp.json()["api"]["active_users"] == 1


@pytest.mark.asyncio
async def test_observability_dashboard_reports_cloudworks_success_rate(client: AsyncClient):
    token, model_id = await setup_env(client, "obs_cloudworks@example.com")

    connection_resp = await client.post(
        f"/models/{model_id}/connections",
        json={"name": "S3", "connector_type": "s3"},
        headers=auth_headers(token),
    )
    assert connection_resp.status_code == 201
    connection_id = connection_resp.json()["id"]

    schedule_resp = await client.post(
        f"/connections/{connection_id}/schedules",
        json={
            "name": "Nightly",
            "schedule_type": "import",
            "cron_expression": "0 0 * * *",
        },
        headers=auth_headers(token),
    )
    assert schedule_resp.status_code == 201
    schedule_id = schedule_resp.json()["id"]

    run1_resp = await client.post(
        f"/schedules/{schedule_id}/trigger",
        headers=auth_headers(token),
    )
    run2_resp = await client.post(
        f"/schedules/{schedule_id}/trigger",
        headers=auth_headers(token),
    )
    assert run1_resp.status_code == 201
    assert run2_resp.status_code == 201

    run1_id = run1_resp.json()["id"]
    run2_id = run2_resp.json()["id"]

    complete_resp = await client.post(
        f"/runs/{run1_id}/complete",
        json={"records_processed": 42},
        headers=auth_headers(token),
    )
    fail_resp = await client.post(
        f"/runs/{run2_id}/fail",
        json={"error_message": "boom"},
        headers=auth_headers(token),
    )
    assert complete_resp.status_code == 200
    assert fail_resp.status_code == 200

    dashboard_resp = await client.get(
        "/observability/dashboard",
        headers=auth_headers(token),
    )
    assert dashboard_resp.status_code == 200

    integration = dashboard_resp.json()["integration"]
    assert integration["cloudworks_runs_total"] == 2
    assert integration["cloudworks_run_success_rate"] == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_observability_dashboard_reports_pipeline_throughput(client: AsyncClient):
    token, model_id = await setup_env(client, "obs_pipeline@example.com")

    pipeline_resp = await client.post(
        f"/models/{model_id}/pipelines",
        json={"name": "Observability Pipeline"},
        headers=auth_headers(token),
    )
    assert pipeline_resp.status_code == 201
    pipeline_id = pipeline_resp.json()["id"]

    step_resp = await client.post(
        f"/pipelines/{pipeline_id}/steps",
        json={"name": "Source", "step_type": "source", "sort_order": 0},
        headers=auth_headers(token),
    )
    assert step_resp.status_code == 201

    run_resp = await client.post(
        f"/pipelines/{pipeline_id}/trigger",
        headers=auth_headers(token),
    )
    assert run_resp.status_code == 201
    run_id = run_resp.json()["id"]

    override_fn = app.dependency_overrides.get(original_get_db)
    assert override_fn is not None

    async for db in override_fn():
        run = await get_run_by_id(db, uuid.UUID(run_id))
        assert run is not None
        assert len(run.step_logs) == 1

        log = run.step_logs[0]
        await update_step_log_status(
            db,
            log,
            StepLogStatus.running,
            records_in=100,
        )
        await update_step_log_status(
            db,
            log,
            StepLogStatus.completed,
            records_in=100,
            records_out=85,
        )
        break

    dashboard_resp = await client.get(
        "/observability/dashboard",
        headers=auth_headers(token),
    )
    assert dashboard_resp.status_code == 200

    integration = dashboard_resp.json()["integration"]
    assert integration["pipeline_runs_total"] == 1
    assert integration["pipeline_throughput_records_per_minute"] > 0


@pytest.mark.asyncio
async def test_observability_dashboard_includes_api_metrics(client: AsyncClient):
    token, _ = await setup_env(client, "obs_api_metrics@example.com")

    health_resp_1 = await client.get("/health")
    health_resp_2 = await client.get("/health")
    missing_resp = await client.get("/this-route-does-not-exist")

    assert health_resp_1.status_code == 200
    assert health_resp_2.status_code == 200
    assert missing_resp.status_code == 404

    dashboard_resp = await client.get(
        "/observability/dashboard",
        headers=auth_headers(token),
    )
    assert dashboard_resp.status_code == 200

    api_metrics = dashboard_resp.json()["api"]
    assert api_metrics["requests_total"] >= 3
    assert api_metrics["requests_last_5m"] >= 1
    assert api_metrics["request_latency_ms_avg"] >= 0
    assert api_metrics["error_rate"] > 0


@pytest.mark.asyncio
async def test_grafana_template_endpoint_returns_dashboard(client: AsyncClient):
    token, _ = await setup_env(client, "obs_grafana@example.com")

    response = await client.get(
        "/observability/grafana-template",
        headers=auth_headers(token),
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["title"] == "Dynaplan Observability"
    assert "template" in payload
    assert len(payload["template"]["panels"]) > 0


@pytest.mark.asyncio
async def test_metrics_endpoint_includes_engine_model_labels(client: AsyncClient):
    token, model_id = await setup_env(client, "obs_metric_labels@example.com")

    profile_resp = await client.post(
        f"/models/{model_id}/engine-profile",
        json={"profile_type": "classic"},
        headers=auth_headers(token),
    )
    metric_resp = await client.post(
        f"/models/{model_id}/engine-profile/metrics",
        json={"metric_name": "calc_time_ms", "metric_value": 250},
        headers=auth_headers(token),
    )
    assert profile_resp.status_code == 201
    assert metric_resp.status_code == 201

    metrics_resp = await client.get("/metrics")
    assert metrics_resp.status_code == 200

    line_prefix = 'dynaplan_engine_calc_time_ms_avg{model_id="%s"}' % model_id
    assert line_prefix in metrics_resp.text


@pytest.mark.asyncio
async def test_observability_dashboard_health_checks_present(client: AsyncClient):
    token, _ = await setup_env(client, "obs_checks@example.com")

    response = await client.get(
        "/observability/dashboard",
        headers=auth_headers(token),
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["health_status"] in ("ok", "degraded")

    check_names = {check["name"] for check in payload["checks"]}
    assert "database" in check_names
    assert "api_error_rate" in check_names
    assert "cloudworks_success_rate" in check_names
