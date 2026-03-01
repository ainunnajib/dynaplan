"""
Tests for Feature F041: Data Orchestrator pipelines.

Covers:
  - Pipeline CRUD (create, list, get detail, update, delete)
  - Pipeline step CRUD (add, update, delete)
  - Step reorder
  - Trigger pipeline run
  - Run lifecycle (trigger, cancel)
  - Run detail with step logs
  - Pipeline validation
  - Auth required for all endpoints
"""
import uuid

import pytest
from httpx import AsyncClient

# Import models so they are registered with Base.metadata before create_all.
from app.models.pipeline import (  # noqa: F401
    Pipeline,
    PipelineRun,
    PipelineStep,
    PipelineStepLog,
)
from app.main import app  # noqa: F401 — used by service-layer tests



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


async def create_pipeline_api(client, token, model_id, name="My Pipeline"):
    resp = await client.post(
        f"/models/{model_id}/pipelines",
        json={"name": name},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def add_step_api(
    client, token, pipeline_id, name="Step 1", step_type="source", sort_order=0, config=None
):
    payload = {"name": name, "step_type": step_type, "sort_order": sort_order}
    if config is not None:
        payload["config"] = config
    resp = await client.post(
        f"/pipelines/{pipeline_id}/steps",
        json=payload,
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def create_full_pipeline(client, token, model_id, name="Full Pipeline"):
    """Create a pipeline with source, transform, and publish steps."""
    pl = await create_pipeline_api(client, token, model_id, name)
    pid = pl["id"]
    s1 = await add_step_api(client, token, pid, "Source", "source", 0)
    s2 = await add_step_api(client, token, pid, "Transform", "transform", 1)
    s3 = await add_step_api(client, token, pid, "Publish", "publish", 2)
    return pl, [s1, s2, s3]


# ---------------------------------------------------------------------------
# Pipeline CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_pipeline(client: AsyncClient):
    token, model_id = await setup_env(client, "pl_create@example.com")
    resp = await client.post(
        f"/models/{model_id}/pipelines",
        json={"name": "ETL Pipeline", "description": "Loads data"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "ETL Pipeline"
    assert data["description"] == "Loads data"
    assert data["is_active"] is True
    assert data["model_id"] == model_id


@pytest.mark.asyncio
async def test_create_pipeline_requires_auth(client: AsyncClient):
    fake_model_id = str(uuid.uuid4())
    resp = await client.post(
        f"/models/{fake_model_id}/pipelines",
        json={"name": "No auth"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_pipeline_model_not_found(client: AsyncClient):
    token = await register_and_login(client, "pl_create_404@example.com")
    fake_model_id = str(uuid.uuid4())
    resp = await client.post(
        f"/models/{fake_model_id}/pipelines",
        json={"name": "No model"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_pipelines(client: AsyncClient):
    token, model_id = await setup_env(client, "pl_list@example.com")
    await create_pipeline_api(client, token, model_id, "PL1")
    await create_pipeline_api(client, token, model_id, "PL2")

    resp = await client.get(
        f"/models/{model_id}/pipelines",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_list_pipelines_empty(client: AsyncClient):
    token, model_id = await setup_env(client, "pl_list_empty@example.com")
    resp = await client.get(
        f"/models/{model_id}/pipelines",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_pipeline_detail(client: AsyncClient):
    token, model_id = await setup_env(client, "pl_detail@example.com")
    pl = await create_pipeline_api(client, token, model_id)
    await add_step_api(client, token, pl["id"], "Source Step", "source", 0)

    resp = await client.get(
        f"/pipelines/{pl['id']}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "My Pipeline"
    assert len(data["steps"]) == 1
    assert data["steps"][0]["name"] == "Source Step"


@pytest.mark.asyncio
async def test_get_pipeline_not_found(client: AsyncClient):
    token = await register_and_login(client, "pl_get_404@example.com")
    resp = await client.get(
        f"/pipelines/{uuid.uuid4()}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_pipeline(client: AsyncClient):
    token, model_id = await setup_env(client, "pl_update@example.com")
    pl = await create_pipeline_api(client, token, model_id)

    resp = await client.put(
        f"/pipelines/{pl['id']}",
        json={"name": "Updated Pipeline", "description": "New desc", "is_active": False},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Pipeline"
    assert resp.json()["description"] == "New desc"
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_delete_pipeline(client: AsyncClient):
    token, model_id = await setup_env(client, "pl_delete@example.com")
    pl = await create_pipeline_api(client, token, model_id)

    resp = await client.delete(
        f"/pipelines/{pl['id']}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 204

    resp2 = await client.get(
        f"/pipelines/{pl['id']}",
        headers=auth_headers(token),
    )
    assert resp2.status_code == 404


# ---------------------------------------------------------------------------
# Step CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_step(client: AsyncClient):
    token, model_id = await setup_env(client, "pl_step_add@example.com")
    pl = await create_pipeline_api(client, token, model_id)

    resp = await client.post(
        f"/pipelines/{pl['id']}/steps",
        json={"name": "Extract", "step_type": "source", "sort_order": 0, "config": '{"url": "s3://bucket"}'},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Extract"
    assert data["step_type"] == "source"
    assert data["sort_order"] == 0
    assert data["config"] == '{"url": "s3://bucket"}'


@pytest.mark.asyncio
async def test_add_step_invalid_type(client: AsyncClient):
    token, model_id = await setup_env(client, "pl_step_bad_type@example.com")
    pl = await create_pipeline_api(client, token, model_id)

    resp = await client.post(
        f"/pipelines/{pl['id']}/steps",
        json={"name": "Bad", "step_type": "invalid_type", "sort_order": 0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_add_step_pipeline_not_found(client: AsyncClient):
    token = await register_and_login(client, "pl_step_no_pipeline@example.com")
    resp = await client.post(
        f"/pipelines/{uuid.uuid4()}/steps",
        json={"name": "Orphan", "step_type": "source", "sort_order": 0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_step(client: AsyncClient):
    token, model_id = await setup_env(client, "pl_step_update@example.com")
    pl = await create_pipeline_api(client, token, model_id)
    step = await add_step_api(client, token, pl["id"])

    resp = await client.put(
        f"/steps/{step['id']}",
        json={"name": "Renamed Step", "step_type": "transform"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed Step"
    assert resp.json()["step_type"] == "transform"


@pytest.mark.asyncio
async def test_update_step_not_found(client: AsyncClient):
    token = await register_and_login(client, "pl_step_update_404@example.com")
    resp = await client.put(
        f"/steps/{uuid.uuid4()}",
        json={"name": "Ghost"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_step(client: AsyncClient):
    token, model_id = await setup_env(client, "pl_step_del@example.com")
    pl = await create_pipeline_api(client, token, model_id)
    step = await add_step_api(client, token, pl["id"])

    resp = await client.delete(
        f"/steps/{step['id']}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Reorder steps
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reorder_steps(client: AsyncClient):
    token, model_id = await setup_env(client, "pl_reorder@example.com")
    pl, steps = await create_full_pipeline(client, token, model_id)

    # Reverse the order
    resp = await client.post(
        f"/pipelines/{pl['id']}/steps/reorder",
        json={"steps": [
            {"step_id": steps[0]["id"], "sort_order": 2},
            {"step_id": steps[1]["id"], "sort_order": 1},
            {"step_id": steps[2]["id"], "sort_order": 0},
        ]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["sort_order"] == 0
    assert data[1]["sort_order"] == 1
    assert data[2]["sort_order"] == 2


@pytest.mark.asyncio
async def test_reorder_steps_invalid_step(client: AsyncClient):
    token, model_id = await setup_env(client, "pl_reorder_bad@example.com")
    pl = await create_pipeline_api(client, token, model_id)

    resp = await client.post(
        f"/pipelines/{pl['id']}/steps/reorder",
        json={"steps": [{"step_id": str(uuid.uuid4()), "sort_order": 0}]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Trigger pipeline run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trigger_run(client: AsyncClient):
    token, model_id = await setup_env(client, "pl_trigger@example.com")
    pl, steps = await create_full_pipeline(client, token, model_id)

    resp = await client.post(
        f"/pipelines/{pl['id']}/trigger",
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert data["total_steps"] == 3
    assert data["completed_steps"] == 0
    assert data["pipeline_id"] == pl["id"]


@pytest.mark.asyncio
async def test_trigger_run_no_steps(client: AsyncClient):
    token, model_id = await setup_env(client, "pl_trigger_empty@example.com")
    pl = await create_pipeline_api(client, token, model_id)

    resp = await client.post(
        f"/pipelines/{pl['id']}/trigger",
        headers=auth_headers(token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_trigger_inactive_pipeline(client: AsyncClient):
    token, model_id = await setup_env(client, "pl_trigger_inactive@example.com")
    pl, _ = await create_full_pipeline(client, token, model_id)

    # Deactivate
    await client.put(
        f"/pipelines/{pl['id']}",
        json={"is_active": False},
        headers=auth_headers(token),
    )

    resp = await client.post(
        f"/pipelines/{pl['id']}/trigger",
        headers=auth_headers(token),
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Run lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_runs(client: AsyncClient):
    token, model_id = await setup_env(client, "pl_list_runs@example.com")
    pl, _ = await create_full_pipeline(client, token, model_id)

    # Trigger twice
    await client.post(f"/pipelines/{pl['id']}/trigger", headers=auth_headers(token))
    await client.post(f"/pipelines/{pl['id']}/trigger", headers=auth_headers(token))

    resp = await client.get(
        f"/pipelines/{pl['id']}/runs",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_get_run_detail(client: AsyncClient):
    token, model_id = await setup_env(client, "pl_run_detail@example.com")
    pl, steps = await create_full_pipeline(client, token, model_id)

    trigger_resp = await client.post(
        f"/pipelines/{pl['id']}/trigger",
        headers=auth_headers(token),
    )
    run_id = trigger_resp.json()["id"]

    resp = await client.get(
        f"/pipeline-runs/{run_id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == run_id
    assert len(data["step_logs"]) == 3
    # All step logs should be pending initially
    for sl in data["step_logs"]:
        assert sl["status"] == "pending"


@pytest.mark.asyncio
async def test_get_run_not_found(client: AsyncClient):
    token = await register_and_login(client, "pl_run_404@example.com")
    resp = await client.get(
        f"/pipeline-runs/{uuid.uuid4()}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cancel_pending_run(client: AsyncClient):
    token, model_id = await setup_env(client, "pl_cancel_pending@example.com")
    pl, _ = await create_full_pipeline(client, token, model_id)

    trigger_resp = await client.post(
        f"/pipelines/{pl['id']}/trigger",
        headers=auth_headers(token),
    )
    run_id = trigger_resp.json()["id"]

    resp = await client.post(
        f"/pipeline-runs/{run_id}/cancel",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_run_marks_pending_logs_skipped(client: AsyncClient):
    token, model_id = await setup_env(client, "pl_cancel_logs@example.com")
    pl, _ = await create_full_pipeline(client, token, model_id)

    trigger_resp = await client.post(
        f"/pipelines/{pl['id']}/trigger",
        headers=auth_headers(token),
    )
    run_id = trigger_resp.json()["id"]

    # Cancel
    await client.post(
        f"/pipeline-runs/{run_id}/cancel",
        headers=auth_headers(token),
    )

    # Check step logs
    resp = await client.get(
        f"/pipeline-runs/{run_id}",
        headers=auth_headers(token),
    )
    data = resp.json()
    for sl in data["step_logs"]:
        assert sl["status"] == "skipped"


@pytest.mark.asyncio
async def test_cancel_completed_run_fails(client: AsyncClient):
    """Cannot cancel a run that is already completed."""
    token, model_id = await setup_env(client, "pl_cancel_done@example.com")
    pl, _ = await create_full_pipeline(client, token, model_id)

    trigger_resp = await client.post(
        f"/pipelines/{pl['id']}/trigger",
        headers=auth_headers(token),
    )
    run_id = trigger_resp.json()["id"]

    # Complete the run via service
    from app.core.database import get_db as original_get_db
    from app.services.pipeline import get_run_by_id, start_run, complete_run

    override_fn = app.dependency_overrides.get(original_get_db)
    async for db in override_fn():
        run = await get_run_by_id(db, uuid.UUID(run_id))
        await start_run(db, run)
        run = await get_run_by_id(db, uuid.UUID(run_id))
        await complete_run(db, run)
        break

    resp = await client.post(
        f"/pipeline-runs/{run_id}/cancel",
        headers=auth_headers(token),
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Run lifecycle via service layer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_start_and_complete_lifecycle(client: AsyncClient):
    """Test pending -> running -> completed lifecycle via service."""
    token, model_id = await setup_env(client, "pl_lifecycle@example.com")
    pl, _ = await create_full_pipeline(client, token, model_id)

    trigger_resp = await client.post(
        f"/pipelines/{pl['id']}/trigger",
        headers=auth_headers(token),
    )
    run_id = trigger_resp.json()["id"]

    from app.core.database import get_db as original_get_db
    from app.services.pipeline import get_run_by_id, start_run, complete_run

    override_fn = app.dependency_overrides.get(original_get_db)
    async for db in override_fn():
        run = await get_run_by_id(db, uuid.UUID(run_id))
        assert run.status.value == "pending"

        run = await start_run(db, run)
        assert run.status.value == "running"
        assert run.started_at is not None

        run = await complete_run(db, run)
        assert run.status.value == "completed"
        assert run.completed_at is not None
        break


@pytest.mark.asyncio
async def test_run_fail_lifecycle(client: AsyncClient):
    """Test pending -> running -> failed lifecycle via service."""
    token, model_id = await setup_env(client, "pl_fail@example.com")
    pl, steps = await create_full_pipeline(client, token, model_id)

    trigger_resp = await client.post(
        f"/pipelines/{pl['id']}/trigger",
        headers=auth_headers(token),
    )
    run_id = trigger_resp.json()["id"]

    from app.core.database import get_db as original_get_db
    from app.services.pipeline import get_run_by_id, start_run, fail_run

    override_fn = app.dependency_overrides.get(original_get_db)
    async for db in override_fn():
        run = await get_run_by_id(db, uuid.UUID(run_id))
        run = await start_run(db, run)
        run = await fail_run(
            db, run,
            error_step_id=uuid.UUID(steps[1]["id"]),
            error_message="Transform failed: bad column",
        )
        assert run.status.value == "failed"
        assert run.error_message == "Transform failed: bad column"
        assert str(run.error_step_id) == steps[1]["id"]
        break


@pytest.mark.asyncio
async def test_step_log_update(client: AsyncClient):
    """Test updating step log status via service."""
    token, model_id = await setup_env(client, "pl_steplog@example.com")
    pl, _ = await create_full_pipeline(client, token, model_id)

    trigger_resp = await client.post(
        f"/pipelines/{pl['id']}/trigger",
        headers=auth_headers(token),
    )
    run_id = trigger_resp.json()["id"]

    from app.core.database import get_db as original_get_db
    from app.services.pipeline import get_run_by_id, update_step_log_status
    from app.models.pipeline import StepLogStatus

    override_fn = app.dependency_overrides.get(original_get_db)
    async for db in override_fn():
        run = await get_run_by_id(db, uuid.UUID(run_id))
        log = run.step_logs[0]

        # Mark running
        log = await update_step_log_status(db, log, StepLogStatus.running)
        assert log.status == StepLogStatus.running
        assert log.started_at is not None

        # Mark completed
        log = await update_step_log_status(
            db, log, StepLogStatus.completed,
            records_in=100, records_out=95,
            log_output="Processed 100 rows, 5 filtered out",
        )
        assert log.status == StepLogStatus.completed
        assert log.records_in == 100
        assert log.records_out == 95
        assert log.completed_at is not None
        assert "Processed" in log.log_output
        break


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_valid_pipeline(client: AsyncClient):
    token, model_id = await setup_env(client, "pl_valid@example.com")
    pl, _ = await create_full_pipeline(client, token, model_id)

    resp = await client.get(
        f"/pipelines/{pl['id']}/validate",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["errors"] == []


@pytest.mark.asyncio
async def test_validate_empty_pipeline(client: AsyncClient):
    token, model_id = await setup_env(client, "pl_valid_empty@example.com")
    pl = await create_pipeline_api(client, token, model_id)

    resp = await client.get(
        f"/pipelines/{pl['id']}/validate",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is False
    assert "no steps" in data["errors"][0].lower()


@pytest.mark.asyncio
async def test_validate_missing_source(client: AsyncClient):
    token, model_id = await setup_env(client, "pl_valid_no_src@example.com")
    pl = await create_pipeline_api(client, token, model_id)
    await add_step_api(client, token, pl["id"], "Transform", "transform", 0)
    await add_step_api(client, token, pl["id"], "Publish", "publish", 1)

    resp = await client.get(
        f"/pipelines/{pl['id']}/validate",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is False
    assert any("source" in e.lower() for e in data["errors"])


@pytest.mark.asyncio
async def test_validate_missing_publish(client: AsyncClient):
    token, model_id = await setup_env(client, "pl_valid_no_pub@example.com")
    pl = await create_pipeline_api(client, token, model_id)
    await add_step_api(client, token, pl["id"], "Source", "source", 0)
    await add_step_api(client, token, pl["id"], "Transform", "transform", 1)

    resp = await client.get(
        f"/pipelines/{pl['id']}/validate",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is False
    assert any("publish" in e.lower() for e in data["errors"])


# ---------------------------------------------------------------------------
# Auth required
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_pipelines_requires_auth(client: AsyncClient):
    resp = await client.get(f"/models/{uuid.uuid4()}/pipelines")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_pipeline_requires_auth(client: AsyncClient):
    resp = await client.get(f"/pipelines/{uuid.uuid4()}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_pipeline_requires_auth(client: AsyncClient):
    resp = await client.put(f"/pipelines/{uuid.uuid4()}", json={"name": "x"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_pipeline_requires_auth(client: AsyncClient):
    resp = await client.delete(f"/pipelines/{uuid.uuid4()}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_add_step_requires_auth(client: AsyncClient):
    resp = await client.post(
        f"/pipelines/{uuid.uuid4()}/steps",
        json={"name": "x", "step_type": "source", "sort_order": 0},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_step_requires_auth(client: AsyncClient):
    resp = await client.put(f"/steps/{uuid.uuid4()}", json={"name": "x"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_step_requires_auth(client: AsyncClient):
    resp = await client.delete(f"/steps/{uuid.uuid4()}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_reorder_steps_requires_auth(client: AsyncClient):
    resp = await client.post(
        f"/pipelines/{uuid.uuid4()}/steps/reorder",
        json={"steps": []},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_trigger_run_requires_auth(client: AsyncClient):
    resp = await client.post(f"/pipelines/{uuid.uuid4()}/trigger")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_runs_requires_auth(client: AsyncClient):
    resp = await client.get(f"/pipelines/{uuid.uuid4()}/runs")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_run_requires_auth(client: AsyncClient):
    resp = await client.get(f"/pipeline-runs/{uuid.uuid4()}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_cancel_run_requires_auth(client: AsyncClient):
    resp = await client.post(f"/pipeline-runs/{uuid.uuid4()}/cancel")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_validate_pipeline_requires_auth(client: AsyncClient):
    resp = await client.get(f"/pipelines/{uuid.uuid4()}/validate")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Additional edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_pipeline_inactive(client: AsyncClient):
    token, model_id = await setup_env(client, "pl_inactive@example.com")
    resp = await client.post(
        f"/models/{model_id}/pipelines",
        json={"name": "Inactive PL", "is_active": False},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_all_step_types(client: AsyncClient):
    """All six step types can be created."""
    token, model_id = await setup_env(client, "pl_types@example.com")
    pl = await create_pipeline_api(client, token, model_id)
    step_types = ["source", "transform", "filter", "map", "aggregate", "publish"]
    for i, st in enumerate(step_types):
        step = await add_step_api(client, token, pl["id"], f"Step {st}", st, i)
        assert step["step_type"] == st


@pytest.mark.asyncio
async def test_delete_pipeline_cascades_steps(client: AsyncClient):
    """Deleting a pipeline removes its steps."""
    token, model_id = await setup_env(client, "pl_cascade@example.com")
    pl, steps = await create_full_pipeline(client, token, model_id)

    # Delete pipeline
    resp = await client.delete(
        f"/pipelines/{pl['id']}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 204

    # Steps should be gone
    for s in steps:
        resp = await client.put(
            f"/steps/{s['id']}",
            json={"name": "ghost"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_multiple_runs_independent(client: AsyncClient):
    """Multiple runs on the same pipeline are independent."""
    token, model_id = await setup_env(client, "pl_multi_run@example.com")
    pl, _ = await create_full_pipeline(client, token, model_id)

    r1 = await client.post(f"/pipelines/{pl['id']}/trigger", headers=auth_headers(token))
    r2 = await client.post(f"/pipelines/{pl['id']}/trigger", headers=auth_headers(token))
    assert r1.json()["id"] != r2.json()["id"]
    assert r1.json()["status"] == "pending"
    assert r2.json()["status"] == "pending"

    # Cancel one, the other should still be pending
    await client.post(f"/pipeline-runs/{r1.json()['id']}/cancel", headers=auth_headers(token))

    resp = await client.get(f"/pipeline-runs/{r2.json()['id']}", headers=auth_headers(token))
    assert resp.json()["status"] == "pending"


# ---------------------------------------------------------------------------
# Backpressure tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.backpressure
async def test_trigger_pipeline_run_burst_backpressure(client: AsyncClient):
    token, model_id = await setup_env(client, "pl_bp_runs@example.com")
    pipeline, _ = await create_full_pipeline(client, token, model_id, "Backpressure Pipeline")

    burst_size = 30
    run_ids = []
    for _ in range(burst_size):
        trigger_resp = await client.post(
            f"/pipelines/{pipeline['id']}/trigger",
            headers=auth_headers(token),
        )
        assert trigger_resp.status_code == 201
        run_data = trigger_resp.json()
        assert run_data["total_steps"] == 3
        run_ids.append(run_data["id"])

    assert len(set(run_ids)) == burst_size

    runs_resp = await client.get(
        f"/pipelines/{pipeline['id']}/runs",
        headers=auth_headers(token),
    )
    assert runs_resp.status_code == 200
    assert len(runs_resp.json()) == burst_size


@pytest.mark.asyncio
@pytest.mark.backpressure
async def test_validate_large_pipeline_backpressure(client: AsyncClient):
    token, model_id = await setup_env(client, "pl_bp_large@example.com")
    pipeline = await create_pipeline_api(client, token, model_id, "Large Validation Pipeline")

    step_count = 50
    await add_step_api(client, token, pipeline["id"], "Source", "source", 0)
    for idx in range(1, step_count - 1):
        await add_step_api(client, token, pipeline["id"], f"Transform {idx}", "transform", idx)
    await add_step_api(client, token, pipeline["id"], "Publish", "publish", step_count - 1)

    validate_resp = await client.get(
        f"/pipelines/{pipeline['id']}/validate",
        headers=auth_headers(token),
    )
    assert validate_resp.status_code == 200
    assert validate_resp.json()["valid"] is True

    trigger_resp = await client.post(
        f"/pipelines/{pipeline['id']}/trigger",
        headers=auth_headers(token),
    )
    assert trigger_resp.status_code == 201
    assert trigger_resp.json()["total_steps"] == step_count
