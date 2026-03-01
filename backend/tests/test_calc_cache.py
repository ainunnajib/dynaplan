"""
Tests for Feature F031 — Calculation caching.

Covers service-layer and REST API behaviour.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.dependency_graph import DependencyGraph
from app.models.calc_cache import CalcCache
from app.services.calc_cache import (
    bulk_set_cache,
    clear_cache,
    compute_formula_hash,
    get_cache_stats,
    get_cached_value,
    get_stale_entries,
    invalidate_cache,
    invalidate_dependents,
    recalculate_stale,
    set_cached_value,
)


# ---------------------------------------------------------------------------
# Shared helpers — same pattern as test_planning_model.py
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


async def create_model(
    client: AsyncClient,
    token: str,
    workspace_id: str,
    name: str = "My Model",
) -> dict:
    resp = await client.post(
        "/models",
        json={"name": name, "workspace_id": workspace_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


# Fixture providing a db session for direct service tests
# (The conftest.py provides `client` and sets up the DB; we pull a session
#  through the same overridden `get_db` dependency.)

@pytest.fixture
async def db_session():
    """Yield an async db session using the test engine configured in conftest."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool
    from app.models import Base

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestSession() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ---------------------------------------------------------------------------
# 1. compute_formula_hash — pure function
# ---------------------------------------------------------------------------

def test_formula_hash_is_64_chars():
    h = compute_formula_hash("A + B * 2")
    assert len(h) == 64


def test_formula_hash_deterministic():
    h1 = compute_formula_hash("Revenue - Cost")
    h2 = compute_formula_hash("Revenue - Cost")
    assert h1 == h2


def test_formula_hash_different_formulas_differ():
    h1 = compute_formula_hash("A + B")
    h2 = compute_formula_hash("A - B")
    assert h1 != h2


# ---------------------------------------------------------------------------
# 2. Service: set and get cached value
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_and_get_cached_value(db_session: AsyncSession):
    model_id = uuid.uuid4()
    line_item_id = uuid.uuid4()
    dim_key = "dim1|dim2"
    formula = "Revenue * 0.1"
    fhash = compute_formula_hash(formula)

    entry = await set_cached_value(
        db_session, model_id, line_item_id, dim_key, 42.0, fhash
    )
    assert entry.computed_value == "42.0"
    assert entry.is_valid is True

    fetched = await get_cached_value(db_session, line_item_id, dim_key)
    assert fetched is not None
    assert fetched.computed_value == "42.0"


@pytest.mark.asyncio
async def test_cache_miss_returns_none(db_session: AsyncSession):
    fetched = await get_cached_value(db_session, uuid.uuid4(), "nonexistent|key")
    assert fetched is None


@pytest.mark.asyncio
async def test_upsert_updates_existing_entry(db_session: AsyncSession):
    model_id = uuid.uuid4()
    line_item_id = uuid.uuid4()
    dim_key = "upsert|test"
    fhash = compute_formula_hash("x + 1")

    await set_cached_value(db_session, model_id, line_item_id, dim_key, 10, fhash)
    await set_cached_value(db_session, model_id, line_item_id, dim_key, 99, fhash)

    fetched = await get_cached_value(db_session, line_item_id, dim_key)
    assert fetched is not None
    assert fetched.computed_value == "99"


# ---------------------------------------------------------------------------
# 3. Service: invalidation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalidate_specific_entry(db_session: AsyncSession):
    model_id = uuid.uuid4()
    line_item_id = uuid.uuid4()
    dim_key = "a|b"
    fhash = compute_formula_hash("a")

    await set_cached_value(db_session, model_id, line_item_id, dim_key, 5, fhash)
    count = await invalidate_cache(db_session, line_item_id, dimension_key=dim_key)
    assert count == 1

    fetched = await get_cached_value(db_session, line_item_id, dim_key)
    assert fetched is None  # is_valid=False so not returned


@pytest.mark.asyncio
async def test_invalidate_all_for_line_item(db_session: AsyncSession):
    model_id = uuid.uuid4()
    line_item_id = uuid.uuid4()
    fhash = compute_formula_hash("x")

    await set_cached_value(db_session, model_id, line_item_id, "k1", 1, fhash)
    await set_cached_value(db_session, model_id, line_item_id, "k2", 2, fhash)

    count = await invalidate_cache(db_session, line_item_id)
    assert count == 2

    assert await get_cached_value(db_session, line_item_id, "k1") is None
    assert await get_cached_value(db_session, line_item_id, "k2") is None


@pytest.mark.asyncio
async def test_invalidated_entry_shows_is_valid_false(db_session: AsyncSession):
    """After invalidation the row still exists with is_valid=False."""
    from sqlalchemy import select

    model_id = uuid.uuid4()
    line_item_id = uuid.uuid4()
    dim_key = "valid|check"
    fhash = compute_formula_hash("z")

    await set_cached_value(db_session, model_id, line_item_id, dim_key, 7, fhash)
    await invalidate_cache(db_session, line_item_id, dimension_key=dim_key)

    result = await db_session.execute(
        select(CalcCache).where(
            CalcCache.line_item_id == line_item_id,
            CalcCache.dimension_key == dim_key,
        )
    )
    row = result.scalar_one_or_none()
    assert row is not None
    assert row.is_valid is False


