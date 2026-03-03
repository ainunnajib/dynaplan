from typing import Tuple

import pytest
from httpx import AsyncClient


async def register_and_login(
    client: AsyncClient, email: str, password: str = "testpass123"
) -> str:
    await client.post(
        "/auth/register",
        json={
            "email": email,
            "full_name": "Test User",
            "password": password,
        },
    )
    resp = await client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def create_workspace(client: AsyncClient, token: str) -> str:
    resp = await client.post(
        "/workspaces/",
        json={"name": "Workspace"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_model(client: AsyncClient, token: str, workspace_id: str) -> str:
    resp = await client.post(
        "/models",
        json={"name": "Model", "workspace_id": workspace_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_dimension(client: AsyncClient, token: str, model_id: str, name: str) -> str:
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


async def create_module(client: AsyncClient, token: str, model_id: str) -> str:
    resp = await client.post(
        f"/models/{model_id}/modules",
        json={"name": "Module"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def setup_model_context(client: AsyncClient, email: str) -> Tuple[str, str, str]:
    token = await register_and_login(client, email)
    workspace_id = await create_workspace(client, token)
    model_id = await create_model(client, token, workspace_id)
    module_id = await create_module(client, token, model_id)
    return token, model_id, module_id


@pytest.mark.asyncio
async def test_list_line_items_for_dimension_endpoint(client: AsyncClient):
    token, model_id, module_id = await setup_model_context(
        client, "li_dim_query@example.com"
    )

    dim_region = await create_dimension(client, token, model_id, "Region")
    dim_product = await create_dimension(client, token, model_id, "Product")

    li_region_resp = await client.post(
        f"/modules/{module_id}/line-items",
        json={"name": "By Region", "applies_to_dimensions": [dim_region]},
        headers=auth_headers(token),
    )
    assert li_region_resp.status_code == 201
    li_region = li_region_resp.json()["id"]

    li_product_resp = await client.post(
        f"/modules/{module_id}/line-items",
        json={"name": "By Product", "applies_to_dimensions": [dim_product]},
        headers=auth_headers(token),
    )
    assert li_product_resp.status_code == 201

    li_both_resp = await client.post(
        f"/modules/{module_id}/line-items",
        json={
            "name": "By Region and Product",
            "applies_to_dimensions": [dim_region, dim_product],
        },
        headers=auth_headers(token),
    )
    assert li_both_resp.status_code == 201
    li_both = li_both_resp.json()["id"]

    query_resp = await client.get(
        f"/dimensions/{dim_region}/line-items",
        headers=auth_headers(token),
    )
    assert query_resp.status_code == 200

    line_item_ids = {line_item["id"] for line_item in query_resp.json()}
    assert li_region in line_item_ids
    assert li_both in line_item_ids
    assert len(line_item_ids) == 2


@pytest.mark.asyncio
async def test_cell_write_validates_line_item_applies_to_dimensions(client: AsyncClient):
    token, model_id, module_id = await setup_model_context(
        client, "li_dim_cell_validation@example.com"
    )

    dim_a = await create_dimension(client, token, model_id, "Dim A")
    dim_b = await create_dimension(client, token, model_id, "Dim B")
    dim_c = await create_dimension(client, token, model_id, "Dim C")

    a1 = await create_dimension_item(client, token, dim_a, "A1", "A1")
    b1 = await create_dimension_item(client, token, dim_b, "B1", "B1")
    c1 = await create_dimension_item(client, token, dim_c, "C1", "C1")

    line_item_resp = await client.post(
        f"/modules/{module_id}/line-items",
        json={"name": "Constrained", "applies_to_dimensions": [dim_a, dim_b]},
        headers=auth_headers(token),
    )
    assert line_item_resp.status_code == 201
    line_item_id = line_item_resp.json()["id"]

    wrong_count_resp = await client.post(
        "/cells",
        json={"line_item_id": line_item_id, "dimension_members": [a1], "value": 1.0},
        headers=auth_headers(token),
    )
    assert wrong_count_resp.status_code == 400

    wrong_dimension_resp = await client.post(
        "/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": [a1, c1],
            "value": 2.0,
        },
        headers=auth_headers(token),
    )
    assert wrong_dimension_resp.status_code == 400

    valid_resp = await client.post(
        "/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": [a1, b1],
            "value": 3.0,
        },
        headers=auth_headers(token),
    )
    assert valid_resp.status_code == 200
    assert valid_resp.json()["value"] == 3.0


@pytest.mark.asyncio
async def test_applies_to_dimensions_deduplicates_dimension_ids(client: AsyncClient):
    token, model_id, module_id = await setup_model_context(
        client, "li_dim_dedupe@example.com"
    )

    dim_a = await create_dimension(client, token, model_id, "Dim A")
    dim_b = await create_dimension(client, token, model_id, "Dim B")

    resp = await client.post(
        f"/modules/{module_id}/line-items",
        json={
            "name": "Deduped",
            "applies_to_dimensions": [dim_a, dim_a, dim_b, dim_b],
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    assert resp.json()["applies_to_dimensions"] == [dim_a, dim_b]
