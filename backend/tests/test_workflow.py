"""
Tests for Feature F038: Workflow tasks and approvals.

Covers:
  - Workflow CRUD (create, list, get, update, delete)
  - Stage CRUD (create, update, delete)
  - Task CRUD and lifecycle (create, update, submit, approve, reject)
  - Status transitions and validation
  - Gate stage completion checks
  - Workflow activate/complete
  - Progress endpoint
  - Auth required for all endpoints
"""
import uuid

import pytest
from httpx import AsyncClient

# Import models so they are registered with Base.metadata before create_all.
from app.models.workflow import (  # noqa: F401
    Workflow,
    WorkflowApproval,
    WorkflowStage,
    WorkflowTask,
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


async def create_workflow_api(client, token, model_id, name="My Workflow"):
    resp = await client.post(
        f"/models/{model_id}/workflows",
        json={"name": name},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def create_stage_api(client, token, workflow_id, name="Stage 1", sort_order=0, is_gate=False):
    resp = await client.post(
        f"/workflows/{workflow_id}/stages",
        json={"name": name, "sort_order": sort_order, "is_gate": is_gate},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def create_task_api(client, token, stage_id, name="Task 1"):
    resp = await client.post(
        f"/stages/{stage_id}/tasks",
        json={"name": name},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Workflow CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_workflow(client: AsyncClient):
    token, model_id = await setup_env(client, "wf_create@example.com")
    resp = await client.post(
        f"/models/{model_id}/workflows",
        json={"name": "Q1 Planning", "description": "Quarterly cycle"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Q1 Planning"
    assert data["description"] == "Quarterly cycle"
    assert data["status"] == "draft"
    assert data["model_id"] == model_id


@pytest.mark.asyncio
async def test_create_workflow_requires_auth(client: AsyncClient):
    fake_model_id = str(uuid.uuid4())
    resp = await client.post(
        f"/models/{fake_model_id}/workflows",
        json={"name": "No auth"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_workflow_model_not_found(client: AsyncClient):
    token = await register_and_login(client, "wf_create_404@example.com")
    fake_model_id = str(uuid.uuid4())
    resp = await client.post(
        f"/models/{fake_model_id}/workflows",
        json={"name": "No model"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_workflows(client: AsyncClient):
    token, model_id = await setup_env(client, "wf_list@example.com")
    await create_workflow_api(client, token, model_id, "WF1")
    await create_workflow_api(client, token, model_id, "WF2")

    resp = await client.get(
        f"/models/{model_id}/workflows",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_list_workflows_empty(client: AsyncClient):
    token, model_id = await setup_env(client, "wf_list_empty@example.com")
    resp = await client.get(
        f"/models/{model_id}/workflows",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_workflow_detail(client: AsyncClient):
    token, model_id = await setup_env(client, "wf_detail@example.com")
    wf = await create_workflow_api(client, token, model_id)
    stage = await create_stage_api(client, token, wf["id"], "Review")
    await create_task_api(client, token, stage["id"], "Review budget")

    resp = await client.get(
        f"/workflows/{wf['id']}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "My Workflow"
    assert len(data["stages"]) == 1
    assert data["stages"][0]["name"] == "Review"
    assert len(data["stages"][0]["tasks"]) == 1


@pytest.mark.asyncio
async def test_get_workflow_not_found(client: AsyncClient):
    token = await register_and_login(client, "wf_get_404@example.com")
    resp = await client.get(
        f"/workflows/{uuid.uuid4()}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_workflow(client: AsyncClient):
    token, model_id = await setup_env(client, "wf_update@example.com")
    wf = await create_workflow_api(client, token, model_id)

    resp = await client.put(
        f"/workflows/{wf['id']}",
        json={"name": "Updated Name", "description": "New desc"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"
    assert resp.json()["description"] == "New desc"


@pytest.mark.asyncio
async def test_delete_workflow(client: AsyncClient):
    token, model_id = await setup_env(client, "wf_delete@example.com")
    wf = await create_workflow_api(client, token, model_id)

    resp = await client.delete(
        f"/workflows/{wf['id']}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 204

    resp2 = await client.get(
        f"/workflows/{wf['id']}",
        headers=auth_headers(token),
    )
    assert resp2.status_code == 404


# ---------------------------------------------------------------------------
# Stage CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_stage(client: AsyncClient):
    token, model_id = await setup_env(client, "wf_stage_create@example.com")
    wf = await create_workflow_api(client, token, model_id)

    resp = await client.post(
        f"/workflows/{wf['id']}/stages",
        json={"name": "Planning", "sort_order": 1, "is_gate": True},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Planning"
    assert data["sort_order"] == 1
    assert data["is_gate"] is True


@pytest.mark.asyncio
async def test_create_stage_workflow_not_found(client: AsyncClient):
    token = await register_and_login(client, "wf_stage_404@example.com")
    resp = await client.post(
        f"/workflows/{uuid.uuid4()}/stages",
        json={"name": "Orphan"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_stage(client: AsyncClient):
    token, model_id = await setup_env(client, "wf_stage_update@example.com")
    wf = await create_workflow_api(client, token, model_id)
    stage = await create_stage_api(client, token, wf["id"])

    resp = await client.put(
        f"/stages/{stage['id']}",
        json={"name": "Renamed Stage", "is_gate": True},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed Stage"
    assert resp.json()["is_gate"] is True


@pytest.mark.asyncio
async def test_delete_stage(client: AsyncClient):
    token, model_id = await setup_env(client, "wf_stage_del@example.com")
    wf = await create_workflow_api(client, token, model_id)
    stage = await create_stage_api(client, token, wf["id"])

    resp = await client.delete(
        f"/stages/{stage['id']}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Task CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_task(client: AsyncClient):
    token, model_id = await setup_env(client, "wf_task_create@example.com")
    wf = await create_workflow_api(client, token, model_id)
    stage = await create_stage_api(client, token, wf["id"])

    resp = await client.post(
        f"/stages/{stage['id']}/tasks",
        json={"name": "Fill in numbers", "description": "Complete the budget"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Fill in numbers"
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_create_task_stage_not_found(client: AsyncClient):
    token = await register_and_login(client, "wf_task_404@example.com")
    resp = await client.post(
        f"/stages/{uuid.uuid4()}/tasks",
        json={"name": "Orphan"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_task(client: AsyncClient):
    token, model_id = await setup_env(client, "wf_task_update@example.com")
    wf = await create_workflow_api(client, token, model_id)
    stage = await create_stage_api(client, token, wf["id"])
    task = await create_task_api(client, token, stage["id"])

    resp = await client.put(
        f"/tasks/{task['id']}",
        json={"name": "Updated Task"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Task"


# ---------------------------------------------------------------------------
# Task lifecycle: submit -> approve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_submit_requires_in_progress(client: AsyncClient):
    """Cannot submit a pending task directly; must be in_progress first."""
    token, model_id = await setup_env(client, "wf_submit_bad@example.com")
    wf = await create_workflow_api(client, token, model_id)
    stage = await create_stage_api(client, token, wf["id"])
    task = await create_task_api(client, token, stage["id"])

    # Task is pending, submit should fail
    resp = await client.post(
        f"/tasks/{task['id']}/submit",
        headers=auth_headers(token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_task_full_approve_lifecycle(client: AsyncClient):
    """pending -> in_progress (via update is not a status transition, need service).
    Actually the submit endpoint uses transition, let's test full flow via service calls."""
    token, model_id = await setup_env(client, "wf_lifecycle@example.com")
    wf = await create_workflow_api(client, token, model_id)
    stage = await create_stage_api(client, token, wf["id"])
    task = await create_task_api(client, token, stage["id"])

    # We need to transition pending -> in_progress first via the service
    # Since there's no direct endpoint for start, let's use the service layer
    from app.core.database import get_db as original_get_db
    from app.main import app
    from app.services.workflow import get_task_by_id, transition_task_status
    from app.models.workflow import TaskStatus

    override_fn = app.dependency_overrides.get(original_get_db)
    assert override_fn is not None

    async for db in override_fn():
        task_obj = await get_task_by_id(db, uuid.UUID(task["id"]))
        assert task_obj is not None
        # pending -> in_progress
        await transition_task_status(db, task_obj, TaskStatus.in_progress)
        break

    # Now submit via API
    resp = await client.post(
        f"/tasks/{task['id']}/submit",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "submitted"

    # Approve
    resp = await client.post(
        f"/tasks/{task['id']}/approve",
        json={"comment": "Looks good"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    assert resp.json()["completed_at"] is not None


@pytest.mark.asyncio
async def test_task_full_reject_lifecycle(client: AsyncClient):
    """Test pending -> in_progress -> submitted -> rejected flow."""
    token, model_id = await setup_env(client, "wf_reject@example.com")
    wf = await create_workflow_api(client, token, model_id)
    stage = await create_stage_api(client, token, wf["id"])
    task = await create_task_api(client, token, stage["id"])

    from app.core.database import get_db as original_get_db
    from app.main import app
    from app.services.workflow import get_task_by_id, transition_task_status
    from app.models.workflow import TaskStatus

    override_fn = app.dependency_overrides.get(original_get_db)
    async for db in override_fn():
        task_obj = await get_task_by_id(db, uuid.UUID(task["id"]))
        await transition_task_status(db, task_obj, TaskStatus.in_progress)
        break

    # Submit
    resp = await client.post(
        f"/tasks/{task['id']}/submit",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200

    # Reject
    resp = await client.post(
        f"/tasks/{task['id']}/reject",
        json={"comment": "Needs more detail"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_approve_non_submitted_task_fails(client: AsyncClient):
    """Cannot approve a task that isn't submitted."""
    token, model_id = await setup_env(client, "wf_approve_bad@example.com")
    wf = await create_workflow_api(client, token, model_id)
    stage = await create_stage_api(client, token, wf["id"])
    task = await create_task_api(client, token, stage["id"])

    resp = await client.post(
        f"/tasks/{task['id']}/approve",
        headers=auth_headers(token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reject_non_submitted_task_fails(client: AsyncClient):
    """Cannot reject a task that isn't submitted."""
    token, model_id = await setup_env(client, "wf_reject_bad@example.com")
    wf = await create_workflow_api(client, token, model_id)
    stage = await create_stage_api(client, token, wf["id"])
    task = await create_task_api(client, token, stage["id"])

    resp = await client.post(
        f"/tasks/{task['id']}/reject",
        headers=auth_headers(token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_cannot_approve_already_approved_task(client: AsyncClient):
    """Double approval is not allowed."""
    token, model_id = await setup_env(client, "wf_double_approve@example.com")
    wf = await create_workflow_api(client, token, model_id)
    stage = await create_stage_api(client, token, wf["id"])
    task = await create_task_api(client, token, stage["id"])

    from app.core.database import get_db as original_get_db
    from app.main import app
    from app.services.workflow import get_task_by_id, transition_task_status
    from app.models.workflow import TaskStatus

    override_fn = app.dependency_overrides.get(original_get_db)
    async for db in override_fn():
        task_obj = await get_task_by_id(db, uuid.UUID(task["id"]))
        await transition_task_status(db, task_obj, TaskStatus.in_progress)
        break

    await client.post(f"/tasks/{task['id']}/submit", headers=auth_headers(token))
    await client.post(f"/tasks/{task['id']}/approve", headers=auth_headers(token))

    # Second approve should fail
    resp = await client.post(f"/tasks/{task['id']}/approve", headers=auth_headers(token))
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Rejected -> resubmit flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rejected_task_can_be_resubmitted(client: AsyncClient):
    """rejected -> in_progress -> submitted -> approved."""
    token, model_id = await setup_env(client, "wf_resubmit@example.com")
    wf = await create_workflow_api(client, token, model_id)
    stage = await create_stage_api(client, token, wf["id"])
    task = await create_task_api(client, token, stage["id"])

    from app.core.database import get_db as original_get_db
    from app.main import app
    from app.services.workflow import get_task_by_id, transition_task_status
    from app.models.workflow import TaskStatus

    override_fn = app.dependency_overrides.get(original_get_db)

    # pending -> in_progress
    async for db in override_fn():
        task_obj = await get_task_by_id(db, uuid.UUID(task["id"]))
        await transition_task_status(db, task_obj, TaskStatus.in_progress)
        break

    # submit
    await client.post(f"/tasks/{task['id']}/submit", headers=auth_headers(token))
    # reject
    await client.post(
        f"/tasks/{task['id']}/reject",
        json={"comment": "Fix it"},
        headers=auth_headers(token),
    )

    # rejected -> in_progress
    async for db in override_fn():
        task_obj = await get_task_by_id(db, uuid.UUID(task["id"]))
        await transition_task_status(db, task_obj, TaskStatus.in_progress)
        break

    # submit again
    resp = await client.post(f"/tasks/{task['id']}/submit", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "submitted"

    # approve
    resp = await client.post(f"/tasks/{task['id']}/approve", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


# ---------------------------------------------------------------------------
# Workflow activate / complete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activate_workflow(client: AsyncClient):
    token, model_id = await setup_env(client, "wf_activate@example.com")
    wf = await create_workflow_api(client, token, model_id)

    resp = await client.post(
        f"/workflows/{wf['id']}/activate",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


@pytest.mark.asyncio
async def test_activate_non_draft_fails(client: AsyncClient):
    token, model_id = await setup_env(client, "wf_activate_bad@example.com")
    wf = await create_workflow_api(client, token, model_id)

    # Activate once
    await client.post(f"/workflows/{wf['id']}/activate", headers=auth_headers(token))
    # Try to activate again
    resp = await client.post(f"/workflows/{wf['id']}/activate", headers=auth_headers(token))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_complete_workflow(client: AsyncClient):
    token, model_id = await setup_env(client, "wf_complete@example.com")
    wf = await create_workflow_api(client, token, model_id)

    # Activate first
    await client.post(f"/workflows/{wf['id']}/activate", headers=auth_headers(token))

    resp = await client.post(
        f"/workflows/{wf['id']}/complete",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_complete_draft_fails(client: AsyncClient):
    token, model_id = await setup_env(client, "wf_complete_bad@example.com")
    wf = await create_workflow_api(client, token, model_id)

    resp = await client.post(
        f"/workflows/{wf['id']}/complete",
        headers=auth_headers(token),
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workflow_progress(client: AsyncClient):
    token, model_id = await setup_env(client, "wf_progress@example.com")
    wf = await create_workflow_api(client, token, model_id)
    stage = await create_stage_api(client, token, wf["id"], is_gate=True)
    await create_task_api(client, token, stage["id"], "Task A")
    await create_task_api(client, token, stage["id"], "Task B")

    resp = await client.get(
        f"/workflows/{wf['id']}/progress",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_stages"] == 1
    assert data["total_tasks"] == 2
    assert data["tasks_by_status"]["pending"] == 2
    assert data["gate_stages_total"] == 1
    assert data["gate_stages_completed"] == 0


@pytest.mark.asyncio
async def test_workflow_progress_not_found(client: AsyncClient):
    token = await register_and_login(client, "wf_progress_404@example.com")
    resp = await client.get(
        f"/workflows/{uuid.uuid4()}/progress",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Gate stage completion check (via service)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gate_stage_completed(client: AsyncClient):
    """Gate stage is completed when all tasks are approved."""
    token, model_id = await setup_env(client, "wf_gate@example.com")
    wf = await create_workflow_api(client, token, model_id)
    stage = await create_stage_api(client, token, wf["id"], is_gate=True)
    task = await create_task_api(client, token, stage["id"])

    from app.core.database import get_db as original_get_db
    from app.main import app
    from app.services.workflow import (
        get_stage_by_id,
        get_task_by_id,
        is_gate_stage_completed,
        transition_task_status,
    )
    from app.models.workflow import TaskStatus

    override_fn = app.dependency_overrides.get(original_get_db)

    # Move task through lifecycle
    async for db in override_fn():
        task_obj = await get_task_by_id(db, uuid.UUID(task["id"]))
        await transition_task_status(db, task_obj, TaskStatus.in_progress)
        break

    await client.post(f"/tasks/{task['id']}/submit", headers=auth_headers(token))
    await client.post(f"/tasks/{task['id']}/approve", headers=auth_headers(token))

    # Check gate completion
    async for db in override_fn():
        stage_obj = await get_stage_by_id(db, uuid.UUID(stage["id"]))
        assert stage_obj is not None
        result = await is_gate_stage_completed(db, stage_obj)
        assert result is True
        break


@pytest.mark.asyncio
async def test_gate_stage_not_completed_with_pending_tasks(client: AsyncClient):
    """Gate stage is not completed if any task is not approved."""
    token, model_id = await setup_env(client, "wf_gate_pending@example.com")
    wf = await create_workflow_api(client, token, model_id)
    stage = await create_stage_api(client, token, wf["id"], is_gate=True)
    await create_task_api(client, token, stage["id"], "Task A")
    await create_task_api(client, token, stage["id"], "Task B")

    from app.core.database import get_db as original_get_db
    from app.main import app
    from app.services.workflow import get_stage_by_id, is_gate_stage_completed

    override_fn = app.dependency_overrides.get(original_get_db)

    async for db in override_fn():
        stage_obj = await get_stage_by_id(db, uuid.UUID(stage["id"]))
        result = await is_gate_stage_completed(db, stage_obj)
        assert result is False
        break


@pytest.mark.asyncio
async def test_gate_stage_empty_not_completed(client: AsyncClient):
    """Gate stage with no tasks is not considered completed."""
    token, model_id = await setup_env(client, "wf_gate_empty@example.com")
    wf = await create_workflow_api(client, token, model_id)
    stage = await create_stage_api(client, token, wf["id"], is_gate=True)

    from app.core.database import get_db as original_get_db
    from app.main import app
    from app.services.workflow import get_stage_by_id, is_gate_stage_completed

    override_fn = app.dependency_overrides.get(original_get_db)

    async for db in override_fn():
        stage_obj = await get_stage_by_id(db, uuid.UUID(stage["id"]))
        result = await is_gate_stage_completed(db, stage_obj)
        assert result is False
        break


@pytest.mark.asyncio
async def test_non_gate_stage_returns_false(client: AsyncClient):
    """is_gate_stage_completed returns False for non-gate stages."""
    token, model_id = await setup_env(client, "wf_nongate@example.com")
    wf = await create_workflow_api(client, token, model_id)
    stage = await create_stage_api(client, token, wf["id"], is_gate=False)

    from app.core.database import get_db as original_get_db
    from app.main import app
    from app.services.workflow import get_stage_by_id, is_gate_stage_completed

    override_fn = app.dependency_overrides.get(original_get_db)

    async for db in override_fn():
        stage_obj = await get_stage_by_id(db, uuid.UUID(stage["id"]))
        result = await is_gate_stage_completed(db, stage_obj)
        assert result is False
        break


# ---------------------------------------------------------------------------
# Auth on all endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_workflows_requires_auth(client: AsyncClient):
    resp = await client.get(f"/models/{uuid.uuid4()}/workflows")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_workflow_requires_auth(client: AsyncClient):
    resp = await client.get(f"/workflows/{uuid.uuid4()}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_workflow_requires_auth(client: AsyncClient):
    resp = await client.put(f"/workflows/{uuid.uuid4()}", json={"name": "x"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_workflow_requires_auth(client: AsyncClient):
    resp = await client.delete(f"/workflows/{uuid.uuid4()}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_stage_requires_auth(client: AsyncClient):
    resp = await client.post(f"/workflows/{uuid.uuid4()}/stages", json={"name": "x"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_stage_requires_auth(client: AsyncClient):
    resp = await client.put(f"/stages/{uuid.uuid4()}", json={"name": "x"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_stage_requires_auth(client: AsyncClient):
    resp = await client.delete(f"/stages/{uuid.uuid4()}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_task_requires_auth(client: AsyncClient):
    resp = await client.post(f"/stages/{uuid.uuid4()}/tasks", json={"name": "x"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_task_requires_auth(client: AsyncClient):
    resp = await client.put(f"/tasks/{uuid.uuid4()}", json={"name": "x"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_submit_task_requires_auth(client: AsyncClient):
    resp = await client.post(f"/tasks/{uuid.uuid4()}/submit")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_approve_task_requires_auth(client: AsyncClient):
    resp = await client.post(f"/tasks/{uuid.uuid4()}/approve")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_reject_task_requires_auth(client: AsyncClient):
    resp = await client.post(f"/tasks/{uuid.uuid4()}/reject")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_activate_workflow_requires_auth(client: AsyncClient):
    resp = await client.post(f"/workflows/{uuid.uuid4()}/activate")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_complete_workflow_requires_auth(client: AsyncClient):
    resp = await client.post(f"/workflows/{uuid.uuid4()}/complete")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_progress_requires_auth(client: AsyncClient):
    resp = await client.get(f"/workflows/{uuid.uuid4()}/progress")
    assert resp.status_code == 401
