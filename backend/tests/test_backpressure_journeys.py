import asyncio
from typing import Any

import pytest
from httpx import AsyncClient, Response


async def register_and_login(
    client: AsyncClient, email: str, password: str = "testpass123"
) -> str:
    await client.post(
        "/auth/register",
        json={
            "email": email,
            "full_name": "Backpressure User",
            "password": password,
        },
    )
    resp = await client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def create_workspace(client: AsyncClient, token: str, name: str) -> str:
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
    name: str,
) -> str:
    resp = await client.post(
        "/models",
        json={"name": name, "workspace_id": workspace_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_module(
    client: AsyncClient,
    token: str,
    model_id: str,
    name: str,
) -> str:
    resp = await client.post(
        f"/models/{model_id}/modules",
        json={"name": name},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_line_item(
    client: AsyncClient,
    token: str,
    module_id: str,
    name: str,
) -> str:
    resp = await client.post(
        f"/modules/{module_id}/line-items",
        json={
            "name": name,
            "format": "number",
            "summary_method": "sum",
            "applies_to_dimensions": [],
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_dimension(
    client: AsyncClient,
    token: str,
    model_id: str,
    name: str,
) -> str:
    resp = await client.post(
        f"/models/{model_id}/dimensions",
        json={"name": name, "dimension_type": "custom"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_dimension_item(
    client: AsyncClient,
    token: str,
    dimension_id: str,
    name: str,
    code: str,
) -> str:
    resp = await client.post(
        f"/dimensions/{dimension_id}/items",
        json={"name": name, "code": code, "sort_order": 0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_version(
    client: AsyncClient,
    token: str,
    model_id: str,
    name: str,
    version_type: str,
) -> str:
    resp = await client.post(
        f"/models/{model_id}/versions",
        json={"name": name, "version_type": version_type},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def run_concurrent(limit: int, coroutines: list[Any]) -> list[Any]:
    semaphore = asyncio.Semaphore(limit)

    async def guarded(coro: Any) -> Any:
        async with semaphore:
            return await coro

    return await asyncio.gather(*(guarded(c) for c in coroutines))


@pytest.mark.asyncio
async def test_auth_me_mixed_concurrency_keeps_valid_token_stable(client: AsyncClient):
    token = await register_and_login(client, "bp_auth_stable@example.com")

    valid_calls = [
        client.get("/auth/me", headers=auth_headers(token))
        for _ in range(40)
    ]
    invalid_calls = [
        client.get("/auth/me", headers=auth_headers(f"invalid-token-{i}"))
        for i in range(40)
    ]
    anonymous_calls = [client.get("/auth/me") for _ in range(40)]

    valid_responses: list[Response] = await run_concurrent(20, valid_calls)
    invalid_responses: list[Response] = await run_concurrent(20, invalid_calls)
    anonymous_responses: list[Response] = await run_concurrent(20, anonymous_calls)

    assert all(r.status_code == 200 for r in valid_responses)
    assert all(r.status_code == 401 for r in invalid_responses)
    assert all(r.status_code == 401 for r in anonymous_responses)


@pytest.mark.asyncio
async def test_redirected_authenticated_workspace_list_under_load(client: AsyncClient):
    token = await register_and_login(client, "bp_redirects@example.com")

    # Seed some data first.
    await create_workspace(client, token, "BP Redirect WS 1")
    await create_workspace(client, token, "BP Redirect WS 2")

    authed_calls = [
        client.get(
            "/workspaces",
            headers=auth_headers(token),
            follow_redirects=True,
        )
        for _ in range(60)
    ]
    anonymous_calls = [
        client.get("/workspaces", follow_redirects=True) for _ in range(30)
    ]

    authed_responses: list[Response] = await run_concurrent(25, authed_calls)
    anonymous_responses: list[Response] = await run_concurrent(25, anonymous_calls)

    assert all(r.status_code == 200 for r in authed_responses)
    assert all(isinstance(r.json(), list) for r in authed_responses)
    assert all(r.status_code == 401 for r in anonymous_responses)


@pytest.mark.asyncio
async def test_concurrent_create_chain_has_no_401_or_5xx(client: AsyncClient):
    token = await register_and_login(client, "bp_create_chain@example.com")

    workspace_create_calls = [
        client.post(
            "/workspaces/",
            json={"name": f"BP WS {i}"},
            headers=auth_headers(token),
        )
        for i in range(10)
    ]
    workspace_responses: list[Response] = await run_concurrent(4, workspace_create_calls)
    assert all(r.status_code == 201 for r in workspace_responses)
    workspace_ids = [r.json()["id"] for r in workspace_responses]

    target_workspace_id = workspace_ids[0]
    model_create_calls = [
        client.post(
            "/models",
            json={"name": f"BP Model {i}", "workspace_id": target_workspace_id},
            headers=auth_headers(token),
        )
        for i in range(10)
    ]
    model_responses: list[Response] = await run_concurrent(4, model_create_calls)
    assert all(r.status_code == 201 for r in model_responses)
    model_ids = [r.json()["id"] for r in model_responses]

    target_model_id = model_ids[0]
    module_create_calls = [
        client.post(
            f"/models/{target_model_id}/modules",
            json={"name": f"BP Module {i}"},
            headers=auth_headers(token),
        )
        for i in range(8)
    ]
    dashboard_create_calls = [
        client.post(
            f"/models/{target_model_id}/dashboards",
            json={"name": f"BP Dashboard {i}"},
            headers=auth_headers(token),
        )
        for i in range(8)
    ]
    mixed_responses: list[Response] = await run_concurrent(
        4, module_create_calls + dashboard_create_calls
    )

    # Under backpressure we still expect success for this happy-path burst.
    assert all(r.status_code == 201 for r in mixed_responses)
    assert all(r.status_code not in {401, 403} for r in mixed_responses)
    assert all(r.status_code < 500 for r in mixed_responses)


@pytest.mark.asyncio
async def test_dashboard_burst_mixed_users_enforces_ownership(client: AsyncClient):
    token_a = await register_and_login(client, "bp_dash_owner_a@example.com")
    token_b = await register_and_login(client, "bp_dash_owner_b@example.com")

    workspace_id = await create_workspace(client, token_a, "BP Dash WS")
    model_id = await create_model(client, token_a, workspace_id, "BP Dash Model")

    create_calls = [
        client.post(
            f"/models/{model_id}/dashboards",
            json={"name": f"Burst Dashboard {i}"},
            headers=auth_headers(token_a),
        )
        for i in range(12)
    ]
    create_responses: list[Response] = await run_concurrent(10, create_calls)
    assert all(r.status_code == 201 for r in create_responses)
    dashboard_ids = [r.json()["id"] for r in create_responses]

    owner_patch_calls = [
        client.patch(
            f"/dashboards/{dash_id}",
            json={"name": f"Owner Updated {i}"},
            headers=auth_headers(token_a),
        )
        for i, dash_id in enumerate(dashboard_ids)
    ]
    non_owner_patch_calls = [
        client.patch(
            f"/dashboards/{dash_id}",
            json={"name": f"Attacker Updated {i}"},
            headers=auth_headers(token_b),
        )
        for i, dash_id in enumerate(dashboard_ids)
    ]

    owner_patch_responses: list[Response] = await run_concurrent(10, owner_patch_calls)
    non_owner_patch_responses: list[Response] = await run_concurrent(
        10, non_owner_patch_calls
    )

    assert all(r.status_code == 200 for r in owner_patch_responses)
    assert all(r.status_code == 403 for r in non_owner_patch_responses)

    # Delete race: owner deletes, non-owner attempts same targets concurrently.
    target_delete_ids = dashboard_ids[:6]
    owner_delete_calls = [
        client.delete(f"/dashboards/{dash_id}", headers=auth_headers(token_a))
        for dash_id in target_delete_ids
    ]
    non_owner_delete_calls = [
        client.delete(f"/dashboards/{dash_id}", headers=auth_headers(token_b))
        for dash_id in target_delete_ids
    ]
    owner_delete_responses: list[Response] = await run_concurrent(10, owner_delete_calls)
    non_owner_delete_responses: list[Response] = await run_concurrent(
        10, non_owner_delete_calls
    )

    assert all(r.status_code == 204 for r in owner_delete_responses)
    assert all(r.status_code in {403, 404} for r in non_owner_delete_responses)

    # Remaining dashboards should still be listable for the owner.
    list_resp = await client.get(
        f"/models/{model_id}/dashboards",
        headers=auth_headers(token_a),
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 6


@pytest.mark.asyncio
async def test_auth_me_reads_stay_healthy_during_write_burst(client: AsyncClient):
    token = await register_and_login(client, "bp_reads_during_writes@example.com")

    write_calls = [
        client.post(
            "/workspaces/",
            json={"name": f"Burst WS {i}"},
            headers=auth_headers(token),
        )
        for i in range(40)
    ]
    read_calls = [client.get("/auth/me", headers=auth_headers(token)) for _ in range(80)]

    write_responses: list[Response] = await run_concurrent(20, write_calls)
    read_responses: list[Response] = await run_concurrent(20, read_calls)

    assert all(r.status_code == 201 for r in write_responses)
    assert all(r.status_code == 200 for r in read_responses)
    assert all(r.status_code < 500 for r in write_responses + read_responses)


@pytest.mark.asyncio
@pytest.mark.backpressure
async def test_module_grid_cells_read_write_burst_stays_healthy(client: AsyncClient):
    token = await register_and_login(client, "bp_grid_cells@example.com")

    workspace_id = await create_workspace(client, token, "BP Grid Cells WS")
    model_id = await create_model(client, token, workspace_id, "BP Grid Cells Model")
    module_id = await create_module(client, token, model_id, "BP Grid Cells Module")
    line_item_ids = [
        await create_line_item(client, token, module_id, f"Revenue {i}")
        for i in range(5)
    ]

    write_calls = [
        client.put(
            f"/modules/{module_id}/cells",
            json={
                "line_item_id": line_item_ids[i % len(line_item_ids)],
                "dimension_member_ids": [],
                "value": i,
            },
            headers=auth_headers(token),
        )
        for i in range(100)
    ]
    read_calls = [
        client.get(
            f"/modules/{module_id}/cells",
            headers=auth_headers(token),
        )
        for _ in range(100)
    ]

    responses: list[Response] = await run_concurrent(30, write_calls + read_calls)
    assert all(r.status_code < 500 for r in responses)
    assert all(r.status_code not in {401, 403} for r in responses)

    write_responses = [r for r in responses if r.request.method == "PUT"]
    read_responses = [r for r in responses if r.request.method == "GET"]
    assert all(r.status_code == 200 for r in write_responses)
    assert all(r.status_code == 200 for r in read_responses)

    final_read = await client.get(
        f"/modules/{module_id}/cells",
        headers=auth_headers(token),
    )
    assert final_read.status_code == 200
    assert len(final_read.json()) >= len(line_item_ids)


@pytest.mark.asyncio
@pytest.mark.backpressure
async def test_blueprint_line_item_burst_then_grid_edits_remain_stable(client: AsyncClient):
    token = await register_and_login(client, "bp_blueprint_grid@example.com")

    workspace_id = await create_workspace(client, token, "BP Blueprint WS")
    model_id = await create_model(client, token, workspace_id, "BP Blueprint Model")
    module_id = await create_module(client, token, model_id, "BP Blueprint Module")

    line_item_create_calls = [
        client.post(
            f"/modules/{module_id}/line-items",
            json={
                "name": f"Line Item {i}",
                "format": "number",
                "summary_method": "sum",
                "applies_to_dimensions": [],
            },
            headers=auth_headers(token),
        )
        for i in range(40)
    ]
    line_item_responses: list[Response] = await run_concurrent(12, line_item_create_calls)
    assert all(r.status_code == 201 for r in line_item_responses)
    line_item_ids = [r.json()["id"] for r in line_item_responses]

    grid_write_calls = [
        client.put(
            f"/modules/{module_id}/cells",
            json={
                "line_item_id": line_item_ids[i % len(line_item_ids)],
                "dimension_member_ids": [],
                "value": float(i),
            },
            headers=auth_headers(token),
        )
        for i in range(400)
    ]
    grid_read_calls = [
        client.get(
            f"/modules/{module_id}/cells",
            headers=auth_headers(token),
        )
        for _ in range(120)
    ]

    responses: list[Response] = await run_concurrent(30, grid_write_calls + grid_read_calls)
    assert all(r.status_code < 500 for r in responses)
    assert all(r.status_code not in {401, 403} for r in responses)

    write_responses = [r for r in responses if r.request.method == "PUT"]
    read_responses = [r for r in responses if r.request.method == "GET"]
    assert all(r.status_code == 200 for r in write_responses)
    assert all(r.status_code == 200 for r in read_responses)

    final_cells = await client.get(
        f"/modules/{module_id}/cells",
        headers=auth_headers(token),
    )
    assert final_cells.status_code == 200
    assert len(final_cells.json()) == len(line_item_ids)


@pytest.mark.asyncio
@pytest.mark.backpressure
async def test_apple_fpa_multidimension_bulk_write_and_query_burst(client: AsyncClient):
    token = await register_and_login(client, "bp_apple_fpa_burst@example.com")

    workspace_id = await create_workspace(client, token, "BP Apple FP&A WS")
    model_id = await create_model(client, token, workspace_id, "BP Apple FP&A Model")
    module_id = await create_module(client, token, model_id, "Global Revenue Planning")

    region_dim = await create_dimension(client, token, model_id, "Region")
    product_dim = await create_dimension(client, token, model_id, "Product Family")
    channel_dim = await create_dimension(client, token, model_id, "Channel")
    period_dim = await create_dimension(client, token, model_id, "Month")

    region_ids = [
        await create_dimension_item(client, token, region_dim, name, code)
        for name, code in [
            ("Americas", "AMER"),
            ("EMEA", "EMEA"),
            ("APAC", "APAC"),
        ]
    ]
    product_ids = [
        await create_dimension_item(client, token, product_dim, name, code)
        for name, code in [
            ("iPhone", "IPH"),
            ("Mac", "MAC"),
            ("iPad", "IPD"),
            ("Services", "SVC"),
        ]
    ]
    channel_ids = [
        await create_dimension_item(client, token, channel_dim, name, code)
        for name, code in [
            ("Retail", "RTL"),
            ("Online", "ONL"),
            ("Carrier", "CAR"),
        ]
    ]
    period_ids = [
        await create_dimension_item(client, token, period_dim, name, code)
        for name, code in [
            ("Jan", "2026-01"),
            ("Feb", "2026-02"),
            ("Mar", "2026-03"),
            ("Apr", "2026-04"),
        ]
    ]

    revenue_line_item_resp = await client.post(
        f"/modules/{module_id}/line-items",
        json={
            "name": "Net Revenue",
            "format": "number",
            "summary_method": "sum",
            "applies_to_dimensions": [region_dim, product_dim, channel_dim, period_dim],
        },
        headers=auth_headers(token),
    )
    assert revenue_line_item_resp.status_code == 201
    revenue_line_item_id = revenue_line_item_resp.json()["id"]

    actuals_version_id = await create_version(
        client,
        token,
        model_id,
        "Actuals FY26",
        "actuals",
    )
    forecast_version_id = await create_version(
        client,
        token,
        model_id,
        "Forecast FY26",
        "forecast",
    )

    base_cells: list[dict[str, Any]] = []
    index = 1
    for region_id in region_ids:
        for product_id in product_ids:
            for channel_id in channel_ids:
                for period_id in period_ids:
                    base_cells.append(
                        {
                            "dimension_members": [
                                region_id,
                                product_id,
                                channel_id,
                                period_id,
                            ],
                            "value": float(index * 1000),
                        }
                    )
                    index += 1

    all_cells: list[dict[str, Any]] = []
    for version_id in (actuals_version_id, forecast_version_id):
        for cell in base_cells:
            all_cells.append(
                {
                    "line_item_id": revenue_line_item_id,
                    "dimension_members": cell["dimension_members"],
                    "version_id": version_id,
                    "value": cell["value"],
                }
            )

    chunk_size = 48
    chunks = [all_cells[i:i + chunk_size] for i in range(0, len(all_cells), chunk_size)]
    bulk_write_calls = [
        client.post(
            "/cells/bulk",
            json={"cells": chunk},
            headers=auth_headers(token),
        )
        for chunk in chunks
    ]
    query_calls = [
        client.post(
            "/cells/query",
            json={
                "line_item_id": revenue_line_item_id,
                "version_id": actuals_version_id if i % 2 == 0 else forecast_version_id,
            },
            headers=auth_headers(token),
        )
        for i in range(60)
    ]

    responses: list[Response] = await run_concurrent(12, bulk_write_calls + query_calls)
    assert all(r.status_code < 500 for r in responses)
    assert all(r.status_code not in {401, 403} for r in responses)

    write_responses = [r for r in responses if r.request.url.path.endswith("/cells/bulk")]
    query_responses = [r for r in responses if r.request.url.path.endswith("/cells/query")]
    assert all(r.status_code == 200 for r in write_responses)
    assert all(r.status_code == 200 for r in query_responses)

    expected_per_version = len(base_cells)
    actuals_cells = await client.post(
        "/cells/query",
        json={
            "line_item_id": revenue_line_item_id,
            "version_id": actuals_version_id,
        },
        headers=auth_headers(token),
    )
    forecast_cells = await client.post(
        "/cells/query",
        json={
            "line_item_id": revenue_line_item_id,
            "version_id": forecast_version_id,
        },
        headers=auth_headers(token),
    )
    assert actuals_cells.status_code == 200
    assert forecast_cells.status_code == 200
    assert len(actuals_cells.json()) == expected_per_version
    assert len(forecast_cells.json()) == expected_per_version
