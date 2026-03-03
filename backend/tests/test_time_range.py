import uuid
from typing import List, Optional

import pytest
from httpx import AsyncClient

# Ensure time_range models are registered with SQLAlchemy metadata
import app.models.time_range  # noqa: F401


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


async def create_model(client: AsyncClient, token: str, workspace_id: str, name: str = "My Model") -> str:
    resp = await client.post(
        "/models",
        json={"name": name, "workspace_id": workspace_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_module(client: AsyncClient, token: str, model_id: str, name: str = "Revenue Module") -> dict:
    resp = await client.post(
        f"/models/{model_id}/modules",
        json={"name": name},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def create_time_range(
    client: AsyncClient,
    token: str,
    model_id: str,
    name: str = "FY2024",
    start_period: str = "2024-01",
    end_period: str = "2024-12",
    granularity: str = "month",
    fiscal_year_start_month: int = 1,
    week_start_day: int = 0,
    week_pattern: str = "iso",
    retail_pattern: str = "standard",
    calendar_periods: Optional[List[dict]] = None,
    is_model_default: bool = False,
) -> dict:
    payload = {
        "name": name,
        "start_period": start_period,
        "end_period": end_period,
        "granularity": granularity,
        "fiscal_year_start_month": fiscal_year_start_month,
        "week_start_day": week_start_day,
        "week_pattern": week_pattern,
        "retail_pattern": retail_pattern,
        "is_model_default": is_model_default,
    }
    if calendar_periods is not None:
        payload["calendar_periods"] = calendar_periods
    resp = await client.post(
        f"/models/{model_id}/time-ranges",
        json=payload,
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def _setup(client: AsyncClient, email: str):
    """Register, create workspace and model. Returns (token, model_id)."""
    token = await register_and_login(client, email)
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    return token, model_id


# ---------------------------------------------------------------------------
# TimeRange CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_time_range_month(client: AsyncClient):
    token, model_id = await _setup(client, "tr_create_m@example.com")
    tr = await create_time_range(client, token, model_id)
    assert tr["name"] == "FY2024"
    assert tr["start_period"] == "2024-01"
    assert tr["end_period"] == "2024-12"
    assert tr["granularity"] == "month"
    assert tr["is_model_default"] is False
    assert tr["model_id"] == model_id
    assert "id" in tr
    assert "created_at" in tr
    assert "updated_at" in tr


@pytest.mark.asyncio
async def test_create_time_range_quarter(client: AsyncClient):
    token, model_id = await _setup(client, "tr_create_q@example.com")
    tr = await create_time_range(
        client, token, model_id,
        name="Q Range", start_period="2024-Q1", end_period="2024-Q4",
        granularity="quarter",
    )
    assert tr["granularity"] == "quarter"
    assert tr["start_period"] == "2024-Q1"


@pytest.mark.asyncio
async def test_create_time_range_year(client: AsyncClient):
    token, model_id = await _setup(client, "tr_create_y@example.com")
    tr = await create_time_range(
        client, token, model_id,
        name="Years", start_period="2020", end_period="2025",
        granularity="year",
    )
    assert tr["granularity"] == "year"
    assert tr["start_period"] == "2020"


@pytest.mark.asyncio
async def test_create_time_range_week(client: AsyncClient):
    token, model_id = await _setup(client, "tr_create_w@example.com")
    tr = await create_time_range(
        client, token, model_id,
        name="Weekly", start_period="2024-W01", end_period="2024-W10",
        granularity="week",
    )
    assert tr["granularity"] == "week"
    assert tr["start_period"] == "2024-W01"


@pytest.mark.asyncio
async def test_create_time_range_half_year(client: AsyncClient):
    token, model_id = await _setup(client, "tr_create_h@example.com")
    tr = await create_time_range(
        client, token, model_id,
        name="Half Years", start_period="FY2024-H1", end_period="FY2025-H2",
        granularity="half_year",
    )
    assert tr["granularity"] == "half_year"
    assert tr["start_period"] == "FY2024-H1"


@pytest.mark.asyncio
async def test_create_time_range_requires_auth(client: AsyncClient):
    fake_model_id = str(uuid.uuid4())
    resp = await client.post(
        f"/models/{fake_model_id}/time-ranges",
        json={
            "name": "No auth",
            "start_period": "2024-01",
            "end_period": "2024-12",
            "granularity": "month",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_time_range_invalid_month_format(client: AsyncClient):
    token, model_id = await _setup(client, "tr_bad_fmt@example.com")
    resp = await client.post(
        f"/models/{model_id}/time-ranges",
        json={
            "name": "Bad",
            "start_period": "2024-13",
            "end_period": "2024-12",
            "granularity": "month",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_time_range_invalid_quarter_format(client: AsyncClient):
    token, model_id = await _setup(client, "tr_bad_q@example.com")
    resp = await client.post(
        f"/models/{model_id}/time-ranges",
        json={
            "name": "Bad Q",
            "start_period": "2024-Q5",
            "end_period": "2024-Q4",
            "granularity": "quarter",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_time_range_invalid_year_format(client: AsyncClient):
    token, model_id = await _setup(client, "tr_bad_y@example.com")
    resp = await client.post(
        f"/models/{model_id}/time-ranges",
        json={
            "name": "Bad Y",
            "start_period": "20",
            "end_period": "2025",
            "granularity": "year",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_time_range_invalid_week_format(client: AsyncClient):
    token, model_id = await _setup(client, "tr_bad_w@example.com")
    resp = await client.post(
        f"/models/{model_id}/time-ranges",
        json={
            "name": "Bad Week",
            "start_period": "2024-W54",
            "end_period": "2024-W10",
            "granularity": "week",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_time_range_invalid_half_year_format(client: AsyncClient):
    token, model_id = await _setup(client, "tr_bad_h@example.com")
    resp = await client.post(
        f"/models/{model_id}/time-ranges",
        json={
            "name": "Bad Half",
            "start_period": "2024-H3",
            "end_period": "2025-H1",
            "granularity": "half_year",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_time_range_start_after_end(client: AsyncClient):
    token, model_id = await _setup(client, "tr_order@example.com")
    resp = await client.post(
        f"/models/{model_id}/time-ranges",
        json={
            "name": "Inverted",
            "start_period": "2024-12",
            "end_period": "2024-01",
            "granularity": "month",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_time_ranges_empty(client: AsyncClient):
    token, model_id = await _setup(client, "tr_list_e@example.com")
    resp = await client.get(
        f"/models/{model_id}/time-ranges",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_time_ranges_returns_created(client: AsyncClient):
    token, model_id = await _setup(client, "tr_list@example.com")
    await create_time_range(client, token, model_id, name="FY2024")
    await create_time_range(
        client, token, model_id,
        name="FY2025", start_period="2025-01", end_period="2025-12",
    )
    resp = await client.get(
        f"/models/{model_id}/time-ranges",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    names = [tr["name"] for tr in resp.json()]
    assert "FY2024" in names
    assert "FY2025" in names


@pytest.mark.asyncio
async def test_get_time_range(client: AsyncClient):
    token, model_id = await _setup(client, "tr_get@example.com")
    tr = await create_time_range(client, token, model_id)
    resp = await client.get(
        f"/time-ranges/{tr['id']}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == tr["id"]
    assert resp.json()["name"] == "FY2024"


@pytest.mark.asyncio
async def test_get_time_range_not_found(client: AsyncClient):
    token, _ = await _setup(client, "tr_get_nf@example.com")
    fake_id = str(uuid.uuid4())
    resp = await client.get(
        f"/time-ranges/{fake_id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_time_range_requires_auth(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/time-ranges/{fake_id}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_time_range_name(client: AsyncClient):
    token, model_id = await _setup(client, "tr_upd_name@example.com")
    tr = await create_time_range(client, token, model_id)
    resp = await client.put(
        f"/time-ranges/{tr['id']}",
        json={"name": "Updated FY2024"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated FY2024"
    # Other fields unchanged
    assert resp.json()["start_period"] == "2024-01"


@pytest.mark.asyncio
async def test_update_time_range_periods(client: AsyncClient):
    token, model_id = await _setup(client, "tr_upd_period@example.com")
    tr = await create_time_range(client, token, model_id)
    resp = await client.put(
        f"/time-ranges/{tr['id']}",
        json={"start_period": "2024-06", "end_period": "2024-12"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["start_period"] == "2024-06"


@pytest.mark.asyncio
async def test_update_time_range_invalid_period(client: AsyncClient):
    token, model_id = await _setup(client, "tr_upd_bad@example.com")
    tr = await create_time_range(client, token, model_id)
    resp = await client.put(
        f"/time-ranges/{tr['id']}",
        json={"start_period": "not-a-date"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_time_range_calendar_settings(client: AsyncClient):
    token, model_id = await _setup(client, "tr_upd_cal@example.com")
    tr = await create_time_range(
        client, token, model_id,
        granularity="week",
        start_period="2024-W01",
        end_period="2024-W52",
    )
    resp = await client.put(
        f"/time-ranges/{tr['id']}",
        json={
            "fiscal_year_start_month": 7,
            "week_start_day": 6,
            "week_pattern": "custom",
            "retail_pattern": "4-4-5",
            "calendar_periods": [
                {
                    "code": "FY2024-P01",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-28",
                }
            ],
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["fiscal_year_start_month"] == 7
    assert body["week_start_day"] == 6
    assert body["week_pattern"] == "custom"
    assert body["retail_pattern"] == "4-4-5"
    assert len(body["calendar_periods"]) == 1


@pytest.mark.asyncio
async def test_update_time_range_invalid_calendar_settings(client: AsyncClient):
    token, model_id = await _setup(client, "tr_upd_cal_bad@example.com")
    tr = await create_time_range(client, token, model_id)
    resp = await client.put(
        f"/time-ranges/{tr['id']}",
        json={"week_start_day": 8},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_time_range_not_found(client: AsyncClient):
    token, _ = await _setup(client, "tr_upd_nf@example.com")
    fake_id = str(uuid.uuid4())
    resp = await client.put(
        f"/time-ranges/{fake_id}",
        json={"name": "Ghost"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_time_range(client: AsyncClient):
    token, model_id = await _setup(client, "tr_del@example.com")
    tr = await create_time_range(client, token, model_id)
    resp = await client.delete(
        f"/time-ranges/{tr['id']}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 204

    # Verify it's gone
    get_resp = await client.get(
        f"/time-ranges/{tr['id']}",
        headers=auth_headers(token),
    )
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_time_range_not_found(client: AsyncClient):
    token, _ = await _setup(client, "tr_del_nf@example.com")
    fake_id = str(uuid.uuid4())
    resp = await client.delete(
        f"/time-ranges/{fake_id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_time_range_requires_auth(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    resp = await client.delete(f"/time-ranges/{fake_id}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Model default management
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_model_default(client: AsyncClient):
    token, model_id = await _setup(client, "tr_default@example.com")
    tr = await create_time_range(
        client, token, model_id, is_model_default=True,
    )
    assert tr["is_model_default"] is True


@pytest.mark.asyncio
async def test_create_time_range_persists_calendar_settings(client: AsyncClient):
    token, model_id = await _setup(client, "tr_cal_persist@example.com")
    tr = await create_time_range(
        client,
        token,
        model_id,
        name="Retail",
        start_period="2024-01",
        end_period="2024-12",
        granularity="month",
        fiscal_year_start_month=2,
        week_start_day=6,
        week_pattern="custom",
        retail_pattern="4-4-5",
        calendar_periods=[
            {
                "code": "FY2024-P01",
                "start_date": "2024-02-01",
                "end_date": "2024-02-28",
            }
        ],
    )
    assert tr["fiscal_year_start_month"] == 2
    assert tr["week_start_day"] == 6
    assert tr["week_pattern"] == "custom"
    assert tr["retail_pattern"] == "4-4-5"
    assert len(tr["calendar_periods"]) == 1


@pytest.mark.asyncio
async def test_only_one_model_default(client: AsyncClient):
    token, model_id = await _setup(client, "tr_one_default@example.com")
    tr1 = await create_time_range(
        client, token, model_id, name="First", is_model_default=True,
    )
    tr2 = await create_time_range(
        client, token, model_id,
        name="Second", start_period="2025-01", end_period="2025-12",
        is_model_default=True,
    )
    # Second should be default
    assert tr2["is_model_default"] is True

    # First should no longer be default
    resp = await client.get(
        f"/time-ranges/{tr1['id']}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["is_model_default"] is False


@pytest.mark.asyncio
async def test_update_to_model_default_unsets_previous(client: AsyncClient):
    token, model_id = await _setup(client, "tr_upd_default@example.com")
    tr1 = await create_time_range(
        client, token, model_id, name="First", is_model_default=True,
    )
    tr2 = await create_time_range(
        client, token, model_id,
        name="Second", start_period="2025-01", end_period="2025-12",
    )
    # Update tr2 to be default
    resp = await client.put(
        f"/time-ranges/{tr2['id']}",
        json={"is_model_default": True},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["is_model_default"] is True

    # tr1 should no longer be default
    resp1 = await client.get(
        f"/time-ranges/{tr1['id']}",
        headers=auth_headers(token),
    )
    assert resp1.json()["is_model_default"] is False


# ---------------------------------------------------------------------------
# Module time range assignment
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_assign_time_range_to_module(client: AsyncClient):
    token, model_id = await _setup(client, "mtr_assign@example.com")
    module = await create_module(client, token, model_id)
    tr = await create_time_range(client, token, model_id)

    resp = await client.post(
        f"/modules/{module['id']}/time-range",
        json={"time_range_id": tr["id"]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["module_id"] == module["id"]
    assert data["time_range_id"] == tr["id"]


@pytest.mark.asyncio
async def test_assign_replaces_existing(client: AsyncClient):
    token, model_id = await _setup(client, "mtr_replace@example.com")
    module = await create_module(client, token, model_id)
    tr1 = await create_time_range(client, token, model_id, name="First")
    tr2 = await create_time_range(
        client, token, model_id,
        name="Second", start_period="2025-01", end_period="2025-12",
    )

    # Assign first
    await client.post(
        f"/modules/{module['id']}/time-range",
        json={"time_range_id": tr1["id"]},
        headers=auth_headers(token),
    )
    # Assign second (replaces first)
    resp = await client.post(
        f"/modules/{module['id']}/time-range",
        json={"time_range_id": tr2["id"]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    assert resp.json()["time_range_id"] == tr2["id"]


@pytest.mark.asyncio
async def test_assign_module_not_found(client: AsyncClient):
    token, model_id = await _setup(client, "mtr_mod_nf@example.com")
    tr = await create_time_range(client, token, model_id)
    fake_id = str(uuid.uuid4())
    resp = await client.post(
        f"/modules/{fake_id}/time-range",
        json={"time_range_id": tr["id"]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_assign_time_range_not_found(client: AsyncClient):
    token, model_id = await _setup(client, "mtr_tr_nf@example.com")
    module = await create_module(client, token, model_id)
    fake_id = str(uuid.uuid4())
    resp = await client.post(
        f"/modules/{module['id']}/time-range",
        json={"time_range_id": fake_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_unassign_time_range_from_module(client: AsyncClient):
    token, model_id = await _setup(client, "mtr_unassign@example.com")
    module = await create_module(client, token, model_id)
    tr = await create_time_range(client, token, model_id)

    await client.post(
        f"/modules/{module['id']}/time-range",
        json={"time_range_id": tr["id"]},
        headers=auth_headers(token),
    )
    resp = await client.delete(
        f"/modules/{module['id']}/time-range",
        headers=auth_headers(token),
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_unassign_when_none_assigned(client: AsyncClient):
    token, model_id = await _setup(client, "mtr_unassign_none@example.com")
    module = await create_module(client, token, model_id)
    resp = await client.delete(
        f"/modules/{module['id']}/time-range",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_unassign_module_not_found(client: AsyncClient):
    token, _ = await _setup(client, "mtr_un_mod_nf@example.com")
    fake_id = str(uuid.uuid4())
    resp = await client.delete(
        f"/modules/{fake_id}/time-range",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Effective time range resolution
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_effective_returns_module_override(client: AsyncClient):
    token, model_id = await _setup(client, "eff_override@example.com")
    module = await create_module(client, token, model_id)
    await create_time_range(
        client, token, model_id, name="Default", is_model_default=True,
    )
    override_tr = await create_time_range(
        client, token, model_id,
        name="Override", start_period="2025-01", end_period="2025-06",
    )
    # Assign override to module
    await client.post(
        f"/modules/{module['id']}/time-range",
        json={"time_range_id": override_tr["id"]},
        headers=auth_headers(token),
    )
    resp = await client.get(
        f"/modules/{module['id']}/effective-time-range",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == override_tr["id"]
    assert resp.json()["name"] == "Override"


@pytest.mark.asyncio
async def test_effective_falls_back_to_model_default(client: AsyncClient):
    token, model_id = await _setup(client, "eff_default@example.com")
    module = await create_module(client, token, model_id)
    default_tr = await create_time_range(
        client, token, model_id, name="Default", is_model_default=True,
    )
    resp = await client.get(
        f"/modules/{module['id']}/effective-time-range",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == default_tr["id"]


@pytest.mark.asyncio
async def test_effective_returns_null_when_no_default(client: AsyncClient):
    token, model_id = await _setup(client, "eff_null@example.com")
    module = await create_module(client, token, model_id)
    resp = await client.get(
        f"/modules/{module['id']}/effective-time-range",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json() is None


@pytest.mark.asyncio
async def test_effective_after_unassign_falls_back(client: AsyncClient):
    token, model_id = await _setup(client, "eff_fallback@example.com")
    module = await create_module(client, token, model_id)
    default_tr = await create_time_range(
        client, token, model_id, name="Default", is_model_default=True,
    )
    override_tr = await create_time_range(
        client, token, model_id,
        name="Override", start_period="2025-01", end_period="2025-06",
    )
    # Assign then unassign
    await client.post(
        f"/modules/{module['id']}/time-range",
        json={"time_range_id": override_tr["id"]},
        headers=auth_headers(token),
    )
    await client.delete(
        f"/modules/{module['id']}/time-range",
        headers=auth_headers(token),
    )
    resp = await client.get(
        f"/modules/{module['id']}/effective-time-range",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == default_tr["id"]


@pytest.mark.asyncio
async def test_effective_module_not_found(client: AsyncClient):
    token, _ = await _setup(client, "eff_mod_nf@example.com")
    fake_id = str(uuid.uuid4())
    resp = await client.get(
        f"/modules/{fake_id}/effective-time-range",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_effective_requires_auth(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/modules/{fake_id}/effective-time-range")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Isolation: time ranges are scoped per model
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_time_ranges_isolated_per_model(client: AsyncClient):
    token, model_a = await _setup(client, "tr_iso@example.com")
    ws_id = await create_workspace(client, token, name="WS2")
    model_b = await create_model(client, token, ws_id, name="Model B")

    await create_time_range(client, token, model_a, name="In A")

    resp = await client.get(
        f"/models/{model_b}/time-ranges",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json() == []
