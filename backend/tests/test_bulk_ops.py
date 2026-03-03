"""
Tests for F032: Bulk data operations.

Covers:
- Bulk write cells (small batch)
- Bulk write with chunking (verify progress updates)
- Bulk read with pagination (limit/offset)
- Bulk read with line_item filter
- Bulk delete cells
- Job creation and status tracking
- Job progress (processed_rows increments)
- Cancel pending job
- Cannot cancel completed job
- List jobs with status filter
- Bulk copy between models
- Auth required on all endpoints
- 404 for nonexistent model/job
- Empty bulk operations (no cells)
- Failed rows handling
- Job completion summary
"""

import uuid

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def register_and_login(
    client: AsyncClient, email: str, password: str = "testpass123"
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
    client: AsyncClient, token: str, workspace_id: str, name: str = "My Model"
) -> str:
    resp = await client.post(
        "/models",
        json={"name": name, "workspace_id": workspace_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_module(
    client: AsyncClient, token: str, model_id: str, name: str = "Sales Module"
) -> str:
    resp = await client.post(
        f"/models/{model_id}/modules",
        json={"name": name},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_line_item(
    client: AsyncClient, token: str, module_id: str, name: str = "Revenue"
) -> str:
    resp = await client.post(
        f"/modules/{module_id}/line-items",
        json={"name": name, "format": "number"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def full_setup(client: AsyncClient, suffix: str):
    """Register/login, create workspace, model, module, line item. Returns (token, model_id, line_item_id)."""
    token = await register_and_login(client, f"bulk_{suffix}@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    module_id = await create_module(client, token, model_id)
    line_item_id = await create_line_item(client, token, module_id)
    return token, model_id, line_item_id


# ---------------------------------------------------------------------------
# Test 1: Bulk write small batch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_write_small_batch(client: AsyncClient):
    """Bulk write a small batch of cells and verify job is created."""
    token, model_id, line_item_id = await full_setup(client, "write_small")
    dims = [str(uuid.uuid4()) for _ in range(3)]

    resp = await client.post(
        f"/models/{model_id}/bulk/write",
        json={
            "cells": [
                {"line_item_id": line_item_id, "dimension_members": [dims[i]], "value": float(i * 10)}
                for i in range(3)
            ],
            "chunk_size": 100,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 202
    job = resp.json()
    assert job["job_type"] == "import_cells"
    assert job["status"] == "completed"
    assert job["processed_rows"] == 3
    assert job["failed_rows"] == 0
    assert job["total_rows"] == 3
    assert "id" in job


# ---------------------------------------------------------------------------
# Test 2: Bulk write with chunking verifies progress tracking
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_write_chunking_progress(client: AsyncClient):
    """Bulk write with explicit small chunk_size — job should track progress."""
    token, model_id, line_item_id = await full_setup(client, "write_chunk")
    dims = [str(uuid.uuid4()) for _ in range(10)]

    resp = await client.post(
        f"/models/{model_id}/bulk/write",
        json={
            "cells": [
                {"line_item_id": line_item_id, "dimension_members": [dims[i]], "value": float(i)}
                for i in range(10)
            ],
            "chunk_size": 3,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 202
    job = resp.json()
    assert job["status"] == "completed"
    assert job["processed_rows"] == 10
    assert job["total_rows"] == 10

    # Job progress endpoint
    job_id = job["id"]
    prog_resp = await client.get(
        f"/bulk/jobs/{job_id}",
        headers=auth_headers(token),
    )
    assert prog_resp.status_code == 200
    progress = prog_resp.json()
    assert progress["processed_rows"] == 10
    assert progress["percentage"] == 100.0


# ---------------------------------------------------------------------------
# Test 3: Bulk read with pagination — limit/offset
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_read_pagination(client: AsyncClient):
    """Bulk read with limit and offset returns correct pages."""
    token, model_id, line_item_id = await full_setup(client, "read_page")
    dims = [str(uuid.uuid4()) for _ in range(15)]

    # Write 15 cells
    await client.post(
        f"/models/{model_id}/bulk/write",
        json={
            "cells": [
                {"line_item_id": line_item_id, "dimension_members": [dims[i]], "value": float(i)}
                for i in range(15)
            ],
        },
        headers=auth_headers(token),
    )

    # Read first page
    page1 = await client.post(
        f"/models/{model_id}/bulk/read",
        json={"limit": 10, "offset": 0},
        headers=auth_headers(token),
    )
    assert page1.status_code == 200
    data1 = page1.json()
    assert len(data1["cells"]) == 10
    assert data1["total_count"] == 15
    assert data1["has_more"] is True

    # Read second page
    page2 = await client.post(
        f"/models/{model_id}/bulk/read",
        json={"limit": 10, "offset": 10},
        headers=auth_headers(token),
    )
    assert page2.status_code == 200
    data2 = page2.json()
    assert len(data2["cells"]) == 5
    assert data2["total_count"] == 15
    assert data2["has_more"] is False


# ---------------------------------------------------------------------------
# Test 4: Bulk read with line_item filter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_read_line_item_filter(client: AsyncClient):
    """Bulk read filtered by line_item_ids returns only matching cells."""
    token, model_id, line_item_id = await full_setup(client, "read_filter")

    # Create a second line item in the same module
    # Re-create module for second line item
    module_id = await create_module(client, token, model_id, name="Filter Module")
    line_item_b = await create_line_item(client, token, module_id, name="Cost")

    dim1 = str(uuid.uuid4())
    dim2 = str(uuid.uuid4())

    # Write to line_item_id
    await client.post(
        f"/models/{model_id}/bulk/write",
        json={
            "cells": [
                {"line_item_id": line_item_id, "dimension_members": [dim1], "value": 100.0},
            ]
        },
        headers=auth_headers(token),
    )

    # Write to line_item_b
    await client.post(
        f"/models/{model_id}/bulk/write",
        json={
            "cells": [
                {"line_item_id": line_item_b, "dimension_members": [dim2], "value": 200.0},
            ]
        },
        headers=auth_headers(token),
    )

    # Read only line_item_b
    resp = await client.post(
        f"/models/{model_id}/bulk/read",
        json={"line_item_ids": [line_item_b]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] == 1
    assert data["cells"][0]["line_item_id"] == line_item_b
    assert data["cells"][0]["value"] == 200.0


# ---------------------------------------------------------------------------
# Test 5: Bulk delete cells
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_delete_cells(client: AsyncClient):
    """Bulk delete all cells for a line item."""
    token, model_id, line_item_id = await full_setup(client, "delete_cells")
    dims = [str(uuid.uuid4()) for _ in range(5)]

    # Write 5 cells
    await client.post(
        f"/models/{model_id}/bulk/write",
        json={
            "cells": [
                {"line_item_id": line_item_id, "dimension_members": [dims[i]], "value": float(i)}
                for i in range(5)
            ]
        },
        headers=auth_headers(token),
    )

    # Confirm they exist
    read_resp = await client.post(
        f"/models/{model_id}/bulk/read",
        json={"line_item_ids": [line_item_id]},
        headers=auth_headers(token),
    )
    assert read_resp.json()["total_count"] == 5

    # Delete them
    del_resp = await client.post(
        f"/models/{model_id}/bulk/delete",
        json={"line_item_id": line_item_id},
        headers=auth_headers(token),
    )
    assert del_resp.status_code == 202
    del_job = del_resp.json()
    assert del_job["status"] == "completed"
    assert del_job["job_type"] == "delete_cells"
    assert del_job["processed_rows"] == 5

    # Confirm cells are gone
    read_after = await client.post(
        f"/models/{model_id}/bulk/read",
        json={"line_item_ids": [line_item_id]},
        headers=auth_headers(token),
    )
    assert read_after.json()["total_count"] == 0


# ---------------------------------------------------------------------------
# Test 6: Job creation and status tracking
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_job_creation_and_status(client: AsyncClient):
    """After bulk write, job status can be queried via GET /bulk/jobs/{job_id}."""
    token, model_id, line_item_id = await full_setup(client, "job_status")
    dim = str(uuid.uuid4())

    write_resp = await client.post(
        f"/models/{model_id}/bulk/write",
        json={
            "cells": [{"line_item_id": line_item_id, "dimension_members": [dim], "value": 42.0}],
        },
        headers=auth_headers(token),
    )
    assert write_resp.status_code == 202
    job_id = write_resp.json()["id"]

    status_resp = await client.get(
        f"/bulk/jobs/{job_id}",
        headers=auth_headers(token),
    )
    assert status_resp.status_code == 200
    progress = status_resp.json()
    assert progress["job_id"] == job_id
    assert progress["status"] == "completed"
    assert progress["processed_rows"] == 1


# ---------------------------------------------------------------------------
# Test 7: Job progress percentage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_job_progress_percentage(client: AsyncClient):
    """Job progress percentage is 100 after completed write."""
    token, model_id, line_item_id = await full_setup(client, "job_percent")
    dims = [str(uuid.uuid4()) for _ in range(4)]

    write_resp = await client.post(
        f"/models/{model_id}/bulk/write",
        json={
            "cells": [
                {"line_item_id": line_item_id, "dimension_members": [d], "value": 1.0}
                for d in dims
            ],
        },
        headers=auth_headers(token),
    )
    job_id = write_resp.json()["id"]

    prog_resp = await client.get(f"/bulk/jobs/{job_id}", headers=auth_headers(token))
    assert prog_resp.status_code == 200
    prog = prog_resp.json()
    assert prog["total_rows"] == 4
    assert prog["processed_rows"] == 4
    assert prog["percentage"] == 100.0


# ---------------------------------------------------------------------------
# Test 8: Cancel endpoint returns 404 for nonexistent job
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancel_nonexistent_job_returns_404(client: AsyncClient):
    """Attempting to cancel a job that does not exist returns 404."""
    token, _, _ = await full_setup(client, "cancel_404")
    fake_job_id = str(uuid.uuid4())

    cancel_resp = await client.post(
        f"/bulk/jobs/{fake_job_id}/cancel",
        headers=auth_headers(token),
    )
    assert cancel_resp.status_code == 404


# ---------------------------------------------------------------------------
# Test 9: Cannot cancel completed job
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cannot_cancel_completed_job(client: AsyncClient):
    """Cancelling a completed job returns 409 Conflict."""
    token, model_id, line_item_id = await full_setup(client, "cancel_done")
    dim = str(uuid.uuid4())

    write_resp = await client.post(
        f"/models/{model_id}/bulk/write",
        json={"cells": [{"line_item_id": line_item_id, "dimension_members": [dim], "value": 1.0}]},
        headers=auth_headers(token),
    )
    job_id = write_resp.json()["id"]

    # Job is completed — cancel should fail
    cancel_resp = await client.post(
        f"/bulk/jobs/{job_id}/cancel",
        headers=auth_headers(token),
    )
    assert cancel_resp.status_code == 409
    assert "Cannot cancel" in cancel_resp.json()["detail"]


# ---------------------------------------------------------------------------
# Test 10: List jobs with status filter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_jobs_with_status_filter(client: AsyncClient):
    """List endpoint respects the status query parameter."""
    token, model_id, line_item_id = await full_setup(client, "list_jobs")
    str(uuid.uuid4())

    # Create some completed jobs
    for i in range(3):
        await client.post(
            f"/models/{model_id}/bulk/write",
            json={"cells": [{"line_item_id": line_item_id, "dimension_members": [str(uuid.uuid4())], "value": float(i)}]},
            headers=auth_headers(token),
        )

    # List all jobs (no filter)
    all_resp = await client.get(
        f"/models/{model_id}/bulk/jobs",
        headers=auth_headers(token),
    )
    assert all_resp.status_code == 200
    assert len(all_resp.json()) == 3

    # Filter by completed
    completed_resp = await client.get(
        f"/models/{model_id}/bulk/jobs?status=completed",
        headers=auth_headers(token),
    )
    assert completed_resp.status_code == 200
    completed_jobs = completed_resp.json()
    assert len(completed_jobs) == 3
    for j in completed_jobs:
        assert j["status"] == "completed"

    # Filter by pending — should be zero
    pending_resp = await client.get(
        f"/models/{model_id}/bulk/jobs?status=pending",
        headers=auth_headers(token),
    )
    assert pending_resp.status_code == 200
    assert len(pending_resp.json()) == 0


# ---------------------------------------------------------------------------
# Test 11: Bulk copy between models
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_copy_between_models(client: AsyncClient):
    """Bulk copy cells from source model to target model."""
    token = await register_and_login(client, "bulk_copy@example.com")
    ws_id = await create_workspace(client, token)

    # Source model
    src_model_id = await create_model(client, token, ws_id, name="Source Model")
    src_module_id = await create_module(client, token, src_model_id, name="Src Module")
    src_li_id = await create_line_item(client, token, src_module_id, name="Src LI")

    # Target model
    tgt_model_id = await create_model(client, token, ws_id, name="Target Model")
    tgt_module_id = await create_module(client, token, tgt_model_id, name="Tgt Module")
    tgt_li_id = await create_line_item(client, token, tgt_module_id, name="Tgt LI")

    dim = str(uuid.uuid4())

    # Write to source
    await client.post(
        f"/models/{src_model_id}/bulk/write",
        json={"cells": [{"line_item_id": src_li_id, "dimension_members": [dim], "value": 777.0}]},
        headers=auth_headers(token),
    )

    # Copy source to target
    copy_resp = await client.post(
        "/bulk/copy",
        json={
            "source_model_id": src_model_id,
            "target_model_id": tgt_model_id,
            "line_item_mapping": {src_li_id: tgt_li_id},
        },
        headers=auth_headers(token),
    )
    assert copy_resp.status_code == 202
    copy_job = copy_resp.json()
    assert copy_job["status"] == "completed"
    assert copy_job["job_type"] == "copy_cells"
    assert copy_job["processed_rows"] == 1

    # Verify target has the cell
    read_resp = await client.post(
        f"/models/{tgt_model_id}/bulk/read",
        json={"line_item_ids": [tgt_li_id]},
        headers=auth_headers(token),
    )
    assert read_resp.status_code == 200
    cells = read_resp.json()["cells"]
    assert len(cells) == 1
    assert cells[0]["value"] == 777.0


# ---------------------------------------------------------------------------
# Test 12: Auth required — bulk write
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_write_requires_auth(client: AsyncClient):
    fake_model_id = str(uuid.uuid4())
    resp = await client.post(
        f"/models/{fake_model_id}/bulk/write",
        json={"cells": []},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Test 13: Auth required — bulk read
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_read_requires_auth(client: AsyncClient):
    fake_model_id = str(uuid.uuid4())
    resp = await client.post(
        f"/models/{fake_model_id}/bulk/read",
        json={},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Test 14: Auth required — bulk delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_delete_requires_auth(client: AsyncClient):
    fake_model_id = str(uuid.uuid4())
    resp = await client.post(
        f"/models/{fake_model_id}/bulk/delete",
        json={},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Test 15: Auth required — job status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_job_status_requires_auth(client: AsyncClient):
    fake_job_id = str(uuid.uuid4())
    resp = await client.get(f"/bulk/jobs/{fake_job_id}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Test 16: 404 for nonexistent model
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_write_404_nonexistent_model(client: AsyncClient):
    token = await register_and_login(client, "bulk_404_model@example.com")
    fake_model_id = str(uuid.uuid4())

    resp = await client.post(
        f"/models/{fake_model_id}/bulk/write",
        json={"cells": []},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test 17: 404 for nonexistent job
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_job_status_404_nonexistent_job(client: AsyncClient):
    token = await register_and_login(client, "bulk_404_job@example.com")
    fake_job_id = str(uuid.uuid4())

    resp = await client.get(
        f"/bulk/jobs/{fake_job_id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test 18: Empty bulk write (no cells)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_write_empty_cells(client: AsyncClient):
    """Bulk write with zero cells creates a completed job with 0 rows."""
    token, model_id, _ = await full_setup(client, "empty_write")

    resp = await client.post(
        f"/models/{model_id}/bulk/write",
        json={"cells": []},
        headers=auth_headers(token),
    )
    assert resp.status_code == 202
    job = resp.json()
    assert job["status"] == "completed"
    assert job["processed_rows"] == 0
    assert job["failed_rows"] == 0
    assert job["total_rows"] == 0


# ---------------------------------------------------------------------------
# Test 19: Job completion summary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_job_completion_summary(client: AsyncClient):
    """Completed write job has a result_summary with processed/failed counts."""
    token, model_id, line_item_id = await full_setup(client, "job_summary")
    dims = [str(uuid.uuid4()) for _ in range(5)]

    resp = await client.post(
        f"/models/{model_id}/bulk/write",
        json={
            "cells": [
                {"line_item_id": line_item_id, "dimension_members": [d], "value": 1.0}
                for d in dims
            ],
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 202
    job = resp.json()
    assert job["status"] == "completed"
    assert job["result_summary"] is not None
    assert job["result_summary"]["processed_rows"] == 5
    assert job["result_summary"]["failed_rows"] == 0


# ---------------------------------------------------------------------------
# Test 20: Bulk read with dimension filters
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_read_dimension_filter(client: AsyncClient):
    """Bulk read with dimension_filters narrows results."""
    token, model_id, line_item_id = await full_setup(client, "read_dim_filter")
    dim_a = str(uuid.uuid4())
    dim_b = str(uuid.uuid4())
    dim_c = str(uuid.uuid4())

    # Write 3 cells at different dimension intersections
    await client.post(
        f"/models/{model_id}/bulk/write",
        json={
            "cells": [
                {"line_item_id": line_item_id, "dimension_members": [dim_a], "value": 10.0},
                {"line_item_id": line_item_id, "dimension_members": [dim_b], "value": 20.0},
                {"line_item_id": line_item_id, "dimension_members": [dim_c], "value": 30.0},
            ],
        },
        headers=auth_headers(token),
    )

    # Filter to only cells containing dim_a or dim_b
    resp = await client.post(
        f"/models/{model_id}/bulk/read",
        json={
            "dimension_filters": {"group": [dim_a, dim_b]},
            "limit": 1000,
            "offset": 0,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] == 2
    values = {c["value"] for c in data["cells"]}
    assert values == {10.0, 20.0}


# ---------------------------------------------------------------------------
# Test 21: List jobs for model — only shows jobs for that model
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_jobs_scoped_to_model(client: AsyncClient):
    """Jobs list is scoped to the specific model."""
    token = await register_and_login(client, "bulk_scope@example.com")
    ws_id = await create_workspace(client, token)
    model_a = await create_model(client, token, ws_id, name="Model A")
    model_b = await create_model(client, token, ws_id, name="Model B")

    # Create a job for model A
    await client.post(
        f"/models/{model_a}/bulk/write",
        json={"cells": []},
        headers=auth_headers(token),
    )

    # List jobs for model B — should be empty
    resp_b = await client.get(
        f"/models/{model_b}/bulk/jobs",
        headers=auth_headers(token),
    )
    assert resp_b.status_code == 200
    assert len(resp_b.json()) == 0

    # List jobs for model A — should have one
    resp_a = await client.get(
        f"/models/{model_a}/bulk/jobs",
        headers=auth_headers(token),
    )
    assert resp_a.status_code == 200
    assert len(resp_a.json()) == 1


# ---------------------------------------------------------------------------
# Test 22: Auth required — copy endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_copy_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/bulk/copy",
        json={
            "source_model_id": str(uuid.uuid4()),
            "target_model_id": str(uuid.uuid4()),
            "line_item_mapping": {},
        },
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Test 23: Auth required — cancel endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancel_requires_auth(client: AsyncClient):
    fake_job_id = str(uuid.uuid4())
    resp = await client.post(f"/bulk/jobs/{fake_job_id}/cancel")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Test 24: Bulk delete with no criteria deletes all cells in model
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_delete_all_cells_in_model(client: AsyncClient):
    """Bulk delete with no filters deletes all cells in the model."""
    token, model_id, line_item_id = await full_setup(client, "delete_all")
    dims = [str(uuid.uuid4()) for _ in range(4)]

    await client.post(
        f"/models/{model_id}/bulk/write",
        json={
            "cells": [
                {"line_item_id": line_item_id, "dimension_members": [d], "value": 1.0}
                for d in dims
            ],
        },
        headers=auth_headers(token),
    )

    del_resp = await client.post(
        f"/models/{model_id}/bulk/delete",
        json={},
        headers=auth_headers(token),
    )
    assert del_resp.status_code == 202
    del_job = del_resp.json()
    assert del_job["status"] == "completed"
    assert del_job["processed_rows"] == 4


# ---------------------------------------------------------------------------
# Test 25: 404 for nonexistent model on read
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_read_404_nonexistent_model(client: AsyncClient):
    token = await register_and_login(client, "bulk_read404@example.com")
    fake_model_id = str(uuid.uuid4())

    resp = await client.post(
        f"/models/{fake_model_id}/bulk/read",
        json={},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404