@pytest.mark.asyncio
async def test_invalidate_with_cascade(db_session: AsyncSession):
    """invalidate_dependents should invalidate downstream line items too."""
    model_id = uuid.uuid4()

    li_a = uuid.uuid4()
    li_b = uuid.uuid4()
    li_c = uuid.uuid4()
    fhash = compute_formula_hash("something")

    # Populate cache for all three
    await set_cached_value(db_session, model_id, li_a, "k", 1, fhash)
    await set_cached_value(db_session, model_id, li_b, "k", 2, fhash)
    await set_cached_value(db_session, model_id, li_c, "k", 3, fhash)

    # Graph: A -> B -> C  (B depends on A, C depends on B)
    graph = DependencyGraph()
    graph.add_dependency(str(li_b), str(li_a))
    graph.add_dependency(str(li_c), str(li_b))

    # Invalidate from A — should cascade to B and C
    total = await invalidate_dependents(db_session, model_id, li_a, graph)
    # A, B, C all invalidated (3 entries)
    assert total == 3


# ---------------------------------------------------------------------------
# 4. Service: expired entry not returned
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_expired_entry_not_returned(db_session: AsyncSession):
    model_id = uuid.uuid4()
    line_item_id = uuid.uuid4()
    dim_key = "exp|key"
    fhash = compute_formula_hash("foo")

    past = datetime.now(tz=timezone.utc) - timedelta(hours=1)
    await set_cached_value(
        db_session, model_id, line_item_id, dim_key, 99, fhash, expires_at=past
    )

    fetched = await get_cached_value(db_session, line_item_id, dim_key)
    assert fetched is None


@pytest.mark.asyncio
async def test_non_expired_entry_returned(db_session: AsyncSession):
    model_id = uuid.uuid4()
    line_item_id = uuid.uuid4()
    dim_key = "future|key"
    fhash = compute_formula_hash("bar")

    future = datetime.now(tz=timezone.utc) + timedelta(hours=1)
    await set_cached_value(
        db_session, model_id, line_item_id, dim_key, 55, fhash, expires_at=future
    )

    fetched = await get_cached_value(db_session, line_item_id, dim_key)
    assert fetched is not None
    assert fetched.computed_value == "55"


# ---------------------------------------------------------------------------
# 5. Service: cache stats
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_stats_counts(db_session: AsyncSession):
    model_id = uuid.uuid4()
    fhash = compute_formula_hash("stat")

    li1 = uuid.uuid4()
    li2 = uuid.uuid4()

    await set_cached_value(db_session, model_id, li1, "k1", 1, fhash)
    await set_cached_value(db_session, model_id, li1, "k2", 2, fhash)
    await set_cached_value(db_session, model_id, li2, "k1", 3, fhash)
    # Invalidate one
    await invalidate_cache(db_session, li2, "k1")

    stats = await get_cache_stats(db_session, model_id)
    assert stats["total_entries"] == 3
    assert stats["valid_count"] == 2
    assert stats["invalid_count"] == 1


@pytest.mark.asyncio
async def test_cache_stats_empty_model(db_session: AsyncSession):
    stats = await get_cache_stats(db_session, uuid.uuid4())
    assert stats["total_entries"] == 0
    assert stats["valid_count"] == 0
    assert stats["invalid_count"] == 0
    assert stats["oldest_entry"] is None
    assert stats["newest_entry"] is None


# ---------------------------------------------------------------------------
# 6. Service: clear cache
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_clear_cache_deletes_all(db_session: AsyncSession):
    model_id = uuid.uuid4()
    li = uuid.uuid4()
    fhash = compute_formula_hash("c")

    await set_cached_value(db_session, model_id, li, "c1", 1, fhash)
    await set_cached_value(db_session, model_id, li, "c2", 2, fhash)

    deleted = await clear_cache(db_session, model_id)
    assert deleted == 2

    stats = await get_cache_stats(db_session, model_id)
    assert stats["total_entries"] == 0


# ---------------------------------------------------------------------------
# 7. Service: bulk set cache
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_set_cache(db_session: AsyncSession):
    model_id = uuid.uuid4()
    li = uuid.uuid4()
    fhash = compute_formula_hash("bulk")

    entries = [
        {"line_item_id": li, "dimension_key": f"k{i}", "value": i * 10, "formula_hash": fhash}
        for i in range(5)
    ]
    result = await bulk_set_cache(db_session, model_id, entries)
    assert len(result) == 5

    stats = await get_cache_stats(db_session, model_id)
    assert stats["total_entries"] == 5


