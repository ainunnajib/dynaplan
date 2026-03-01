import uuid
from datetime import datetime, timezone, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# We import TestSession from conftest to get a DB session for direct service calls
from tests.conftest import TestSession


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


async def get_db_session() -> AsyncSession:
    """Return a bare async session for direct service calls in tests."""
    async with TestSession() as session:
        return session


# ---------------------------------------------------------------------------
# Service-layer tests (direct)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_log_event_cell_update(client: AsyncClient):
    """Test logging a cell_update audit event via service."""
    from app.services.audit import log_event, get_audit_log
    from app.models.audit import AuditEventType

    model_id = uuid.uuid4()
    entity_id = str(uuid.uuid4())

    async with TestSession() as db:
        entry = await log_event(
            db,
            model_id=model_id,
            event_type=AuditEventType.cell_update,
            entity_type="cell",
            entity_id=entity_id,
            old_value={"value": 100},
            new_value={"value": 200},
        )
        assert entry.id is not None
        assert entry.model_id == model_id
        assert entry.event_type == AuditEventType.cell_update
        assert entry.entity_type == "cell"
        assert entry.entity_id == entity_id
        assert entry.old_value == {"value": 100}
        assert entry.new_value == {"value": 200}


@pytest.mark.asyncio
async def test_log_event_line_item_create(client: AsyncClient):
    """Test logging a line_item_create event."""
    from app.services.audit import log_event
    from app.models.audit import AuditEventType

    model_id = uuid.uuid4()
    async with TestSession() as db:
        entry = await log_event(
            db,
            model_id=model_id,
            event_type=AuditEventType.line_item_create,
            entity_type="line_item",
            entity_id=str(uuid.uuid4()),
            new_value={"name": "Revenue", "format": "number"},
        )
        assert entry.event_type == AuditEventType.line_item_create
        assert entry.new_value == {"name": "Revenue", "format": "number"}
        assert entry.old_value is None


@pytest.mark.asyncio
async def test_log_event_module_delete(client: AsyncClient):
    """Test logging a module_delete event."""
    from app.services.audit import log_event
    from app.models.audit import AuditEventType

    model_id = uuid.uuid4()
    async with TestSession() as db:
        entry = await log_event(
            db,
            model_id=model_id,
            event_type=AuditEventType.module_delete,
            entity_type="module",
            entity_id=str(uuid.uuid4()),
            old_value={"name": "Old Module"},
        )
        assert entry.event_type == AuditEventType.module_delete
        assert entry.old_value == {"name": "Old Module"}
        assert entry.new_value is None


@pytest.mark.asyncio
async def test_log_event_with_metadata(client: AsyncClient):
    """Test logging event with extra metadata."""
    from app.services.audit import log_event
    from app.models.audit import AuditEventType

    model_id = uuid.uuid4()
    async with TestSession() as db:
        entry = await log_event(
            db,
            model_id=model_id,
            event_type=AuditEventType.model_update,
            entity_type="model",
            entity_id=str(model_id),
            metadata={"source": "api", "ip": "127.0.0.1"},
        )
        assert entry.metadata_ == {"source": "api", "ip": "127.0.0.1"}


@pytest.mark.asyncio
async def test_log_event_with_user_id(client: AsyncClient):
    """Test logging event with user_id."""
    from app.services.audit import log_event
    from app.models.audit import AuditEventType

    model_id = uuid.uuid4()
    user_id = uuid.uuid4()
    async with TestSession() as db:
        entry = await log_event(
            db,
            model_id=model_id,
            event_type=AuditEventType.dimension_create,
            entity_type="dimension",
            entity_id=str(uuid.uuid4()),
            user_id=user_id,
        )
        assert entry.user_id == user_id


