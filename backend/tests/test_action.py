import asyncio
import uuid

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


async def create_model(client: AsyncClient, token: str, workspace_id: str, name: str = "Test Model") -> str:
    resp = await client.post(
        "/models",
        json={"name": name, "workspace_id": workspace_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_action(
    client: AsyncClient,
    token: str,
    model_id: str,
    name: str = "My Action",
    action_type: str = "import_data",
    config: dict = None,
) -> dict:
    payload = {"name": name, "action_type": action_type}
    if config is not None:
        payload["config"] = config
    resp = await client.post(
        f"/models/{model_id}/actions",
        json=payload,
        headers=auth_headers(token),
    )
    return resp


async def create_process(
    client: AsyncClient,
    token: str,
    model_id: str,
    name: str = "My Process",
    description: str = None,
) -> dict:
    payload = {"name": name}
    if description is not None:
        payload["description"] = description
    resp = await client.post(
        f"/models/{model_id}/processes",
        json=payload,
        headers=auth_headers(token),
    )
    return resp


async def create_runnable_process(
    client: AsyncClient,
    token: str,
    model_id: str,
    *,
    step_count: int = 1,
    name: str = "Runnable Process",
) -> str:
    """Create a process with deterministic ordered steps for run stress tests."""
    process_resp = await create_process(client, token, model_id, name=name)
    assert process_resp.status_code == 201
    process_id = process_resp.json()["id"]

    for index in range(step_count):
        action_resp = await create_action(
            client,
            token,
            model_id,
            name=f"{name} Action {index + 1}",
            action_type="import_data",
            config={
                "file_path": f"/tmp/{name.lower().replace(' ', '_')}_{index + 1}.csv",
                "source_module_id": f"mod-{index + 1}",
            },
        )
        assert action_resp.status_code == 201
        action_id = action_resp.json()["id"]

        step_resp = await client.post(
            f"/processes/{process_id}/steps",
            json={"action_id": action_id, "step_order": index + 1},
            headers=auth_headers(token),
        )
        assert step_resp.status_code == 201

    return process_id


# ---------------------------------------------------------------------------
# Action CRUD tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_action_import(client: AsyncClient):
    token = await register_and_login(client, "act_import@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await create_action(
        client, token, model_id,
        name="Import Revenue",
        action_type="import_data",
        config={"file_path": "/data/revenue.csv", "source_module_id": "mod-123"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Import Revenue"
    assert data["action_type"] == "import_data"
    assert data["model_id"] == model_id
    assert data["config"]["file_path"] == "/data/revenue.csv"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_action_export(client: AsyncClient):
    token = await register_and_login(client, "act_export@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await create_action(client, token, model_id, name="Export Data", action_type="export_data")
    assert resp.status_code == 201
    assert resp.json()["action_type"] == "export_data"


@pytest.mark.asyncio
async def test_create_action_delete(client: AsyncClient):
    token = await register_and_login(client, "act_delete@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await create_action(client, token, model_id, name="Delete Old Data", action_type="delete_data")
    assert resp.status_code == 201
    assert resp.json()["action_type"] == "delete_data"


@pytest.mark.asyncio
async def test_create_action_run_formula(client: AsyncClient):
    token = await register_and_login(client, "act_formula@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await create_action(client, token, model_id, name="Recalc Formulas", action_type="run_formula")
    assert resp.status_code == 201
    assert resp.json()["action_type"] == "run_formula"


@pytest.mark.asyncio
async def test_create_action_copy_data(client: AsyncClient):
    token = await register_and_login(client, "act_copy@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await create_action(
        client, token, model_id,
        name="Copy Budget",
        action_type="copy_data",
        config={"source_module_id": "mod-A", "target_module_id": "mod-B"},
    )
    assert resp.status_code == 201
    assert resp.json()["action_type"] == "copy_data"


@pytest.mark.asyncio
async def test_list_actions(client: AsyncClient):
    token = await register_and_login(client, "act_list@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    await create_action(client, token, model_id, name="Action A", action_type="import_data")
    await create_action(client, token, model_id, name="Action B", action_type="export_data")

    resp = await client.get(f"/models/{model_id}/actions", headers=auth_headers(token))
    assert resp.status_code == 200
    names = [a["name"] for a in resp.json()]
    assert "Action A" in names
    assert "Action B" in names


@pytest.mark.asyncio
async def test_update_action(client: AsyncClient):
    token = await register_and_login(client, "act_update@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    create_resp = await create_action(client, token, model_id, name="Old Name", action_type="import_data")
    action_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/actions/{action_id}",
        json={"name": "New Name", "action_type": "export_data"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "New Name"
    assert data["action_type"] == "export_data"


@pytest.mark.asyncio
async def test_delete_action(client: AsyncClient):
    token = await register_and_login(client, "act_del@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    create_resp = await create_action(client, token, model_id, name="Delete Me", action_type="delete_data")
    action_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/actions/{action_id}", headers=auth_headers(token))
    assert del_resp.status_code == 204

    # Verify it's gone from the list
    list_resp = await client.get(f"/models/{model_id}/actions", headers=auth_headers(token))
    ids = [a["id"] for a in list_resp.json()]
    assert action_id not in ids


@pytest.mark.asyncio
async def test_delete_action_404(client: AsyncClient):
    token = await register_and_login(client, "act_del404@example.com")

    resp = await client.delete(f"/actions/{uuid.uuid4()}", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_action_requires_auth(client: AsyncClient):
    fake_model_id = str(uuid.uuid4())
    resp = await client.post(
        f"/models/{fake_model_id}/actions",
        json={"name": "Unauthorized", "action_type": "import_data"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_actions_requires_auth(client: AsyncClient):
    fake_model_id = str(uuid.uuid4())
    resp = await client.get(f"/models/{fake_model_id}/actions")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Process CRUD tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_process(client: AsyncClient):
    token = await register_and_login(client, "proc_create@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await create_process(
        client, token, model_id,
        name="Month-End Process",
        description="Runs all month-end actions",
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Month-End Process"
    assert data["description"] == "Runs all month-end actions"
    assert data["model_id"] == model_id
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_list_processes(client: AsyncClient):
    token = await register_and_login(client, "proc_list@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    await create_process(client, token, model_id, name="Process Alpha")
    await create_process(client, token, model_id, name="Process Beta")

    resp = await client.get(f"/models/{model_id}/processes", headers=auth_headers(token))
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "Process Alpha" in names
    assert "Process Beta" in names


@pytest.mark.asyncio
async def test_get_process_with_steps(client: AsyncClient):
    token = await register_and_login(client, "proc_get@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    proc_resp = await create_process(client, token, model_id, name="Detailed Process")
    process_id = proc_resp.json()["id"]

    resp = await client.get(f"/processes/{process_id}", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == process_id
    assert data["name"] == "Detailed Process"
    assert "steps" in data
    assert data["steps"] == []


@pytest.mark.asyncio
async def test_get_process_404(client: AsyncClient):
    token = await register_and_login(client, "proc_404@example.com")
    resp = await client.get(f"/processes/{uuid.uuid4()}", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_process_requires_auth(client: AsyncClient):
    fake_model_id = str(uuid.uuid4())
    resp = await client.post(
        f"/models/{fake_model_id}/processes",
        json={"name": "Unauthorized"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# ProcessStep tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_and_remove_process_step(client: AsyncClient):
    token = await register_and_login(client, "step_add@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    action_resp = await create_action(client, token, model_id, name="Step Action", action_type="import_data")
    action_id = action_resp.json()["id"]

    proc_resp = await create_process(client, token, model_id, name="Step Process")
    process_id = proc_resp.json()["id"]

    # Add step
    step_resp = await client.post(
        f"/processes/{process_id}/steps",
        json={"action_id": action_id, "step_order": 1},
        headers=auth_headers(token),
    )
    assert step_resp.status_code == 201
    step_data = step_resp.json()
    assert step_data["action_id"] == action_id
    assert step_data["step_order"] == 1
    assert step_data["process_id"] == process_id
    step_id = step_data["id"]

    # Verify step appears in process
    get_resp = await client.get(f"/processes/{process_id}", headers=auth_headers(token))
    steps = get_resp.json()["steps"]
    assert len(steps) == 1
    assert steps[0]["id"] == step_id

    # Remove step
    del_resp = await client.delete(f"/process-steps/{step_id}", headers=auth_headers(token))
    assert del_resp.status_code == 204

    # Verify step is gone
    get_resp2 = await client.get(f"/processes/{process_id}", headers=auth_headers(token))
    assert get_resp2.json()["steps"] == []


@pytest.mark.asyncio
async def test_step_ordering(client: AsyncClient):
    token = await register_and_login(client, "step_order@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    action1_resp = await create_action(client, token, model_id, name="Action 1", action_type="import_data")
    action2_resp = await create_action(client, token, model_id, name="Action 2", action_type="export_data")
    action3_resp = await create_action(client, token, model_id, name="Action 3", action_type="copy_data")

    action1_id = action1_resp.json()["id"]
    action2_id = action2_resp.json()["id"]
    action3_id = action3_resp.json()["id"]

    proc_resp = await create_process(client, token, model_id, name="Ordered Process")
    process_id = proc_resp.json()["id"]

    # Add steps out of order to verify ordering
    await client.post(
        f"/processes/{process_id}/steps",
        json={"action_id": action3_id, "step_order": 3},
        headers=auth_headers(token),
    )
    await client.post(
        f"/processes/{process_id}/steps",
        json={"action_id": action1_id, "step_order": 1},
        headers=auth_headers(token),
    )
    await client.post(
        f"/processes/{process_id}/steps",
        json={"action_id": action2_id, "step_order": 2},
        headers=auth_headers(token),
    )

    get_resp = await client.get(f"/processes/{process_id}", headers=auth_headers(token))
    steps = get_resp.json()["steps"]
    assert len(steps) == 3
    orders = [s["step_order"] for s in steps]
    assert orders == sorted(orders)


@pytest.mark.asyncio
async def test_remove_step_404(client: AsyncClient):
    token = await register_and_login(client, "step_del404@example.com")
    resp = await client.delete(f"/process-steps/{uuid.uuid4()}", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_add_step_process_not_found(client: AsyncClient):
    token = await register_and_login(client, "step_proc404@example.com")
    resp = await client.post(
        f"/processes/{uuid.uuid4()}/steps",
        json={"action_id": str(uuid.uuid4()), "step_order": 1},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Process run tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_process_creates_run(client: AsyncClient):
    token = await register_and_login(client, "run_create@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    action_resp = await create_action(client, token, model_id, name="Run Action", action_type="import_data")
    action_id = action_resp.json()["id"]

    proc_resp = await create_process(client, token, model_id, name="Runnable Process")
    process_id = proc_resp.json()["id"]

    await client.post(
        f"/processes/{process_id}/steps",
        json={"action_id": action_id, "step_order": 1},
        headers=auth_headers(token),
    )

    run_resp = await client.post(f"/processes/{process_id}/run", headers=auth_headers(token))
    assert run_resp.status_code == 201
    run_data = run_resp.json()
    assert run_data["process_id"] == process_id
    assert run_data["status"] == "completed"
    assert run_data["started_at"] is not None
    assert run_data["completed_at"] is not None
    assert run_data["result"] is not None
    assert "steps" in run_data["result"]


@pytest.mark.asyncio
async def test_run_process_records_step_results(client: AsyncClient):
    token = await register_and_login(client, "run_steps@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    action_resp = await create_action(
        client, token, model_id,
        name="Copy Action",
        action_type="copy_data",
        config={"source_module_id": "src", "target_module_id": "tgt"},
    )
    action_id = action_resp.json()["id"]

    proc_resp = await create_process(client, token, model_id, name="Copy Process")
    process_id = proc_resp.json()["id"]

    await client.post(
        f"/processes/{process_id}/steps",
        json={"action_id": action_id, "step_order": 1},
        headers=auth_headers(token),
    )

    run_resp = await client.post(f"/processes/{process_id}/run", headers=auth_headers(token))
    assert run_resp.status_code == 201
    run_data = run_resp.json()
    steps = run_data["result"]["steps"]
    assert len(steps) == 1
    assert steps[0]["action_id"] == action_id
    assert steps[0]["step_order"] == 1


@pytest.mark.asyncio
async def test_run_process_empty_steps(client: AsyncClient):
    """Running a process with no steps should still complete successfully."""
    token = await register_and_login(client, "run_empty@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    proc_resp = await create_process(client, token, model_id, name="Empty Process")
    process_id = proc_resp.json()["id"]

    run_resp = await client.post(f"/processes/{process_id}/run", headers=auth_headers(token))
    assert run_resp.status_code == 201
    run_data = run_resp.json()
    assert run_data["status"] == "completed"
    assert run_data["result"]["steps"] == []


@pytest.mark.asyncio
async def test_run_process_404(client: AsyncClient):
    token = await register_and_login(client, "run_404@example.com")
    resp = await client.post(f"/processes/{uuid.uuid4()}/run", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_run_process_requires_auth(client: AsyncClient):
    resp = await client.post(f"/processes/{uuid.uuid4()}/run")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Run history tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_run_history(client: AsyncClient):
    token = await register_and_login(client, "hist_list@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    proc_resp = await create_process(client, token, model_id, name="History Process")
    process_id = proc_resp.json()["id"]

    # Run process twice
    await client.post(f"/processes/{process_id}/run", headers=auth_headers(token))
    await client.post(f"/processes/{process_id}/run", headers=auth_headers(token))

    hist_resp = await client.get(f"/processes/{process_id}/runs", headers=auth_headers(token))
    assert hist_resp.status_code == 200
    runs = hist_resp.json()
    assert len(runs) == 2
    for run in runs:
        assert run["process_id"] == process_id
        assert run["status"] == "completed"


@pytest.mark.asyncio
async def test_run_history_empty(client: AsyncClient):
    token = await register_and_login(client, "hist_empty@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    proc_resp = await create_process(client, token, model_id, name="No Runs Process")
    process_id = proc_resp.json()["id"]

    hist_resp = await client.get(f"/processes/{process_id}/runs", headers=auth_headers(token))
    assert hist_resp.status_code == 200
    assert hist_resp.json() == []


@pytest.mark.asyncio
async def test_run_history_404(client: AsyncClient):
    token = await register_and_login(client, "hist_404@example.com")
    resp = await client.get(f"/processes/{uuid.uuid4()}/runs", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_run_history_requires_auth(client: AsyncClient):
    resp = await client.get(f"/processes/{uuid.uuid4()}/runs")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Multi-step run ordering verification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_executes_steps_in_order(client: AsyncClient):
    token = await register_and_login(client, "run_order@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    a1 = (await create_action(client, token, model_id, name="Step 1 Action", action_type="import_data")).json()["id"]
    a2 = (await create_action(client, token, model_id, name="Step 2 Action", action_type="run_formula")).json()["id"]
    a3 = (await create_action(client, token, model_id, name="Step 3 Action", action_type="export_data")).json()["id"]

    proc_resp = await create_process(client, token, model_id, name="Ordered Run Process")
    process_id = proc_resp.json()["id"]

    # Add steps in reverse order
    await client.post(f"/processes/{process_id}/steps", json={"action_id": a3, "step_order": 3}, headers=auth_headers(token))
    await client.post(f"/processes/{process_id}/steps", json={"action_id": a1, "step_order": 1}, headers=auth_headers(token))
    await client.post(f"/processes/{process_id}/steps", json={"action_id": a2, "step_order": 2}, headers=auth_headers(token))

    run_resp = await client.post(f"/processes/{process_id}/run", headers=auth_headers(token))
    assert run_resp.status_code == 201
    steps = run_resp.json()["result"]["steps"]
    assert len(steps) == 3
    executed_orders = [s["step_order"] for s in steps]
    assert executed_orders == [1, 2, 3]


# ---------------------------------------------------------------------------
# Backpressure tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.backpressure
async def test_run_process_burst_backpressure(client: AsyncClient):
    token = await register_and_login(client, "run_burst_backpressure@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    process_id = await create_runnable_process(
        client,
        token,
        model_id,
        step_count=1,
        name="Burst Backpressure Process",
    )

    burst_size = 30
    run_ids = []
    for _ in range(burst_size):
        run_resp = await client.post(f"/processes/{process_id}/run", headers=auth_headers(token))
        assert run_resp.status_code == 201
        run_data = run_resp.json()
        assert run_data["status"] == "completed"
        run_ids.append(run_data["id"])

    assert len(set(run_ids)) == burst_size

    history_resp = await client.get(f"/processes/{process_id}/runs", headers=auth_headers(token))
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert len(history) == burst_size
    assert all(run["status"] == "completed" for run in history)


@pytest.mark.asyncio
@pytest.mark.backpressure
async def test_run_process_concurrent_backpressure(client: AsyncClient):
    token = await register_and_login(client, "run_concurrent_backpressure@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    process_id = await create_runnable_process(
        client,
        token,
        model_id,
        step_count=2,
        name="Concurrent Backpressure Process",
    )

    async def trigger_run() -> dict:
        resp = await client.post(f"/processes/{process_id}/run", headers=auth_headers(token))
        assert resp.status_code == 201
        return resp.json()

    concurrent_runs = 8
    runs = await asyncio.gather(*[trigger_run() for _ in range(concurrent_runs)])
    run_ids = [r["id"] for r in runs]
    assert len(set(run_ids)) == concurrent_runs
    assert all(r["status"] == "completed" for r in runs)

    history_resp = await client.get(f"/processes/{process_id}/runs", headers=auth_headers(token))
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert len(history) == concurrent_runs


@pytest.mark.asyncio
@pytest.mark.backpressure
async def test_run_process_many_steps_backpressure(client: AsyncClient):
    token = await register_and_login(client, "run_many_steps_backpressure@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    step_count = 40
    process_id = await create_runnable_process(
        client,
        token,
        model_id,
        step_count=step_count,
        name="Many Steps Backpressure Process",
    )

    run_resp = await client.post(f"/processes/{process_id}/run", headers=auth_headers(token))
    assert run_resp.status_code == 201
    run_data = run_resp.json()
    assert run_data["status"] == "completed"

    steps = run_data["result"]["steps"]
    assert len(steps) == step_count
    assert [step["step_order"] for step in steps] == list(range(1, step_count + 1))