# ---------------------------------------------------------------------------
# 8. Service: get stale entries
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_stale_entries(db_session: AsyncSession):
    model_id = uuid.uuid4()
    li = uuid.uuid4()
    fhash = compute_formula_hash("stale")

    await set_cached_value(db_session, model_id, li, "s1", 1, fhash)
    await set_cached_value(db_session, model_id, li, "s2", 2, fhash)
    await set_cached_value(db_session, model_id, li, "s3", 3, fhash)
    await invalidate_cache(db_session, li, "s1")
    await invalidate_cache(db_session, li, "s3")

    stale = await get_stale_entries(db_session, model_id, limit=100)
    dim_keys = {e.dimension_key for e in stale}
    assert "s1" in dim_keys
    assert "s3" in dim_keys
    assert "s2" not in dim_keys


@pytest.mark.asyncio
async def test_get_stale_entries_limit(db_session: AsyncSession):
    model_id = uuid.uuid4()
    li = uuid.uuid4()
    fhash = compute_formula_hash("lim")

    for i in range(10):
        await set_cached_value(db_session, model_id, li, f"k{i}", i, fhash)
    await invalidate_cache(db_session, li)

    stale = await get_stale_entries(db_session, model_id, limit=3)
    assert len(stale) == 3


# ---------------------------------------------------------------------------
# 9. Service: recalculate stale
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recalculate_stale(db_session: AsyncSession):
    model_id = uuid.uuid4()
    li = uuid.uuid4()
    fhash = compute_formula_hash("recalc")

    await set_cached_value(db_session, model_id, li, "r1", 1, fhash)
    await set_cached_value(db_session, model_id, li, "r2", 2, fhash)
    await set_cached_value(db_session, model_id, li, "r3", 3, fhash)
    await invalidate_cache(db_session, li)

    result = await recalculate_stale(db_session, model_id, batch_size=2)
    assert result["entries_recalculated"] == 2
    assert result["entries_remaining"] == 1


# ---------------------------------------------------------------------------
# 10. API: auth required on all endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stats_requires_auth(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/models/{fake_id}/cache/stats")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_invalidate_requires_auth(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    resp = await client.post(
        f"/models/{fake_id}/cache/invalidate",
        json={"line_item_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_clear_cache_requires_auth(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    resp = await client.delete(f"/models/{fake_id}/cache")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_recalculate_requires_auth(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    resp = await client.post(f"/models/{fake_id}/cache/recalculate")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_stale_list_requires_auth(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/models/{fake_id}/cache/stale")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 11. API: 404 for nonexistent model
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stats_404_nonexistent_model(client: AsyncClient):
    token = await register_and_login(client, "cc_stats404@example.com")
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/models/{fake_id}/cache/stats", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_clear_404_nonexistent_model(client: AsyncClient):
    token = await register_and_login(client, "cc_clear404@example.com")
    fake_id = str(uuid.uuid4())
    resp = await client.delete(f"/models/{fake_id}/cache", headers=auth_headers(token))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 12. API: full integration flows
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_stats_empty(client: AsyncClient):
    token = await register_and_login(client, "cc_api_stats@example.com")
    ws_id = await create_workspace(client, token)
    model = await create_model(client, token, ws_id)
    model_id = model["id"]

    resp = await client.get(f"/models/{model_id}/cache/stats", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_entries"] == 0
    assert data["valid_count"] == 0
    assert data["invalid_count"] == 0


@pytest.mark.asyncio
async def test_api_clear_cache(client: AsyncClient):
    token = await register_and_login(client, "cc_api_clear@example.com")
    ws_id = await create_workspace(client, token)
    model = await create_model(client, token, ws_id)
    model_id = model["id"]

    resp = await client.delete(f"/models/{model_id}/cache", headers=auth_headers(token))
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_api_recalculate_empty_model(client: AsyncClient):
    token = await register_and_login(client, "cc_api_recalc@example.com")
    ws_id = await create_workspace(client, token)
    model = await create_model(client, token, ws_id)
    model_id = model["id"]

    resp = await client.post(
        f"/models/{model_id}/cache/recalculate",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["entries_recalculated"] == 0
    assert data["entries_remaining"] == 0


@pytest.mark.asyncio
async def test_api_stale_list_empty(client: AsyncClient):
    token = await register_and_login(client, "cc_api_stale@example.com")
    ws_id = await create_workspace(client, token)
    model = await create_model(client, token, ws_id)
    model_id = model["id"]

    resp = await client.get(f"/models/{model_id}/cache/stale", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_api_invalidate_line_item(client: AsyncClient):
    token = await register_and_login(client, "cc_api_inv@example.com")
    ws_id = await create_workspace(client, token)
    model = await create_model(client, token, ws_id)
    model_id = model["id"]
    li_id = str(uuid.uuid4())

    resp = await client.post(
        f"/models/{model_id}/cache/invalidate",
        json={"line_item_id": li_id, "cascade": False},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    # No entries existed, so 0 invalidated
    assert data["invalidated"] == 0


@pytest.mark.asyncio
async def test_api_recalculate_404(client: AsyncClient):
    token = await register_and_login(client, "cc_recalc404@example.com")
    fake_id = str(uuid.uuid4())
    resp = await client.post(
        f"/models/{fake_id}/cache/recalculate",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404
