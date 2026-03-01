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