# ---------------------------------------------------------------------------
# GET /models/{model_id}/audit  endpoint tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_audit_log_empty(client: AsyncClient):
    """Audit log for a new model is empty."""
    token = await register_and_login(client, "audit_empty@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await client.get(f"/models/{model_id}/audit", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_audit_log_requires_auth(client: AsyncClient):
    """Audit log endpoint requires authentication."""
    model_id = str(uuid.uuid4())
    resp = await client.get(f"/models/{model_id}/audit")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_audit_log_with_entries(client: AsyncClient):
    """Audit log returns entries after logging events."""
    from app.services.audit import log_event
    from app.models.audit import AuditEventType

    token = await register_and_login(client, "audit_entries@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    model_uuid = uuid.UUID(model_id)

    async with TestSession() as db:
        await log_event(db, model_id=model_uuid, event_type=AuditEventType.cell_update,
                        entity_type="cell", entity_id="cell-1", old_value={"v": 1}, new_value={"v": 2})
        await log_event(db, model_id=model_uuid, event_type=AuditEventType.line_item_create,
                        entity_type="line_item", entity_id="li-1", new_value={"name": "LI1"})

    resp = await client.get(f"/models/{model_id}/audit", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_get_audit_log_filter_by_event_type(client: AsyncClient):
    """Audit log can be filtered by event_type."""
    from app.services.audit import log_event
    from app.models.audit import AuditEventType

    token = await register_and_login(client, "audit_filter_type@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    model_uuid = uuid.UUID(model_id)

    async with TestSession() as db:
        await log_event(db, model_id=model_uuid, event_type=AuditEventType.cell_update,
                        entity_type="cell", entity_id="c1")
        await log_event(db, model_id=model_uuid, event_type=AuditEventType.module_create,
                        entity_type="module", entity_id="m1")
        await log_event(db, model_id=model_uuid, event_type=AuditEventType.cell_update,
                        entity_type="cell", entity_id="c2")

    resp = await client.get(
        f"/models/{model_id}/audit",
        params={"event_type": "cell_update"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert all(e["event_type"] == "cell_update" for e in data)


@pytest.mark.asyncio
async def test_get_audit_log_filter_by_entity_type(client: AsyncClient):
    """Audit log can be filtered by entity_type."""
    from app.services.audit import log_event
    from app.models.audit import AuditEventType

    token = await register_and_login(client, "audit_filter_etype@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    model_uuid = uuid.UUID(model_id)

    async with TestSession() as db:
        await log_event(db, model_id=model_uuid, event_type=AuditEventType.cell_update,
                        entity_type="cell", entity_id="c1")
        await log_event(db, model_id=model_uuid, event_type=AuditEventType.module_create,
                        entity_type="module", entity_id="m1")

    resp = await client.get(
        f"/models/{model_id}/audit",
        params={"entity_type": "module"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["entity_type"] == "module"


@pytest.mark.asyncio
async def test_get_audit_log_filter_by_entity_id(client: AsyncClient):
    """Audit log can be filtered by entity_id."""
    from app.services.audit import log_event
    from app.models.audit import AuditEventType

    token = await register_and_login(client, "audit_filter_eid@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    model_uuid = uuid.UUID(model_id)
    target_id = str(uuid.uuid4())

    async with TestSession() as db:
        await log_event(db, model_id=model_uuid, event_type=AuditEventType.cell_update,
                        entity_type="cell", entity_id=target_id)
        await log_event(db, model_id=model_uuid, event_type=AuditEventType.cell_update,
                        entity_type="cell", entity_id=str(uuid.uuid4()))

    resp = await client.get(
        f"/models/{model_id}/audit",
        params={"entity_id": target_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["entity_id"] == target_id


@pytest.mark.asyncio
async def test_get_audit_log_pagination(client: AsyncClient):
    """Audit log supports limit and offset for pagination."""
    from app.services.audit import log_event
    from app.models.audit import AuditEventType

    token = await register_and_login(client, "audit_pagination@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    model_uuid = uuid.UUID(model_id)

    async with TestSession() as db:
        for i in range(10):
            await log_event(db, model_id=model_uuid, event_type=AuditEventType.cell_update,
                            entity_type="cell", entity_id=f"cell-{i}")

    # First page
    resp = await client.get(
        f"/models/{model_id}/audit",
        params={"limit": 3, "offset": 0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3

    # Second page
    resp2 = await client.get(
        f"/models/{model_id}/audit",
        params={"limit": 3, "offset": 3},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert len(data2) == 3

    # Entries should differ between pages
    ids_page1 = {e["id"] for e in data}
    ids_page2 = {e["id"] for e in data2}
    assert ids_page1.isdisjoint(ids_page2)


@pytest.mark.asyncio
async def test_get_audit_log_date_range_filter(client: AsyncClient):
    """Audit log can be filtered by before date."""
    from app.services.audit import log_event
    from app.models.audit import AuditEventType

    token = await register_and_login(client, "audit_daterange@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    model_uuid = uuid.UUID(model_id)

    async with TestSession() as db:
        await log_event(db, model_id=model_uuid, event_type=AuditEventType.cell_update,
                        entity_type="cell", entity_id="c1")

    # Use a date clearly in the past so the entry won't match
    past_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
    resp = await client.get(
        f"/models/{model_id}/audit",
        params={"before": past_time.isoformat()},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 0


# ---------------------------------------------------------------------------
# GET /models/{model_id}/audit/summary  endpoint tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audit_summary_empty(client: AsyncClient):
    """Summary for a model with no events returns empty counts."""
    token = await register_and_login(client, "audit_sum_empty@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await client.get(f"/models/{model_id}/audit/summary", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["counts"] == {}


@pytest.mark.asyncio
async def test_audit_summary_counts(client: AsyncClient):
    """Summary counts events by type correctly."""
    from app.services.audit import log_event
    from app.models.audit import AuditEventType

    token = await register_and_login(client, "audit_sum_counts@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    model_uuid = uuid.UUID(model_id)

    async with TestSession() as db:
        await log_event(db, model_id=model_uuid, event_type=AuditEventType.cell_update,
                        entity_type="cell", entity_id="c1")
        await log_event(db, model_id=model_uuid, event_type=AuditEventType.cell_update,
                        entity_type="cell", entity_id="c2")
        await log_event(db, model_id=model_uuid, event_type=AuditEventType.module_create,
                        entity_type="module", entity_id="m1")

    resp = await client.get(f"/models/{model_id}/audit/summary", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert data["counts"]["cell_update"] == 2
    assert data["counts"]["module_create"] == 1


@pytest.mark.asyncio
async def test_audit_summary_requires_auth(client: AsyncClient):
    """Audit summary endpoint requires authentication."""
    model_id = str(uuid.uuid4())
    resp = await client.get(f"/models/{model_id}/audit/summary")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /audit/entity/{entity_type}/{entity_id}  endpoint tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_entity_history_empty(client: AsyncClient):
    """Entity history for unknown entity returns empty list."""
    token = await register_and_login(client, "audit_ent_empty@example.com")
    resp = await client.get(
        f"/audit/entity/cell/{uuid.uuid4()}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_entity_history_returns_changes(client: AsyncClient):
    """Entity history returns all changes for a specific entity."""
    from app.services.audit import log_event
    from app.models.audit import AuditEventType

    token = await register_and_login(client, "audit_ent_hist@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    model_uuid = uuid.UUID(model_id)
    entity_id = str(uuid.uuid4())

    async with TestSession() as db:
        await log_event(db, model_id=model_uuid, event_type=AuditEventType.cell_update,
                        entity_type="cell", entity_id=entity_id,
                        old_value={"value": 10}, new_value={"value": 20})
        await log_event(db, model_id=model_uuid, event_type=AuditEventType.cell_update,
                        entity_type="cell", entity_id=entity_id,
                        old_value={"value": 20}, new_value={"value": 30})
        # Different entity — should not appear
        await log_event(db, model_id=model_uuid, event_type=AuditEventType.cell_update,
                        entity_type="cell", entity_id=str(uuid.uuid4()))

    resp = await client.get(
        f"/audit/entity/cell/{entity_id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert all(e["entity_id"] == entity_id for e in data)


@pytest.mark.asyncio
async def test_entity_history_requires_auth(client: AsyncClient):
    """Entity history endpoint requires authentication."""
    resp = await client.get(f"/audit/entity/cell/{uuid.uuid4()}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_entity_history_limit(client: AsyncClient):
    """Entity history respects limit parameter."""
    from app.services.audit import log_event
    from app.models.audit import AuditEventType

    token = await register_and_login(client, "audit_ent_limit@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    model_uuid = uuid.UUID(model_id)
    entity_id = str(uuid.uuid4())

    async with TestSession() as db:
        for i in range(5):
            await log_event(db, model_id=model_uuid, event_type=AuditEventType.cell_update,
                            entity_type="cell", entity_id=entity_id,
                            old_value={"v": i}, new_value={"v": i + 1})

    resp = await client.get(
        f"/audit/entity/cell/{entity_id}",
        params={"limit": 3},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 3


# ---------------------------------------------------------------------------
# DELETE /models/{model_id}/audit  endpoint tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_purge_audit_non_admin_forbidden(client: AsyncClient):
    """Non-admin users cannot purge audit entries."""
    token = await register_and_login(client, "audit_purge_nonadmin@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    future_time = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    resp = await client.delete(
        f"/models/{model_id}/audit",
        params={"before": future_time},
        headers=auth_headers(token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_purge_audit_requires_auth(client: AsyncClient):
    """Purge audit endpoint requires authentication."""
    model_id = str(uuid.uuid4())
    future_time = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    resp = await client.delete(
        f"/models/{model_id}/audit",
        params={"before": future_time},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_purge_audit_service_layer(client: AsyncClient):
    """Purge service deletes entries older than the given date."""
    from app.services.audit import log_event, purge_old_entries, get_audit_log
    from app.models.audit import AuditEventType

    model_id = uuid.uuid4()

    async with TestSession() as db:
        await log_event(db, model_id=model_id, event_type=AuditEventType.cell_update,
                        entity_type="cell", entity_id="c1")
        await log_event(db, model_id=model_id, event_type=AuditEventType.cell_update,
                        entity_type="cell", entity_id="c2")

        # Purge entries before a future date
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        deleted = await purge_old_entries(db, model_id=model_id, before_date=future)
        assert deleted == 2

        # Log is now empty
        remaining = await get_audit_log(db, model_id=model_id)
        assert len(remaining) == 0


@pytest.mark.asyncio
async def test_purge_audit_partial(client: AsyncClient):
    """Purge only entries before the cutoff, leaving newer entries."""
    from app.services.audit import log_event, purge_old_entries, get_audit_log
    from app.models.audit import AuditEventType

    model_id = uuid.uuid4()

    async with TestSession() as db:
        # Log an entry
        await log_event(db, model_id=model_id, event_type=AuditEventType.cell_update,
                        entity_type="cell", entity_id="c1")

        # Log a newer entry
        await log_event(db, model_id=model_id, event_type=AuditEventType.module_create,
                        entity_type="module", entity_id="m1")

        # Use a future cutoff so everything gets purged, then verify we can purge selectively
        # by using a cutoff far in the future vs far in the past
        far_future = datetime(2099, 1, 1)
        far_past = datetime(2020, 1, 1)

        # Purge entries before far_past — nothing should be deleted
        deleted = await purge_old_entries(db, model_id=model_id, before_date=far_past)
        assert deleted == 0

        remaining = await get_audit_log(db, model_id=model_id)
        assert len(remaining) == 2

        # Purge entries before far_future — everything should be deleted
        deleted = await purge_old_entries(db, model_id=model_id, before_date=far_future)
        assert deleted == 2

        remaining = await get_audit_log(db, model_id=model_id)
        assert len(remaining) == 0


# ---------------------------------------------------------------------------
# Audit response field tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audit_entry_response_fields(client: AsyncClient):
    """Audit entries returned by API have all required fields."""
    from app.services.audit import log_event
    from app.models.audit import AuditEventType

    token = await register_and_login(client, "audit_fields@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    model_uuid = uuid.UUID(model_id)

    async with TestSession() as db:
        await log_event(
            db,
            model_id=model_uuid,
            event_type=AuditEventType.cell_update,
            entity_type="cell",
            entity_id="cell-xyz",
            old_value={"value": 5},
            new_value={"value": 10},
            metadata={"note": "test"},
        )

    resp = await client.get(f"/models/{model_id}/audit", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    entry = data[0]

    assert "id" in entry
    assert "model_id" in entry
    assert "event_type" in entry
    assert "entity_type" in entry
    assert "entity_id" in entry
    assert "user_id" in entry
    assert "old_value" in entry
    assert "new_value" in entry
    assert "metadata_" in entry
    assert "created_at" in entry

    assert entry["event_type"] == "cell_update"
    assert entry["entity_type"] == "cell"
    assert entry["entity_id"] == "cell-xyz"
    assert entry["old_value"] == {"value": 5}
    assert entry["new_value"] == {"value": 10}
    assert entry["metadata_"] == {"note": "test"}


@pytest.mark.asyncio
async def test_all_event_types_are_loggable(client: AsyncClient):
    """All AuditEventType values can be logged without error."""
    from app.services.audit import log_event
    from app.models.audit import AuditEventType

    model_id = uuid.uuid4()
    all_types = list(AuditEventType)

    async with TestSession() as db:
        for et in all_types:
            entry = await log_event(
                db,
                model_id=model_id,
                event_type=et,
                entity_type=et.value.split("_")[0],
                entity_id=str(uuid.uuid4()),
            )
            assert entry.event_type == et


@pytest.mark.asyncio
async def test_audit_log_nonexistent_model_returns_empty(client: AsyncClient):
    """Querying audit log for a model with no entries returns empty list."""
    token = await register_and_login(client, "audit_nomodel@example.com")
    fake_model_id = str(uuid.uuid4())

    resp = await client.get(f"/models/{fake_model_id}/audit", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_audit_summary_nonexistent_model(client: AsyncClient):
    """Summary for nonexistent model returns zero counts."""
    token = await register_and_login(client, "audit_sum_nomod@example.com")
    fake_model_id = str(uuid.uuid4())

    resp = await client.get(f"/models/{fake_model_id}/audit/summary", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["counts"] == {}


@pytest.mark.asyncio
async def test_get_audit_log_filter_by_user_id(client: AsyncClient):
    """Audit log can be filtered by user_id."""
    from app.services.audit import log_event
    from app.models.audit import AuditEventType

    token = await register_and_login(client, "audit_filter_uid@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    model_uuid = uuid.UUID(model_id)
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()

    async with TestSession() as db:
        await log_event(db, model_id=model_uuid, event_type=AuditEventType.cell_update,
                        entity_type="cell", entity_id="c1", user_id=user_a)
        await log_event(db, model_id=model_uuid, event_type=AuditEventType.cell_update,
                        entity_type="cell", entity_id="c2", user_id=user_b)
        await log_event(db, model_id=model_uuid, event_type=AuditEventType.cell_update,
                        entity_type="cell", entity_id="c3", user_id=user_a)

    resp = await client.get(
        f"/models/{model_id}/audit",
        params={"user_id": str(user_a)},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert all(e["user_id"] == str(user_a) for e in data)
