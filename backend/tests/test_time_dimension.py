"""
API integration tests for time dimension endpoints (F009).
At least 10 test cases as required by the spec.
"""

import uuid

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers (shared with test_dimension.py style)
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


# ---------------------------------------------------------------------------
# Create time dimension
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_time_dimension_basic(client: AsyncClient):
    """POST /models/{model_id}/time-dimensions returns 201 with dimension info."""
    token = await register_and_login(client, "td_create@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await client.post(
        f"/models/{model_id}/time-dimensions",
        json={
            "name": "Time",
            "start_year": 2024,
            "end_year": 2024,
            "granularity": "month",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Time"
    assert data["dimension_type"] == "time"
    assert data["model_id"] == model_id
    assert "id" in data


@pytest.mark.asyncio
async def test_create_time_dimension_requires_auth(client: AsyncClient):
    """POST /models/{model_id}/time-dimensions returns 401 without token."""
    fake_model_id = str(uuid.uuid4())
    resp = await client.post(
        f"/models/{fake_model_id}/time-dimensions",
        json={
            "name": "Time",
            "start_year": 2024,
            "end_year": 2024,
            "granularity": "month",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_time_dimension_with_fiscal_calendar(client: AsyncClient):
    """Can create a time dimension with a non-standard fiscal year start."""
    token = await register_and_login(client, "td_fiscal@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await client.post(
        f"/models/{model_id}/time-dimensions",
        json={
            "name": "Fiscal Time",
            "start_year": 2023,
            "end_year": 2023,
            "granularity": "month",
            "fiscal_calendar": {
                "fiscal_year_start_month": 7,
                "week_start_day": 0,
            },
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    assert resp.json()["dimension_type"] == "time"


@pytest.mark.asyncio
async def test_create_time_dimension_quarter_granularity(client: AsyncClient):
    """A quarter-granularity time dimension can be created successfully."""
    token = await register_and_login(client, "td_quarter@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await client.post(
        f"/models/{model_id}/time-dimensions",
        json={
            "name": "Quarters",
            "start_year": 2024,
            "end_year": 2024,
            "granularity": "quarter",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_time_dimension_retail_calendar(client: AsyncClient):
    """Retail calendar settings generate fiscal periods and weeks."""
    token = await register_and_login(client, "td_retail@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    create_resp = await client.post(
        f"/models/{model_id}/time-dimensions",
        json={
            "name": "Retail Time",
            "start_year": 2024,
            "end_year": 2024,
            "granularity": "week",
            "fiscal_calendar": {
                "fiscal_year_start_month": 1,
                "week_start_day": 6,
                "week_pattern": "custom",
                "retail_pattern": "4-4-5",
            },
        },
        headers=auth_headers(token),
    )
    assert create_resp.status_code == 201
    dim_id = create_resp.json()["id"]

    list_resp = await client.get(
        f"/dimensions/{dim_id}/time-periods",
        headers=auth_headers(token),
    )
    assert list_resp.status_code == 200
    periods = list_resp.json()
    months = [p for p in periods if p["period_type"] == "month"]
    weeks = [p for p in periods if p["period_type"] == "week"]
    assert len(months) == 12
    assert len(weeks) == 52
    assert months[0]["code"].startswith("FY2024-P")


@pytest.mark.asyncio
async def test_create_time_dimension_multi_year(client: AsyncClient):
    """Can create a time dimension spanning multiple years."""
    token = await register_and_login(client, "td_multiyear@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await client.post(
        f"/models/{model_id}/time-dimensions",
        json={
            "name": "3 Year Plan",
            "start_year": 2023,
            "end_year": 2025,
            "granularity": "month",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    dim_id = resp.json()["id"]

    # List time periods and verify count (3 years * 12 months = 36)
    list_resp = await client.get(
        f"/dimensions/{dim_id}/time-periods",
        headers=auth_headers(token),
    )
    assert list_resp.status_code == 200
    periods = list_resp.json()
    months = [p for p in periods if p["period_type"] == "month"]
    assert len(months) == 36


# ---------------------------------------------------------------------------
# List time periods
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_time_periods_has_date_info(client: AsyncClient):
    """GET /dimensions/{id}/time-periods returns periods with start/end dates."""
    token = await register_and_login(client, "td_list_dates@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    create_resp = await client.post(
        f"/models/{model_id}/time-dimensions",
        json={
            "name": "Time",
            "start_year": 2024,
            "end_year": 2024,
            "granularity": "month",
        },
        headers=auth_headers(token),
    )
    dim_id = create_resp.json()["id"]

    resp = await client.get(
        f"/dimensions/{dim_id}/time-periods",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    periods = resp.json()
    assert len(periods) > 0
    for p in periods:
        assert "start_date" in p
        assert "end_date" in p
        assert "period_type" in p
        assert p["start_date"] is not None
        assert p["end_date"] is not None


@pytest.mark.asyncio
async def test_list_time_periods_month_count(client: AsyncClient):
    """A single-year month-granularity dimension has exactly 12 month periods."""
    token = await register_and_login(client, "td_month_count@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    create_resp = await client.post(
        f"/models/{model_id}/time-dimensions",
        json={
            "name": "Monthly",
            "start_year": 2024,
            "end_year": 2024,
            "granularity": "month",
        },
        headers=auth_headers(token),
    )
    dim_id = create_resp.json()["id"]

    resp = await client.get(
        f"/dimensions/{dim_id}/time-periods",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    months = [p for p in resp.json() if p["period_type"] == "month"]
    assert len(months) == 12


@pytest.mark.asyncio
async def test_list_time_periods_hierarchy_parent_ids(client: AsyncClient):
    """Dimension items have parent_id set correctly to encode hierarchy."""
    token = await register_and_login(client, "td_hierarchy@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    create_resp = await client.post(
        f"/models/{model_id}/time-dimensions",
        json={
            "name": "Hierarchical",
            "start_year": 2024,
            "end_year": 2024,
            "granularity": "month",
        },
        headers=auth_headers(token),
    )
    dim_id = create_resp.json()["id"]

    resp = await client.get(
        f"/dimensions/{dim_id}/time-periods",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    periods = resp.json()

    # All months should have a non-null parent_id (their quarter)
    months = [p for p in periods if p["period_type"] == "month"]
    assert all(m["parent_id"] is not None for m in months)

    # All quarters should have a non-null parent_id (their half)
    quarters = [p for p in periods if p["period_type"] == "quarter"]
    assert all(q["parent_id"] is not None for q in quarters)

    # Year should have null parent_id
    years = [p for p in periods if p["period_type"] == "year"]
    assert all(y["parent_id"] is None for y in years)


@pytest.mark.asyncio
async def test_list_time_periods_requires_auth(client: AsyncClient):
    """GET /dimensions/{id}/time-periods returns 401 without token."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/dimensions/{fake_id}/time-periods")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_time_periods_not_found(client: AsyncClient):
    """GET /dimensions/{id}/time-periods returns 404 for unknown dimension."""
    token = await register_and_login(client, "td_not_found@example.com")
    fake_id = str(uuid.uuid4())
    resp = await client.get(
        f"/dimensions/{fake_id}/time-periods",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_time_dimension_appears_in_model_dimensions(client: AsyncClient):
    """A created time dimension appears in the model's dimension list."""
    token = await register_and_login(client, "td_list_model@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    create_resp = await client.post(
        f"/models/{model_id}/time-dimensions",
        json={
            "name": "Calendar",
            "start_year": 2024,
            "end_year": 2024,
            "granularity": "year",
        },
        headers=auth_headers(token),
    )
    dim_id = create_resp.json()["id"]

    list_resp = await client.get(
        f"/models/{model_id}/dimensions",
        headers=auth_headers(token),
    )
    assert list_resp.status_code == 200
    ids = [d["id"] for d in list_resp.json()]
    assert dim_id in ids


@pytest.mark.asyncio
async def test_time_periods_codes_are_clean(client: AsyncClient):
    """Period codes returned by the API should not contain the pipe separator."""
    token = await register_and_login(client, "td_clean_codes@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    create_resp = await client.post(
        f"/models/{model_id}/time-dimensions",
        json={
            "name": "Clean",
            "start_year": 2024,
            "end_year": 2024,
            "granularity": "quarter",
        },
        headers=auth_headers(token),
    )
    dim_id = create_resp.json()["id"]

    resp = await client.get(
        f"/dimensions/{dim_id}/time-periods",
        headers=auth_headers(token),
    )
    periods = resp.json()
    for p in periods:
        assert "|" not in p["code"], f"Raw encoded code leaked into response: {p['code']}"
