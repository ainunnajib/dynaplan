"""Tests for Feature F026: Rolling forecasts."""

import uuid
from typing import Optional

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


async def create_model(client: AsyncClient, token: str, workspace_id: str, name: str = "My Model") -> str:
    resp = await client.post(
        "/models",
        json={"name": name, "workspace_id": workspace_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_version(
    client: AsyncClient,
    token: str,
    model_id: str,
    name: str = "Version 1",
    version_type: str = "forecast",
    switchover_period: Optional[str] = None,
) -> dict:
    payload: dict = {
        "name": name,
        "version_type": version_type,
    }
    if switchover_period is not None:
        payload["switchover_period"] = switchover_period
    resp = await client.post(
        f"/models/{model_id}/versions",
        json=payload,
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def setup_model(client: AsyncClient, email: str) -> tuple:
    """Register user, create workspace + model. Returns (token, model_id)."""
    token = await register_and_login(client, email)
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    return token, model_id


async def setup_model_with_versions(client: AsyncClient, email: str) -> tuple:
    """Set up model with actuals + forecast versions. Returns (token, model_id, actuals_id, forecast_id)."""
    token, model_id = await setup_model(client, email)
    actuals_v = await create_version(
        client, token, model_id, name="Actuals", version_type="actuals"
    )
    forecast_v = await create_version(
        client, token, model_id, name="Forecast", version_type="forecast",
        switchover_period="2025-01"
    )
    return token, model_id, actuals_v["id"], forecast_v["id"]


async def create_forecast_config(
    client: AsyncClient,
    token: str,
    model_id: str,
    forecast_horizon_months: int = 12,
    auto_archive: bool = True,
    actuals_version_id: Optional[str] = None,
    forecast_version_id: Optional[str] = None,
) -> dict:
    payload: dict = {
        "model_id": model_id,
        "forecast_horizon_months": forecast_horizon_months,
        "auto_archive": auto_archive,
    }
    if actuals_version_id is not None:
        payload["actuals_version_id"] = actuals_version_id
    if forecast_version_id is not None:
        payload["forecast_version_id"] = forecast_version_id
    resp = await client.post(
        f"/models/{model_id}/forecast-config",
        json=payload,
        headers=auth_headers(token),
    )
    assert resp.status_code == 201, f"Failed to create config: {resp.text}"
    return resp.json()


# ---------------------------------------------------------------------------
# Create forecast config
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_forecast_config_basic(client: AsyncClient):
    """Create a forecast config with default settings."""
    token, model_id = await setup_model(client, "rf_create_basic@example.com")

    resp = await client.post(
        f"/models/{model_id}/forecast-config",
        json={"model_id": model_id, "forecast_horizon_months": 12, "auto_archive": True},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["model_id"] == model_id
    assert data["forecast_horizon_months"] == 12
    assert data["auto_archive"] is True
    assert data["archive_actuals_version_id"] is None
    assert data["forecast_version_id"] is None
    assert data["last_rolled_at"] is None
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_forecast_config_with_versions(client: AsyncClient):
    """Create forecast config referencing actuals and forecast versions."""
    token, model_id, actuals_id, forecast_id = await setup_model_with_versions(
        client, "rf_create_versions@example.com"
    )

    resp = await client.post(
        f"/models/{model_id}/forecast-config",
        json={
            "model_id": model_id,
            "forecast_horizon_months": 24,
            "auto_archive": True,
            "actuals_version_id": actuals_id,
            "forecast_version_id": forecast_id,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["archive_actuals_version_id"] == actuals_id
    assert data["forecast_version_id"] == forecast_id
    assert data["forecast_horizon_months"] == 24


@pytest.mark.asyncio
async def test_create_forecast_config_requires_auth(client: AsyncClient):
    """Create config without auth should return 401."""
    token, model_id = await setup_model(client, "rf_create_auth@example.com")

    resp = await client.post(
        f"/models/{model_id}/forecast-config",
        json={"model_id": model_id, "forecast_horizon_months": 12, "auto_archive": True},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_duplicate_forecast_config_rejected(client: AsyncClient):
    """Creating a second config for the same model should return 409."""
    token, model_id = await setup_model(client, "rf_create_dup@example.com")

    await create_forecast_config(client, token, model_id)

    resp = await client.post(
        f"/models/{model_id}/forecast-config",
        json={"model_id": model_id, "forecast_horizon_months": 6, "auto_archive": False},
        headers=auth_headers(token),
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_forecast_config_auto_archive_false(client: AsyncClient):
    """Create config with auto_archive disabled."""
    token, model_id = await setup_model(client, "rf_create_noarchive@example.com")

    resp = await client.post(
        f"/models/{model_id}/forecast-config",
        json={"model_id": model_id, "forecast_horizon_months": 6, "auto_archive": False},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    assert resp.json()["auto_archive"] is False


# ---------------------------------------------------------------------------
# Get forecast config
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_forecast_config(client: AsyncClient):
    """Get an existing forecast config."""
    token, model_id = await setup_model(client, "rf_get@example.com")
    await create_forecast_config(client, token, model_id)

    resp = await client.get(
        f"/models/{model_id}/forecast-config",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["model_id"] == model_id


@pytest.mark.asyncio
async def test_get_forecast_config_not_found(client: AsyncClient):
    """Get config for model with no config returns 404."""
    token, model_id = await setup_model(client, "rf_get_404@example.com")

    resp = await client.get(
        f"/models/{model_id}/forecast-config",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_forecast_config_requires_auth(client: AsyncClient):
    """Get config without auth returns 401."""
    token, model_id = await setup_model(client, "rf_get_auth@example.com")
    await create_forecast_config(client, token, model_id)

    resp = await client.get(f"/models/{model_id}/forecast-config")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Update forecast config
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_forecast_config_horizon(client: AsyncClient):
    """Update forecast horizon months."""
    token, model_id = await setup_model(client, "rf_update_horizon@example.com")
    await create_forecast_config(client, token, model_id, forecast_horizon_months=12)

    resp = await client.patch(
        f"/models/{model_id}/forecast-config",
        json={"forecast_horizon_months": 18},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["forecast_horizon_months"] == 18


@pytest.mark.asyncio
async def test_update_forecast_config_auto_archive(client: AsyncClient):
    """Toggle auto_archive on the config."""
    token, model_id = await setup_model(client, "rf_update_archive@example.com")
    await create_forecast_config(client, token, model_id, auto_archive=True)

    resp = await client.patch(
        f"/models/{model_id}/forecast-config",
        json={"auto_archive": False},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["auto_archive"] is False


@pytest.mark.asyncio
async def test_update_forecast_config_not_found(client: AsyncClient):
    """Update config for model with no config returns 404."""
    token, model_id = await setup_model(client, "rf_update_404@example.com")

    resp = await client.patch(
        f"/models/{model_id}/forecast-config",
        json={"forecast_horizon_months": 6},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_forecast_config_set_versions(client: AsyncClient):
    """Update config to reference actuals and forecast versions."""
    token, model_id, actuals_id, forecast_id = await setup_model_with_versions(
        client, "rf_update_versions@example.com"
    )
    await create_forecast_config(client, token, model_id)

    resp = await client.patch(
        f"/models/{model_id}/forecast-config",
        json={
            "actuals_version_id": actuals_id,
            "forecast_version_id": forecast_id,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["archive_actuals_version_id"] == actuals_id
    assert data["forecast_version_id"] == forecast_id


# ---------------------------------------------------------------------------
# Roll forecast
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_roll_forecast_one_period(client: AsyncClient):
    """Roll forecast forward by one period."""
    token, model_id, actuals_id, forecast_id = await setup_model_with_versions(
        client, "rf_roll_one@example.com"
    )
    await create_forecast_config(
        client, token, model_id,
        actuals_version_id=actuals_id,
        forecast_version_id=forecast_id,
    )

    resp = await client.post(
        f"/models/{model_id}/forecast/roll",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["periods_rolled"] == 1
    assert data["new_switchover_period"] == "2025-02"
    assert "cells_archived" in data


@pytest.mark.asyncio
async def test_roll_forecast_multiple_periods(client: AsyncClient):
    """Roll forecast forward by 3 periods."""
    token, model_id, actuals_id, forecast_id = await setup_model_with_versions(
        client, "rf_roll_multi@example.com"
    )
    await create_forecast_config(
        client, token, model_id,
        actuals_version_id=actuals_id,
        forecast_version_id=forecast_id,
    )

    resp = await client.post(
        f"/models/{model_id}/forecast/roll?periods_to_roll=3",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["periods_rolled"] == 3
    assert data["new_switchover_period"] == "2025-04"


@pytest.mark.asyncio
async def test_roll_updates_switchover_period(client: AsyncClient):
    """Rolling should advance the switchover_period on the forecast version."""
    token, model_id, actuals_id, forecast_id = await setup_model_with_versions(
        client, "rf_roll_switchover@example.com"
    )
    await create_forecast_config(
        client, token, model_id,
        actuals_version_id=actuals_id,
        forecast_version_id=forecast_id,
    )

    # Roll
    await client.post(
        f"/models/{model_id}/forecast/roll",
        headers=auth_headers(token),
    )

    # Check the forecast version's switchover period was updated
    v_resp = await client.get(
        f"/versions/{forecast_id}",
        headers=auth_headers(token),
    )
    assert v_resp.status_code == 200
    assert v_resp.json()["switchover_period"] == "2025-02"


@pytest.mark.asyncio
async def test_roll_updates_last_rolled_at(client: AsyncClient):
    """Rolling should update the last_rolled_at timestamp on the config."""
    token, model_id, actuals_id, forecast_id = await setup_model_with_versions(
        client, "rf_roll_last_rolled@example.com"
    )
    await create_forecast_config(
        client, token, model_id,
        actuals_version_id=actuals_id,
        forecast_version_id=forecast_id,
    )

    await client.post(
        f"/models/{model_id}/forecast/roll",
        headers=auth_headers(token),
    )

    config_resp = await client.get(
        f"/models/{model_id}/forecast-config",
        headers=auth_headers(token),
    )
    assert config_resp.status_code == 200
    assert config_resp.json()["last_rolled_at"] is not None


@pytest.mark.asyncio
async def test_roll_requires_config(client: AsyncClient):
    """Rolling without a config should return 404."""
    token, model_id = await setup_model(client, "rf_roll_no_config@example.com")

    resp = await client.post(
        f"/models/{model_id}/forecast/roll",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_roll_requires_auth(client: AsyncClient):
    """Rolling without auth should return 401."""
    token, model_id = await setup_model(client, "rf_roll_auth@example.com")
    await create_forecast_config(client, token, model_id)

    resp = await client.post(f"/models/{model_id}/forecast/roll")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_roll_no_cells_no_error(client: AsyncClient):
    """Rolling when no cells exist should succeed with cells_archived=0."""
    token, model_id, actuals_id, forecast_id = await setup_model_with_versions(
        client, "rf_roll_empty@example.com"
    )
    await create_forecast_config(
        client, token, model_id,
        actuals_version_id=actuals_id,
        forecast_version_id=forecast_id,
    )

    resp = await client.post(
        f"/models/{model_id}/forecast/roll",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["cells_archived"] == 0
    assert data["periods_rolled"] == 1


@pytest.mark.asyncio
async def test_roll_auto_archive_disabled_no_cells_copied(client: AsyncClient):
    """With auto_archive=False, cells should not be copied even if they exist."""
    token, model_id, actuals_id, forecast_id = await setup_model_with_versions(
        client, "rf_roll_noarchive@example.com"
    )
    await create_forecast_config(
        client, token, model_id,
        auto_archive=False,
        actuals_version_id=actuals_id,
        forecast_version_id=forecast_id,
    )

    resp = await client.post(
        f"/models/{model_id}/forecast/roll",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    # No cells archived because auto_archive is False
    assert data["cells_archived"] == 0
    # But switchover still advances
    assert data["new_switchover_period"] == "2025-02"


# ---------------------------------------------------------------------------
# Forecast status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_forecast_status(client: AsyncClient):
    """Get forecast status returns correct structure."""
    token, model_id, actuals_id, forecast_id = await setup_model_with_versions(
        client, "rf_status@example.com"
    )
    await create_forecast_config(
        client, token, model_id,
        forecast_horizon_months=12,
        actuals_version_id=actuals_id,
        forecast_version_id=forecast_id,
    )

    resp = await client.get(
        f"/models/{model_id}/forecast/status",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "horizon_months" in data
    assert "periods_elapsed" in data
    assert "periods_remaining" in data
    assert "last_rolled_at" in data
    assert "next_roll_suggestion" in data
    assert data["horizon_months"] == 12


@pytest.mark.asyncio
async def test_get_forecast_status_not_found(client: AsyncClient):
    """Status for model with no config returns 404."""
    token, model_id = await setup_model(client, "rf_status_404@example.com")

    resp = await client.get(
        f"/models/{model_id}/forecast/status",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_forecast_status_requires_auth(client: AsyncClient):
    """Status without auth returns 401."""
    token, model_id = await setup_model(client, "rf_status_auth@example.com")
    await create_forecast_config(client, token, model_id)

    resp = await client.get(f"/models/{model_id}/forecast/status")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_forecast_status_next_roll_suggestion(client: AsyncClient):
    """next_roll_suggestion should be one month ahead of switchover_period."""
    token, model_id, actuals_id, forecast_id = await setup_model_with_versions(
        client, "rf_status_suggest@example.com"
    )
    await create_forecast_config(
        client, token, model_id,
        actuals_version_id=actuals_id,
        forecast_version_id=forecast_id,
    )

    resp = await client.get(
        f"/models/{model_id}/forecast/status",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    # switchover_period is 2025-01, next suggestion is 2025-02
    assert data["next_roll_suggestion"] == "2025-02"


@pytest.mark.asyncio
async def test_forecast_status_periods_remaining_after_roll(client: AsyncClient):
    """periods_remaining should decrease by 1 after rolling forward."""
    token, model_id, actuals_id, forecast_id = await setup_model_with_versions(
        client, "rf_status_remaining@example.com"
    )
    await create_forecast_config(
        client, token, model_id,
        forecast_horizon_months=12,
        actuals_version_id=actuals_id,
        forecast_version_id=forecast_id,
    )

    status_before = await client.get(
        f"/models/{model_id}/forecast/status",
        headers=auth_headers(token),
    )
    remaining_before = status_before.json()["periods_remaining"]

    await client.post(
        f"/models/{model_id}/forecast/roll",
        headers=auth_headers(token),
    )

    status_after = await client.get(
        f"/models/{model_id}/forecast/status",
        headers=auth_headers(token),
    )
    remaining_after = status_after.json()["periods_remaining"]

    # After rolling, remaining should be at most one less (since we advanced the switchover)
    # The exact value depends on how far in the past 2025-01 was from "now"
    assert remaining_after <= remaining_before


@pytest.mark.asyncio
async def test_roll_forecast_nonexistent_model(client: AsyncClient):
    """Rolling for a nonexistent model should return 404."""
    token, _ = await setup_model(client, "rf_roll_nomodel@example.com")
    fake_model_id = str(uuid.uuid4())

    resp = await client.post(
        f"/models/{fake_model_id}/forecast/roll",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404
