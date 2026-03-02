import uuid
from typing import Dict

import pytest
from httpx import AsyncClient

from app.models.cell import CellValue
from app.services.version import get_cells_with_switchover
from tests.conftest import TestSession


async def register_and_login(client: AsyncClient, email: str, password: str = "testpass123") -> str:
    await client.post("/auth/register", json={
        "email": email,
        "full_name": "Test User",
        "password": password,
    })
    resp = await client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def auth_headers(token: str) -> Dict[str, str]:
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


async def create_module(client: AsyncClient, token: str, model_id: str, name: str = "Revenue") -> str:
    resp = await client.post(
        f"/models/{model_id}/modules",
        json={"name": name},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_line_item(client: AsyncClient, token: str, module_id: str, name: str = "Revenue Item") -> str:
    resp = await client.post(
        f"/modules/{module_id}/line-items",
        json={"name": name, "format": "number"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_version(
    client: AsyncClient,
    token: str,
    model_id: str,
    name: str,
    version_type: str = "forecast",
) -> str:
    resp = await client.post(
        f"/models/{model_id}/versions",
        json={"name": name, "version_type": version_type},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def setup_line_item(client: AsyncClient, email: str) -> Dict[str, str]:
    token = await register_and_login(client, email)
    workspace_id = await create_workspace(client, token)
    model_id = await create_model(client, token, workspace_id)
    module_id = await create_module(client, token, model_id)
    line_item_id = await create_line_item(client, token, module_id)
    return {
        "token": token,
        "model_id": model_id,
        "line_item_id": line_item_id,
    }


@pytest.mark.asyncio
async def test_write_cell_populates_version_id_from_dimension_members(client: AsyncClient):
    setup = await setup_line_item(client, "f060_members@example.com")
    token = setup["token"]
    model_id = setup["model_id"]
    line_item_id = setup["line_item_id"]

    version_id = await create_version(client, token, model_id, "Forecast V1")
    base_dim = str(uuid.uuid4())

    write_resp = await client.post(
        "/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": [version_id, base_dim],
            "value": 125.0,
        },
        headers=auth_headers(token),
    )
    assert write_resp.status_code == 200
    assert write_resp.json()["version_id"] == version_id

    query_resp = await client.post(
        "/cells/query",
        json={
            "line_item_id": line_item_id,
            "version_id": version_id,
        },
        headers=auth_headers(token),
    )
    assert query_resp.status_code == 200
    rows = query_resp.json()
    assert len(rows) == 1
    assert rows[0]["version_id"] == version_id
    assert rows[0]["value"] == 125.0


@pytest.mark.asyncio
async def test_write_cell_supports_explicit_version_id(client: AsyncClient):
    setup = await setup_line_item(client, "f060_explicit@example.com")
    token = setup["token"]
    model_id = setup["model_id"]
    line_item_id = setup["line_item_id"]

    version_id = await create_version(client, token, model_id, "Budget V1", "budget")
    base_dim = str(uuid.uuid4())

    write_resp = await client.post(
        "/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": [base_dim],
            "version_id": version_id,
            "value": 88.0,
        },
        headers=auth_headers(token),
    )
    assert write_resp.status_code == 200
    data = write_resp.json()
    assert data["version_id"] == version_id
    assert version_id in data["dimension_key"]


@pytest.mark.asyncio
async def test_compare_versions_aligns_on_base_key_with_version_id(client: AsyncClient):
    setup = await setup_line_item(client, "f060_compare@example.com")
    token = setup["token"]
    model_id = setup["model_id"]
    line_item_id = setup["line_item_id"]

    version_a = await create_version(client, token, model_id, "Version A")
    version_b = await create_version(client, token, model_id, "Version B")
    base_dim = str(uuid.uuid4())

    resp_a = await client.post(
        "/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": [base_dim],
            "version_id": version_a,
            "value": 100.0,
        },
        headers=auth_headers(token),
    )
    assert resp_a.status_code == 200

    resp_b = await client.post(
        "/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": [base_dim],
            "version_id": version_b,
            "value": 150.0,
        },
        headers=auth_headers(token),
    )
    assert resp_b.status_code == 200

    compare_resp = await client.post(
        "/versions/compare",
        json={
            "version_id_a": version_a,
            "version_id_b": version_b,
            "line_item_id": line_item_id,
        },
        headers=auth_headers(token),
    )
    assert compare_resp.status_code == 200
    compare_data = compare_resp.json()
    assert len(compare_data["cells"]) == 1
    cell = compare_data["cells"][0]
    assert cell["value_a"] == 100.0
    assert cell["value_b"] == 150.0
    assert cell["variance_absolute"] == pytest.approx(50.0)


@pytest.mark.asyncio
async def test_get_cells_with_switchover_prefers_actuals_before_period_and_forecast_after(
    client: AsyncClient,
):
    setup = await setup_line_item(client, "f060_switchover@example.com")
    token = setup["token"]
    model_id = setup["model_id"]
    line_item_id = uuid.UUID(setup["line_item_id"])

    actuals_version = uuid.UUID(
        await create_version(client, token, model_id, "Actuals", "actuals")
    )
    forecast_version = uuid.UUID(
        await create_version(client, token, model_id, "Forecast", "forecast")
    )
    base_dim = str(uuid.uuid4())

    async with TestSession() as db:
        db.add(
            CellValue(
                line_item_id=line_item_id,
                version_id=actuals_version,
                dimension_key="|".join(sorted([str(actuals_version), base_dim, "2024-12"])),
                value_number=10.0,
            )
        )
        db.add(
            CellValue(
                line_item_id=line_item_id,
                version_id=forecast_version,
                dimension_key="|".join(sorted([str(forecast_version), base_dim, "2024-12"])),
                value_number=20.0,
            )
        )
        db.add(
            CellValue(
                line_item_id=line_item_id,
                version_id=actuals_version,
                dimension_key="|".join(sorted([str(actuals_version), base_dim, "2025-01"])),
                value_number=30.0,
            )
        )
        db.add(
            CellValue(
                line_item_id=line_item_id,
                version_id=forecast_version,
                dimension_key="|".join(sorted([str(forecast_version), base_dim, "2025-01"])),
                value_number=40.0,
            )
        )
        await db.commit()

        effective_cells = await get_cells_with_switchover(
            db=db,
            line_item_id=line_item_id,
            actuals_version_id=actuals_version,
            forecast_version_id=forecast_version,
            switchover_period="2025-01",
        )

    values_by_period: Dict[str, float] = {}
    for cell in effective_cells:
        if "2024-12" in cell.dimension_key:
            values_by_period["2024-12"] = float(cell.value_number or 0.0)
        if "2025-01" in cell.dimension_key:
            values_by_period["2025-01"] = float(cell.value_number or 0.0)

    assert values_by_period["2024-12"] == 10.0
    assert values_by_period["2025-01"] == 40.0
