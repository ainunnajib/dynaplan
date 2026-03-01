"""
Tests for F042: Transactional and chunked file APIs.

Covers:
- Create chunked upload session
- Upload individual chunks
- Chunk index validation (out of range, duplicate)
- Upload status tracking (received_chunks increments)
- Auto-complete when all chunks uploaded
- Explicit complete endpoint
- Cannot complete with missing chunks
- Get upload status
- Upload not found (404)
- Create import task from upload
- Get import task status
- List import tasks for model
- Import task not found (404)
- Create transactional batch
- Add operations to batch
- Commit batch
- Rollback batch
- Cannot add ops to committed batch
- Cannot commit already committed batch
- Cannot rollback committed batch
- Get transaction status
- Transaction not found (404)
- Auth required on upload endpoints
- Auth required on import task endpoints
- Auth required on transaction endpoints
- Model not found (404) on create upload
- Model not found (404) on create import task
- Model not found (404) on create transaction
- Invalid total_chunks (< 1)
"""

import base64
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


async def setup_env(client: AsyncClient):
    """Register user, create workspace and model. Returns (token, model_id)."""
    token = await register_and_login(client, "chunk@test.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    return token, model_id


def make_chunk_data(content: str = "hello") -> str:
    return base64.b64encode(content.encode()).decode()


# ---------------------------------------------------------------------------
# Chunked Upload Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_upload_session(client: AsyncClient):
    token, model_id = await setup_env(client)
    resp = await client.post(
        f"/models/{model_id}/uploads",
        json={
            "filename": "data.csv",
            "content_type": "text/csv",
            "total_chunks": 3,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["filename"] == "data.csv"
    assert body["total_chunks"] == 3
    assert body["received_chunks"] == 0
    assert body["status"] == "uploading"


@pytest.mark.asyncio
async def test_upload_chunk(client: AsyncClient):
    token, model_id = await setup_env(client)
    resp = await client.post(
        f"/models/{model_id}/uploads",
        json={"filename": "f.csv", "content_type": "text/csv", "total_chunks": 2},
        headers=auth_headers(token),
    )
    upload_id = resp.json()["id"]

    chunk_resp = await client.post(
        f"/uploads/{upload_id}/chunks",
        json={
            "chunk_index": 0,
            "data": make_chunk_data("part1"),
            "size_bytes": 5,
        },
        headers=auth_headers(token),
    )
    assert chunk_resp.status_code == 201
    assert chunk_resp.json()["chunk_index"] == 0


@pytest.mark.asyncio
async def test_upload_all_chunks_auto_completes(client: AsyncClient):
    token, model_id = await setup_env(client)
    resp = await client.post(
        f"/models/{model_id}/uploads",
        json={"filename": "f.csv", "content_type": "text/csv", "total_chunks": 2},
        headers=auth_headers(token),
    )
    upload_id = resp.json()["id"]

    for i in range(2):
        await client.post(
            f"/uploads/{upload_id}/chunks",
            json={"chunk_index": i, "data": make_chunk_data(f"p{i}"), "size_bytes": 2},
            headers=auth_headers(token),
        )

    status_resp = await client.get(
        f"/uploads/{upload_id}", headers=auth_headers(token)
    )
    assert status_resp.status_code == 200
    body = status_resp.json()
    assert body["received_chunks"] == 2
    assert body["status"] == "complete"


@pytest.mark.asyncio
async def test_chunk_index_out_of_range(client: AsyncClient):
    token, model_id = await setup_env(client)
    resp = await client.post(
        f"/models/{model_id}/uploads",
        json={"filename": "f.csv", "content_type": "text/csv", "total_chunks": 2},
        headers=auth_headers(token),
    )
    upload_id = resp.json()["id"]

    bad_resp = await client.post(
        f"/uploads/{upload_id}/chunks",
        json={"chunk_index": 5, "data": make_chunk_data(), "size_bytes": 5},
        headers=auth_headers(token),
    )
    assert bad_resp.status_code == 400


@pytest.mark.asyncio
async def test_duplicate_chunk_rejected(client: AsyncClient):
    token, model_id = await setup_env(client)
    resp = await client.post(
        f"/models/{model_id}/uploads",
        json={"filename": "f.csv", "content_type": "text/csv", "total_chunks": 2},
        headers=auth_headers(token),
    )
    upload_id = resp.json()["id"]

    await client.post(
        f"/uploads/{upload_id}/chunks",
        json={"chunk_index": 0, "data": make_chunk_data(), "size_bytes": 5},
        headers=auth_headers(token),
    )
    dup_resp = await client.post(
        f"/uploads/{upload_id}/chunks",
        json={"chunk_index": 0, "data": make_chunk_data(), "size_bytes": 5},
        headers=auth_headers(token),
    )
    assert dup_resp.status_code == 400


@pytest.mark.asyncio
async def test_get_upload_status(client: AsyncClient):
    token, model_id = await setup_env(client)
    resp = await client.post(
        f"/models/{model_id}/uploads",
        json={"filename": "f.csv", "content_type": "text/csv", "total_chunks": 3},
        headers=auth_headers(token),
    )
    upload_id = resp.json()["id"]

    status_resp = await client.get(
        f"/uploads/{upload_id}", headers=auth_headers(token)
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "uploading"


@pytest.mark.asyncio
async def test_upload_not_found(client: AsyncClient):
    token, _ = await setup_env(client)
    fake_id = str(uuid.uuid4())
    resp = await client.get(
        f"/uploads/{fake_id}", headers=auth_headers(token)
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_complete_upload_explicit(client: AsyncClient):
    token, model_id = await setup_env(client)
    resp = await client.post(
        f"/models/{model_id}/uploads",
        json={"filename": "f.csv", "content_type": "text/csv", "total_chunks": 1},
        headers=auth_headers(token),
    )
    upload_id = resp.json()["id"]

    await client.post(
        f"/uploads/{upload_id}/chunks",
        json={"chunk_index": 0, "data": make_chunk_data(), "size_bytes": 5},
        headers=auth_headers(token),
    )

    complete_resp = await client.post(
        f"/uploads/{upload_id}/complete", headers=auth_headers(token)
    )
    assert complete_resp.status_code == 200
    assert complete_resp.json()["status"] == "complete"


@pytest.mark.asyncio
async def test_complete_upload_missing_chunks(client: AsyncClient):
    token, model_id = await setup_env(client)
    resp = await client.post(
        f"/models/{model_id}/uploads",
        json={"filename": "f.csv", "content_type": "text/csv", "total_chunks": 3},
        headers=auth_headers(token),
    )
    upload_id = resp.json()["id"]

    complete_resp = await client.post(
        f"/uploads/{upload_id}/complete", headers=auth_headers(token)
    )
    assert complete_resp.status_code == 400


@pytest.mark.asyncio
async def test_invalid_total_chunks(client: AsyncClient):
    token, model_id = await setup_env(client)
    resp = await client.post(
        f"/models/{model_id}/uploads",
        json={"filename": "f.csv", "content_type": "text/csv", "total_chunks": 0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Import Task Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_import_task(client: AsyncClient):
    token, model_id = await setup_env(client)
    resp = await client.post(
        f"/models/{model_id}/import-tasks",
        json={
            "task_type": "list_import",
            "target_id": str(uuid.uuid4()),
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["task_type"] == "list_import"
    assert body["status"] == "pending"
    assert body["processed_records"] == 0


@pytest.mark.asyncio
async def test_create_import_task_with_upload(client: AsyncClient):
    token, model_id = await setup_env(client)
    # Create upload first
    up_resp = await client.post(
        f"/models/{model_id}/uploads",
        json={"filename": "f.csv", "content_type": "text/csv", "total_chunks": 1},
        headers=auth_headers(token),
    )
    upload_id = up_resp.json()["id"]

    resp = await client.post(
        f"/models/{model_id}/import-tasks",
        json={
            "task_type": "module_import",
            "target_id": str(uuid.uuid4()),
            "upload_id": upload_id,
            "total_records": 100,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    assert resp.json()["upload_id"] == upload_id
    assert resp.json()["total_records"] == 100


@pytest.mark.asyncio
async def test_get_import_task(client: AsyncClient):
    token, model_id = await setup_env(client)
    create_resp = await client.post(
        f"/models/{model_id}/import-tasks",
        json={"task_type": "cell_import", "target_id": "mod1"},
        headers=auth_headers(token),
    )
    task_id = create_resp.json()["id"]

    resp = await client.get(
        f"/import-tasks/{task_id}", headers=auth_headers(token)
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == task_id


@pytest.mark.asyncio
async def test_list_import_tasks(client: AsyncClient):
    token, model_id = await setup_env(client)
    # Create two tasks
    for tt in ["list_import", "module_import"]:
        await client.post(
            f"/models/{model_id}/import-tasks",
            json={"task_type": tt, "target_id": "t1"},
            headers=auth_headers(token),
        )

    resp = await client.get(
        f"/models/{model_id}/import-tasks", headers=auth_headers(token)
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_import_task_not_found(client: AsyncClient):
    token, _ = await setup_env(client)
    fake_id = str(uuid.uuid4())
    resp = await client.get(
        f"/import-tasks/{fake_id}", headers=auth_headers(token)
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Transaction Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_transaction(client: AsyncClient):
    token, model_id = await setup_env(client)
    resp = await client.post(
        f"/models/{model_id}/transactions",
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "open"
    assert body["operations"] == []


@pytest.mark.asyncio
async def test_add_operation_to_batch(client: AsyncClient):
    token, model_id = await setup_env(client)
    resp = await client.post(
        f"/models/{model_id}/transactions", headers=auth_headers(token)
    )
    batch_id = resp.json()["id"]

    op_resp = await client.post(
        f"/transactions/{batch_id}/operations",
        json={
            "operation_type": "write_cell",
            "target": str(uuid.uuid4()),
            "payload": {"value": 42},
        },
        headers=auth_headers(token),
    )
    assert op_resp.status_code == 200
    assert len(op_resp.json()["operations"]) == 1


@pytest.mark.asyncio
async def test_add_multiple_operations(client: AsyncClient):
    token, model_id = await setup_env(client)
    resp = await client.post(
        f"/models/{model_id}/transactions", headers=auth_headers(token)
    )
    batch_id = resp.json()["id"]

    for i in range(3):
        await client.post(
            f"/transactions/{batch_id}/operations",
            json={
                "operation_type": "write_cell",
                "target": f"target_{i}",
                "payload": {"value": i},
            },
            headers=auth_headers(token),
        )

    get_resp = await client.get(
        f"/transactions/{batch_id}", headers=auth_headers(token)
    )
    assert len(get_resp.json()["operations"]) == 3


@pytest.mark.asyncio
async def test_commit_batch(client: AsyncClient):
    token, model_id = await setup_env(client)
    resp = await client.post(
        f"/models/{model_id}/transactions", headers=auth_headers(token)
    )
    batch_id = resp.json()["id"]

    await client.post(
        f"/transactions/{batch_id}/operations",
        json={"operation_type": "write_cell", "target": "t1", "payload": {"v": 1}},
        headers=auth_headers(token),
    )

    commit_resp = await client.post(
        f"/transactions/{batch_id}/commit", headers=auth_headers(token)
    )
    assert commit_resp.status_code == 200
    assert commit_resp.json()["status"] == "committed"
    assert commit_resp.json()["committed_at"] is not None


@pytest.mark.asyncio
async def test_rollback_batch(client: AsyncClient):
    token, model_id = await setup_env(client)
    resp = await client.post(
        f"/models/{model_id}/transactions", headers=auth_headers(token)
    )
    batch_id = resp.json()["id"]

    rollback_resp = await client.post(
        f"/transactions/{batch_id}/rollback", headers=auth_headers(token)
    )
    assert rollback_resp.status_code == 200
    assert rollback_resp.json()["status"] == "rolled_back"


@pytest.mark.asyncio
async def test_cannot_add_ops_to_committed_batch(client: AsyncClient):
    token, model_id = await setup_env(client)
    resp = await client.post(
        f"/models/{model_id}/transactions", headers=auth_headers(token)
    )
    batch_id = resp.json()["id"]

    await client.post(
        f"/transactions/{batch_id}/commit", headers=auth_headers(token)
    )

    op_resp = await client.post(
        f"/transactions/{batch_id}/operations",
        json={"operation_type": "write_cell", "target": "t1", "payload": {"v": 1}},
        headers=auth_headers(token),
    )
    assert op_resp.status_code == 400


@pytest.mark.asyncio
async def test_cannot_commit_committed_batch(client: AsyncClient):
    token, model_id = await setup_env(client)
    resp = await client.post(
        f"/models/{model_id}/transactions", headers=auth_headers(token)
    )
    batch_id = resp.json()["id"]

    await client.post(
        f"/transactions/{batch_id}/commit", headers=auth_headers(token)
    )
    second = await client.post(
        f"/transactions/{batch_id}/commit", headers=auth_headers(token)
    )
    assert second.status_code == 400


@pytest.mark.asyncio
async def test_cannot_rollback_committed_batch(client: AsyncClient):
    token, model_id = await setup_env(client)
    resp = await client.post(
        f"/models/{model_id}/transactions", headers=auth_headers(token)
    )
    batch_id = resp.json()["id"]

    await client.post(
        f"/transactions/{batch_id}/commit", headers=auth_headers(token)
    )
    rb_resp = await client.post(
        f"/transactions/{batch_id}/rollback", headers=auth_headers(token)
    )
    assert rb_resp.status_code == 400


@pytest.mark.asyncio
async def test_get_transaction_status(client: AsyncClient):
    token, model_id = await setup_env(client)
    resp = await client.post(
        f"/models/{model_id}/transactions", headers=auth_headers(token)
    )
    batch_id = resp.json()["id"]

    get_resp = await client.get(
        f"/transactions/{batch_id}", headers=auth_headers(token)
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == batch_id


@pytest.mark.asyncio
async def test_transaction_not_found(client: AsyncClient):
    token, _ = await setup_env(client)
    fake_id = str(uuid.uuid4())
    resp = await client.get(
        f"/transactions/{fake_id}", headers=auth_headers(token)
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Auth Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auth_required_upload(client: AsyncClient):
    fake_model = str(uuid.uuid4())
    resp = await client.post(
        f"/models/{fake_model}/uploads",
        json={"filename": "f.csv", "content_type": "text/csv", "total_chunks": 1},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_auth_required_import_task(client: AsyncClient):
    fake_model = str(uuid.uuid4())
    resp = await client.post(
        f"/models/{fake_model}/import-tasks",
        json={"task_type": "list_import", "target_id": "t1"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_auth_required_transaction(client: AsyncClient):
    fake_model = str(uuid.uuid4())
    resp = await client.post(f"/models/{fake_model}/transactions")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Model not found Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_model_not_found_upload(client: AsyncClient):
    token = await register_and_login(client, "nf1@test.com")
    fake_model = str(uuid.uuid4())
    resp = await client.post(
        f"/models/{fake_model}/uploads",
        json={"filename": "f.csv", "content_type": "text/csv", "total_chunks": 1},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_model_not_found_import_task(client: AsyncClient):
    token = await register_and_login(client, "nf2@test.com")
    fake_model = str(uuid.uuid4())
    resp = await client.post(
        f"/models/{fake_model}/import-tasks",
        json={"task_type": "list_import", "target_id": "t1"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_model_not_found_transaction(client: AsyncClient):
    token = await register_and_login(client, "nf3@test.com")
    fake_model = str(uuid.uuid4())
    resp = await client.post(
        f"/models/{fake_model}/transactions",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Backpressure tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.backpressure
async def test_upload_large_chunk_count_backpressure(client: AsyncClient):
    token, model_id = await setup_env(client)
    total_chunks = 120

    create_resp = await client.post(
        f"/models/{model_id}/uploads",
        json={
            "filename": "large_file.csv",
            "content_type": "text/csv",
            "total_chunks": total_chunks,
        },
        headers=auth_headers(token),
    )
    assert create_resp.status_code == 201
    upload_id = create_resp.json()["id"]

    for index in range(total_chunks):
        chunk_resp = await client.post(
            f"/uploads/{upload_id}/chunks",
            json={
                "chunk_index": index,
                "data": make_chunk_data(f"chunk-{index}"),
                "size_bytes": 8,
            },
            headers=auth_headers(token),
        )
        assert chunk_resp.status_code == 201

    status_resp = await client.get(
        f"/uploads/{upload_id}", headers=auth_headers(token)
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["received_chunks"] == total_chunks
    assert status_resp.json()["status"] == "complete"


@pytest.mark.asyncio
@pytest.mark.backpressure
async def test_transaction_many_operations_backpressure(client: AsyncClient):
    token, model_id = await setup_env(client)
    create_resp = await client.post(
        f"/models/{model_id}/transactions",
        headers=auth_headers(token),
    )
    assert create_resp.status_code == 201
    batch_id = create_resp.json()["id"]

    operation_count = 150
    for index in range(operation_count):
        op_resp = await client.post(
            f"/transactions/{batch_id}/operations",
            json={
                "operation_type": "write_cell",
                "target": f"line_item_{index}",
                "payload": {"value": index},
            },
            headers=auth_headers(token),
        )
        assert op_resp.status_code == 200

    commit_resp = await client.post(
        f"/transactions/{batch_id}/commit",
        headers=auth_headers(token),
    )
    assert commit_resp.status_code == 200
    assert commit_resp.json()["status"] == "committed"
    assert len(commit_resp.json()["operations"]) == operation_count
