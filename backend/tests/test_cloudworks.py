import csv
import uuid

import pytest
from httpx import AsyncClient

# Import models so Base.metadata includes cloudworks tables
import app.models.cloudworks  # noqa: F401


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


async def create_model(client: AsyncClient, token: str, workspace_id: str, name: str = "Test Model") -> str:
    resp = await client.post(
        "/models",
        json={"name": name, "workspace_id": workspace_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_connection(
    client: AsyncClient,
    token: str,
    model_id: str,
    name: str = "My S3 Connection",
    connector_type: str = "s3",
    config: dict = None,
) -> dict:
    payload = {"name": name, "connector_type": connector_type}
    if config is not None:
        payload["config"] = config
    resp = await client.post(
        f"/models/{model_id}/connections",
        json=payload,
        headers=auth_headers(token),
    )
    return resp


async def create_schedule(
    client: AsyncClient,
    token: str,
    conn_id: str,
    name: str = "Nightly Import",
    schedule_type: str = "import",
    cron_expression: str = "0 0 * * *",
) -> dict:
    payload = {
        "name": name,
        "schedule_type": schedule_type,
        "cron_expression": cron_expression,
    }
    resp = await client.post(
        f"/connections/{conn_id}/schedules",
        json=payload,
        headers=auth_headers(token),
    )
    return resp


async def setup_model(client: AsyncClient, email: str):
    """Helper: register, login, create workspace + model. Returns (token, model_id)."""
    token = await register_and_login(client, email)
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    return token, model_id


async def setup_connection(client: AsyncClient, email: str):
    """Helper: setup model + connection. Returns (token, model_id, conn_id)."""
    token, model_id = await setup_model(client, email)
    resp = await create_connection(client, token, model_id)
    assert resp.status_code == 201
    conn_id = resp.json()["id"]
    return token, model_id, conn_id


async def setup_schedule(client: AsyncClient, email: str):
    """Helper: setup connection + schedule. Returns (token, model_id, conn_id, schedule_id)."""
    token, model_id, conn_id = await setup_connection(client, email)
    resp = await create_schedule(client, token, conn_id)
    assert resp.status_code == 201
    schedule_id = resp.json()["id"]
    return token, model_id, conn_id, schedule_id


# ---------------------------------------------------------------------------
# Connection CRUD tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_connection_s3(client: AsyncClient):
    token, model_id = await setup_model(client, "cw_conn_s3@example.com")
    resp = await create_connection(
        client, token, model_id,
        name="S3 Bucket",
        connector_type="s3",
        config={"bucket": "my-bucket", "region": "us-east-1"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "S3 Bucket"
    assert data["connector_type"] == "s3"
    assert data["model_id"] == model_id
    assert data["is_active"] is True
    assert data["config"]["bucket"] == "my-bucket"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_connection_sftp(client: AsyncClient):
    token, model_id = await setup_model(client, "cw_conn_sftp@example.com")
    resp = await create_connection(
        client, token, model_id,
        name="SFTP Server",
        connector_type="sftp",
        config={"host": "sftp.example.com", "port": 22},
    )
    assert resp.status_code == 201
    assert resp.json()["connector_type"] == "sftp"


@pytest.mark.asyncio
async def test_create_connection_database(client: AsyncClient):
    token, model_id = await setup_model(client, "cw_conn_db@example.com")
    resp = await create_connection(
        client, token, model_id,
        name="Postgres Source",
        connector_type="database",
    )
    assert resp.status_code == 201
    assert resp.json()["connector_type"] == "database"


@pytest.mark.asyncio
async def test_list_connections(client: AsyncClient):
    token, model_id = await setup_model(client, "cw_conn_list@example.com")
    await create_connection(client, token, model_id, name="Conn A", connector_type="s3")
    await create_connection(client, token, model_id, name="Conn B", connector_type="gcs")

    resp = await client.get(f"/models/{model_id}/connections", headers=auth_headers(token))
    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()]
    assert "Conn A" in names
    assert "Conn B" in names


@pytest.mark.asyncio
async def test_get_connection(client: AsyncClient):
    token, model_id, conn_id = await setup_connection(client, "cw_conn_get@example.com")
    resp = await client.get(f"/connections/{conn_id}", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["id"] == conn_id


@pytest.mark.asyncio
async def test_get_connection_404(client: AsyncClient):
    token = await register_and_login(client, "cw_conn_404@example.com")
    resp = await client.get(f"/connections/{uuid.uuid4()}", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_connection(client: AsyncClient):
    token, model_id, conn_id = await setup_connection(client, "cw_conn_upd@example.com")
    resp = await client.put(
        f"/connections/{conn_id}",
        json={"name": "Updated Name", "is_active": False},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Name"
    assert data["is_active"] is False


@pytest.mark.asyncio
async def test_delete_connection(client: AsyncClient):
    token, model_id, conn_id = await setup_connection(client, "cw_conn_del@example.com")
    del_resp = await client.delete(f"/connections/{conn_id}", headers=auth_headers(token))
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/connections/{conn_id}", headers=auth_headers(token))
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_connection_404(client: AsyncClient):
    token = await register_and_login(client, "cw_conn_del404@example.com")
    resp = await client.delete(f"/connections/{uuid.uuid4()}", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_connection_requires_auth(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    resp = await client.post(
        f"/models/{fake_id}/connections",
        json={"name": "No Auth", "connector_type": "s3"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_connections_requires_auth(client: AsyncClient):
    resp = await client.get(f"/models/{uuid.uuid4()}/connections")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Schedule CRUD tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_schedule_import(client: AsyncClient):
    token, model_id, conn_id = await setup_connection(client, "cw_sched_imp@example.com")
    resp = await create_schedule(
        client, token, conn_id,
        name="Nightly Import",
        schedule_type="import",
        cron_expression="0 2 * * *",
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Nightly Import"
    assert data["schedule_type"] == "import"
    assert data["cron_expression"] == "0 2 * * *"
    assert data["is_enabled"] is True
    assert data["max_retries"] == 3
    assert data["retry_delay_seconds"] == 60
    assert data["connection_id"] == conn_id


@pytest.mark.asyncio
async def test_create_schedule_export(client: AsyncClient):
    token, model_id, conn_id = await setup_connection(client, "cw_sched_exp@example.com")
    resp = await create_schedule(
        client, token, conn_id,
        name="Weekly Export",
        schedule_type="export",
        cron_expression="0 0 * * 0",
    )
    assert resp.status_code == 201
    assert resp.json()["schedule_type"] == "export"


@pytest.mark.asyncio
async def test_create_schedule_with_configs(client: AsyncClient):
    token, model_id, conn_id = await setup_connection(client, "cw_sched_cfg@example.com")
    resp = await client.post(
        f"/connections/{conn_id}/schedules",
        json={
            "name": "Configured Schedule",
            "schedule_type": "import",
            "cron_expression": "*/5 * * * *",
            "source_config": {"path": "/data/input.csv"},
            "target_config": {"module_id": "mod-123"},
            "max_retries": 5,
            "retry_delay_seconds": 120,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["source_config"]["path"] == "/data/input.csv"
    assert data["target_config"]["module_id"] == "mod-123"
    assert data["max_retries"] == 5
    assert data["retry_delay_seconds"] == 120


@pytest.mark.asyncio
async def test_list_schedules(client: AsyncClient):
    token, model_id, conn_id = await setup_connection(client, "cw_sched_list@example.com")
    await create_schedule(client, token, conn_id, name="Schedule A")
    await create_schedule(client, token, conn_id, name="Schedule B")

    resp = await client.get(f"/connections/{conn_id}/schedules", headers=auth_headers(token))
    assert resp.status_code == 200
    names = [s["name"] for s in resp.json()]
    assert "Schedule A" in names
    assert "Schedule B" in names


@pytest.mark.asyncio
async def test_get_schedule(client: AsyncClient):
    token, model_id, conn_id, sched_id = await setup_schedule(client, "cw_sched_get@example.com")
    resp = await client.get(f"/schedules/{sched_id}", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["id"] == sched_id


@pytest.mark.asyncio
async def test_get_schedule_404(client: AsyncClient):
    token = await register_and_login(client, "cw_sched_404@example.com")
    resp = await client.get(f"/schedules/{uuid.uuid4()}", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_schedule(client: AsyncClient):
    token, model_id, conn_id, sched_id = await setup_schedule(client, "cw_sched_upd@example.com")
    resp = await client.put(
        f"/schedules/{sched_id}",
        json={"name": "Updated Schedule", "cron_expression": "0 6 * * *", "max_retries": 10},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Schedule"
    assert data["cron_expression"] == "0 6 * * *"
    assert data["max_retries"] == 10


@pytest.mark.asyncio
async def test_delete_schedule(client: AsyncClient):
    token, model_id, conn_id, sched_id = await setup_schedule(client, "cw_sched_del@example.com")
    del_resp = await client.delete(f"/schedules/{sched_id}", headers=auth_headers(token))
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/schedules/{sched_id}", headers=auth_headers(token))
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_schedule_404(client: AsyncClient):
    token = await register_and_login(client, "cw_sched_del404@example.com")
    resp = await client.delete(f"/schedules/{uuid.uuid4()}", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_schedule_connection_404(client: AsyncClient):
    token = await register_and_login(client, "cw_sched_conn404@example.com")
    resp = await client.post(
        f"/connections/{uuid.uuid4()}/schedules",
        json={"name": "Orphan", "schedule_type": "import", "cron_expression": "* * * * *"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_schedule_requires_auth(client: AsyncClient):
    resp = await client.post(
        f"/connections/{uuid.uuid4()}/schedules",
        json={"name": "No Auth", "schedule_type": "import", "cron_expression": "* * * * *"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Enable / disable schedule
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enable_disable_schedule(client: AsyncClient):
    token, model_id, conn_id, sched_id = await setup_schedule(client, "cw_enable@example.com")

    # Disable
    resp = await client.put(
        f"/schedules/{sched_id}/enable",
        json={"is_enabled": False},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["is_enabled"] is False

    # Re-enable
    resp = await client.put(
        f"/schedules/{sched_id}/enable",
        json={"is_enabled": True},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["is_enabled"] is True


@pytest.mark.asyncio
async def test_enable_schedule_404(client: AsyncClient):
    token = await register_and_login(client, "cw_enable404@example.com")
    resp = await client.put(
        f"/schedules/{uuid.uuid4()}/enable",
        json={"is_enabled": False},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Trigger run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trigger_run(client: AsyncClient):
    token, model_id, conn_id, sched_id = await setup_schedule(client, "cw_trigger@example.com")
    resp = await client.post(f"/schedules/{sched_id}/trigger", headers=auth_headers(token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["schedule_id"] == sched_id
    assert data["status"] == "pending"
    assert data["attempt_number"] == 1


@pytest.mark.asyncio
async def test_trigger_run_schedule_404(client: AsyncClient):
    token = await register_and_login(client, "cw_trigger404@example.com")
    resp = await client.post(f"/schedules/{uuid.uuid4()}/trigger", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_trigger_run_requires_auth(client: AsyncClient):
    resp = await client.post(f"/schedules/{uuid.uuid4()}/trigger")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Run lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_lifecycle_complete(client: AsyncClient):
    token, model_id, conn_id, sched_id = await setup_schedule(client, "cw_lifecycle@example.com")

    # Trigger
    trigger_resp = await client.post(f"/schedules/{sched_id}/trigger", headers=auth_headers(token))
    run_id = trigger_resp.json()["id"]
    assert trigger_resp.json()["status"] == "pending"

    # Complete
    complete_resp = await client.post(
        f"/runs/{run_id}/complete",
        json={"records_processed": 42},
        headers=auth_headers(token),
    )
    assert complete_resp.status_code == 200
    data = complete_resp.json()
    assert data["status"] == "completed"
    assert data["records_processed"] == 42
    assert data["completed_at"] is not None


@pytest.mark.asyncio
async def test_run_lifecycle_fail(client: AsyncClient):
    token, model_id, conn_id, sched_id = await setup_schedule(client, "cw_fail@example.com")

    trigger_resp = await client.post(f"/schedules/{sched_id}/trigger", headers=auth_headers(token))
    run_id = trigger_resp.json()["id"]

    fail_resp = await client.post(
        f"/runs/{run_id}/fail",
        json={"error_message": "Connection refused"},
        headers=auth_headers(token),
    )
    assert fail_resp.status_code == 200
    data = fail_resp.json()
    assert data["status"] == "failed"
    assert data["error_message"] == "Connection refused"
    assert data["completed_at"] is not None


@pytest.mark.asyncio
async def test_complete_run_without_body(client: AsyncClient):
    token, model_id, conn_id, sched_id = await setup_schedule(client, "cw_complete_nobody@example.com")
    trigger_resp = await client.post(f"/schedules/{sched_id}/trigger", headers=auth_headers(token))
    run_id = trigger_resp.json()["id"]

    resp = await client.post(f"/runs/{run_id}/complete", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
    assert resp.json()["records_processed"] is None


@pytest.mark.asyncio
async def test_fail_run_without_body(client: AsyncClient):
    token, model_id, conn_id, sched_id = await setup_schedule(client, "cw_fail_nobody@example.com")
    trigger_resp = await client.post(f"/schedules/{sched_id}/trigger", headers=auth_headers(token))
    run_id = trigger_resp.json()["id"]

    resp = await client.post(f"/runs/{run_id}/fail", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "failed"


@pytest.mark.asyncio
async def test_get_run(client: AsyncClient):
    token, model_id, conn_id, sched_id = await setup_schedule(client, "cw_get_run@example.com")
    trigger_resp = await client.post(f"/schedules/{sched_id}/trigger", headers=auth_headers(token))
    run_id = trigger_resp.json()["id"]

    resp = await client.get(f"/runs/{run_id}", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["id"] == run_id
    assert resp.json()["schedule_id"] == sched_id


@pytest.mark.asyncio
async def test_get_run_404(client: AsyncClient):
    token = await register_and_login(client, "cw_run_404@example.com")
    resp = await client.get(f"/runs/{uuid.uuid4()}", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_runs(client: AsyncClient):
    token, model_id, conn_id, sched_id = await setup_schedule(client, "cw_list_runs@example.com")

    await client.post(f"/schedules/{sched_id}/trigger", headers=auth_headers(token))
    await client.post(f"/schedules/{sched_id}/trigger", headers=auth_headers(token))

    resp = await client.get(f"/schedules/{sched_id}/runs", headers=auth_headers(token))
    assert resp.status_code == 200
    runs = resp.json()
    assert len(runs) == 2
    for run in runs:
        assert run["schedule_id"] == sched_id


@pytest.mark.asyncio
async def test_list_runs_empty(client: AsyncClient):
    token, model_id, conn_id, sched_id = await setup_schedule(client, "cw_runs_empty@example.com")
    resp = await client.get(f"/schedules/{sched_id}/runs", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_runs_schedule_404(client: AsyncClient):
    token = await register_and_login(client, "cw_runs_404@example.com")
    resp = await client.get(f"/schedules/{uuid.uuid4()}/runs", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_runs_requires_auth(client: AsyncClient):
    resp = await client.get(f"/schedules/{uuid.uuid4()}/runs")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retry_run_success(client: AsyncClient):
    token, model_id, conn_id, sched_id = await setup_schedule(client, "cw_retry@example.com")

    # Trigger and fail
    trigger_resp = await client.post(f"/schedules/{sched_id}/trigger", headers=auth_headers(token))
    run_id = trigger_resp.json()["id"]
    await client.post(
        f"/runs/{run_id}/fail",
        json={"error_message": "Timeout"},
        headers=auth_headers(token),
    )

    # Retry
    retry_resp = await client.post(f"/runs/{run_id}/retry", headers=auth_headers(token))
    assert retry_resp.status_code == 201
    retry_data = retry_resp.json()
    assert retry_data["status"] == "retrying"
    assert retry_data["attempt_number"] == 2
    assert retry_data["schedule_id"] == sched_id


@pytest.mark.asyncio
async def test_retry_run_max_retries_exceeded(client: AsyncClient):
    token, model_id, conn_id = await setup_connection(client, "cw_retry_max@example.com")

    # Create schedule with max_retries=1
    sched_resp = await client.post(
        f"/connections/{conn_id}/schedules",
        json={
            "name": "Low Retry Schedule",
            "schedule_type": "import",
            "cron_expression": "0 0 * * *",
            "max_retries": 1,
        },
        headers=auth_headers(token),
    )
    assert sched_resp.status_code == 201
    sched_id = sched_resp.json()["id"]

    # Trigger and fail
    trigger_resp = await client.post(f"/schedules/{sched_id}/trigger", headers=auth_headers(token))
    run_id = trigger_resp.json()["id"]
    await client.post(f"/runs/{run_id}/fail", headers=auth_headers(token))

    # Retry should fail — attempt_number (1) >= max_retries (1)
    retry_resp = await client.post(f"/runs/{run_id}/retry", headers=auth_headers(token))
    assert retry_resp.status_code == 400
    assert "Max retries" in retry_resp.json()["detail"]


@pytest.mark.asyncio
async def test_retry_run_increments_attempt(client: AsyncClient):
    token, model_id, conn_id = await setup_connection(client, "cw_retry_inc@example.com")

    sched_resp = await client.post(
        f"/connections/{conn_id}/schedules",
        json={
            "name": "Multi Retry Schedule",
            "schedule_type": "import",
            "cron_expression": "0 0 * * *",
            "max_retries": 5,
        },
        headers=auth_headers(token),
    )
    sched_id = sched_resp.json()["id"]

    # Trigger -> fail -> retry -> fail -> retry
    trigger_resp = await client.post(f"/schedules/{sched_id}/trigger", headers=auth_headers(token))
    run_id = trigger_resp.json()["id"]
    assert trigger_resp.json()["attempt_number"] == 1

    await client.post(f"/runs/{run_id}/fail", headers=auth_headers(token))

    retry1_resp = await client.post(f"/runs/{run_id}/retry", headers=auth_headers(token))
    assert retry1_resp.status_code == 201
    retry1_id = retry1_resp.json()["id"]
    assert retry1_resp.json()["attempt_number"] == 2

    await client.post(f"/runs/{retry1_id}/fail", headers=auth_headers(token))

    retry2_resp = await client.post(f"/runs/{retry1_id}/retry", headers=auth_headers(token))
    assert retry2_resp.status_code == 201
    assert retry2_resp.json()["attempt_number"] == 3


@pytest.mark.asyncio
async def test_retry_run_404(client: AsyncClient):
    token = await register_and_login(client, "cw_retry404@example.com")
    resp = await client.post(f"/runs/{uuid.uuid4()}/retry", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_retry_requires_auth(client: AsyncClient):
    resp = await client.post(f"/runs/{uuid.uuid4()}/retry")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Connector types coverage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_all_connector_types(client: AsyncClient):
    token, model_id = await setup_model(client, "cw_all_types@example.com")
    for ct in ["s3", "gcs", "azure_blob", "sftp", "http", "database", "local_file"]:
        resp = await create_connection(client, token, model_id, name=f"{ct} conn", connector_type=ct)
        assert resp.status_code == 201
        assert resp.json()["connector_type"] == ct


# ---------------------------------------------------------------------------
# Connection cascade delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_connection_cascades_schedules(client: AsyncClient):
    token, model_id, conn_id = await setup_connection(client, "cw_cascade@example.com")
    sched_resp = await create_schedule(client, token, conn_id, name="Cascade Sched")
    sched_id = sched_resp.json()["id"]

    # Delete connection
    del_resp = await client.delete(f"/connections/{conn_id}", headers=auth_headers(token))
    assert del_resp.status_code == 204

    # Schedule should be gone
    get_resp = await client.get(f"/schedules/{sched_id}", headers=auth_headers(token))
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# Complete/fail run auth
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_run_requires_auth(client: AsyncClient):
    resp = await client.post(f"/runs/{uuid.uuid4()}/complete")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_fail_run_requires_auth(client: AsyncClient):
    resp = await client.post(f"/runs/{uuid.uuid4()}/fail")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Backpressure tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.backpressure
async def test_trigger_run_burst_backpressure(client: AsyncClient):
    token, model_id, conn_id, sched_id = await setup_schedule(client, "cw_burst@example.com")

    burst_size = 40
    run_ids = []
    for _ in range(burst_size):
        trigger_resp = await client.post(
            f"/schedules/{sched_id}/trigger",
            headers=auth_headers(token),
        )
        assert trigger_resp.status_code == 201
        run_ids.append(trigger_resp.json()["id"])

    assert len(set(run_ids)) == burst_size

    list_resp = await client.get(
        f"/schedules/{sched_id}/runs",
        headers=auth_headers(token),
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == burst_size


# ---------------------------------------------------------------------------
# Connector execution (F063)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_run_import_local_file_to_local_file(
    client: AsyncClient,
    tmp_path,
):
    token, model_id = await setup_model(client, "cw_exec_import@example.com")

    source_path = tmp_path / "source.csv"
    source_path.write_text("name,value\nAlpha,10\nBeta,20\n", encoding="utf-8")
    target_path = tmp_path / "target.csv"

    conn_resp = await create_connection(
        client,
        token,
        model_id,
        name="Local Source",
        connector_type="local_file",
        config={"path": str(source_path), "format": "csv"},
    )
    assert conn_resp.status_code == 201
    conn_id = conn_resp.json()["id"]

    schedule_resp = await client.post(
        f"/connections/{conn_id}/schedules",
        json={
            "name": "Local Import Run",
            "schedule_type": "import",
            "cron_expression": "0 0 * * *",
            "target_config": {
                "connector_type": "local_file",
                "path": str(target_path),
                "format": "csv",
            },
        },
        headers=auth_headers(token),
    )
    assert schedule_resp.status_code == 201
    schedule_id = schedule_resp.json()["id"]

    trigger_resp = await client.post(
        f"/schedules/{schedule_id}/trigger",
        headers=auth_headers(token),
    )
    assert trigger_resp.status_code == 201
    run_id = trigger_resp.json()["id"]

    execute_resp = await client.post(
        f"/runs/{run_id}/execute",
        headers=auth_headers(token),
    )
    assert execute_resp.status_code == 200
    run_data = execute_resp.json()
    assert run_data["status"] == "completed"
    assert run_data["records_processed"] == 2
    assert run_data["started_at"] is not None
    assert run_data["completed_at"] is not None

    assert target_path.exists()
    with target_path.open("r", encoding="utf-8") as target_file:
        rows = list(csv.DictReader(target_file))
    assert rows == [
        {"name": "Alpha", "value": "10"},
        {"name": "Beta", "value": "20"},
    ]


@pytest.mark.asyncio
async def test_execute_run_export_local_file_source_to_connection_target(
    client: AsyncClient,
    tmp_path,
):
    token, model_id = await setup_model(client, "cw_exec_export@example.com")

    source_path = tmp_path / "export_source.csv"
    source_path.write_text("sku,qty\nS1,3\nS2,8\n", encoding="utf-8")
    target_path = tmp_path / "export_target.csv"

    conn_resp = await create_connection(
        client,
        token,
        model_id,
        name="Local Target",
        connector_type="local_file",
        config={"path": str(target_path), "format": "csv"},
    )
    assert conn_resp.status_code == 201
    conn_id = conn_resp.json()["id"]

    schedule_resp = await client.post(
        f"/connections/{conn_id}/schedules",
        json={
            "name": "Local Export Run",
            "schedule_type": "export",
            "cron_expression": "0 1 * * *",
            "source_config": {
                "connector_type": "local_file",
                "path": str(source_path),
                "format": "csv",
            },
        },
        headers=auth_headers(token),
    )
    assert schedule_resp.status_code == 201
    schedule_id = schedule_resp.json()["id"]

    trigger_resp = await client.post(
        f"/schedules/{schedule_id}/trigger",
        headers=auth_headers(token),
    )
    run_id = trigger_resp.json()["id"]

    execute_resp = await client.post(
        f"/runs/{run_id}/execute",
        headers=auth_headers(token),
    )
    assert execute_resp.status_code == 200
    run_data = execute_resp.json()
    assert run_data["status"] == "completed"
    assert run_data["records_processed"] == 2

    assert target_path.exists()
    with target_path.open("r", encoding="utf-8") as target_file:
        rows = list(csv.DictReader(target_file))
    assert rows == [
        {"sku": "S1", "qty": "3"},
        {"sku": "S2", "qty": "8"},
    ]


@pytest.mark.asyncio
async def test_execute_run_marks_failed_for_unimplemented_connector(
    client: AsyncClient,
    tmp_path,
):
    token, model_id = await setup_model(client, "cw_exec_fail_connector@example.com")
    target_path = tmp_path / "failed_target.csv"

    conn_resp = await create_connection(
        client,
        token,
        model_id,
        name="Unsupported Source",
        connector_type="gcs",
        config={"bucket": "unused"},
    )
    assert conn_resp.status_code == 201
    conn_id = conn_resp.json()["id"]

    schedule_resp = await client.post(
        f"/connections/{conn_id}/schedules",
        json={
            "name": "Unsupported Import Run",
            "schedule_type": "import",
            "cron_expression": "0 0 * * *",
            "target_config": {
                "connector_type": "local_file",
                "path": str(target_path),
                "format": "csv",
            },
        },
        headers=auth_headers(token),
    )
    assert schedule_resp.status_code == 201
    schedule_id = schedule_resp.json()["id"]

    trigger_resp = await client.post(
        f"/schedules/{schedule_id}/trigger",
        headers=auth_headers(token),
    )
    run_id = trigger_resp.json()["id"]

    execute_resp = await client.post(
        f"/runs/{run_id}/execute",
        headers=auth_headers(token),
    )
    assert execute_resp.status_code == 200
    run_data = execute_resp.json()
    assert run_data["status"] == "failed"
    assert "not implemented" in (run_data["error_message"] or "").lower()
    assert run_data["completed_at"] is not None


@pytest.mark.asyncio
async def test_execute_run_rejects_completed_status(client: AsyncClient):
    token, model_id, conn_id, sched_id = await setup_schedule(
        client, "cw_exec_status_guard@example.com"
    )
    trigger_resp = await client.post(
        f"/schedules/{sched_id}/trigger",
        headers=auth_headers(token),
    )
    run_id = trigger_resp.json()["id"]

    complete_resp = await client.post(
        f"/runs/{run_id}/complete",
        headers=auth_headers(token),
    )
    assert complete_resp.status_code == 200
    assert complete_resp.json()["status"] == "completed"

    execute_resp = await client.post(
        f"/runs/{run_id}/execute",
        headers=auth_headers(token),
    )
    assert execute_resp.status_code == 400
    assert "pending/retrying" in execute_resp.json()["detail"]


@pytest.mark.asyncio
async def test_execute_run_requires_auth(client: AsyncClient):
    resp = await client.post(f"/runs/{uuid.uuid4()}/execute")
    assert resp.status_code == 401
