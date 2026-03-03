from typing import List, Optional

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


async def create_dimension(
    client: AsyncClient,
    token: str,
    model_id: str,
    name: str,
    dimension_type: str = "custom",
) -> str:
    resp = await client.post(
        f"/models/{model_id}/dimensions",
        json={"name": name, "dimension_type": dimension_type},
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
        json={"name": "Sales"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_line_item(
    client: AsyncClient,
    token: str,
    module_id: str,
    applies_to_dimensions: Optional[List[str]] = None,
) -> str:
    payload = {"name": "Revenue", "format": "number"}
    if applies_to_dimensions is not None:
        payload["applies_to_dimensions"] = applies_to_dimensions
    resp = await client.post(
        f"/modules/{module_id}/line-items",
        json=payload,
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_create_composite_dimension_success(client: AsyncClient):
    token = await register_and_login(client, "composite_create@example.com")
    workspace_id = await create_workspace(client, token)
    model_id = await create_model(client, token, workspace_id)

    products_id = await create_dimension(client, token, model_id, "Products")
    regions_id = await create_dimension(client, token, model_id, "Regions")

    resp = await client.post(
        f"/models/{model_id}/composite-dimensions",
        json={
            "name": "Product x Region",
            "source_dimension_ids": [products_id, regions_id],
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    composite = resp.json()
    assert composite["model_id"] == model_id
    assert composite["name"] == "Product x Region"
    assert composite["dimension_type"] == "composite"
    assert composite["source_dimension_ids"] == [products_id, regions_id]

    list_resp = await client.get(
        f"/models/{model_id}/composite-dimensions",
        headers=auth_headers(token),
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1
    assert list_resp.json()[0]["id"] == composite["id"]

    dimensions_resp = await client.get(
        f"/models/{model_id}/dimensions",
        headers=auth_headers(token),
    )
    assert dimensions_resp.status_code == 200
    composite_dimension = next(
        (
            dimension
            for dimension in dimensions_resp.json()
            if dimension["id"] == composite["dimension_id"]
        ),
        None,
    )
    assert composite_dimension is not None
    assert composite_dimension["dimension_type"] == "composite"


@pytest.mark.asyncio
async def test_create_composite_dimension_validates_sources(client: AsyncClient):
    token = await register_and_login(client, "composite_source_validation@example.com")
    workspace_id = await create_workspace(client, token)
    model_id = await create_model(client, token, workspace_id)

    products_id = await create_dimension(client, token, model_id, "Products")

    one_source_resp = await client.post(
        f"/models/{model_id}/composite-dimensions",
        json={"name": "Invalid", "source_dimension_ids": [products_id]},
        headers=auth_headers(token),
    )
    assert one_source_resp.status_code == 400

    duplicate_source_resp = await client.post(
        f"/models/{model_id}/composite-dimensions",
        json={"name": "Invalid", "source_dimension_ids": [products_id, products_id]},
        headers=auth_headers(token),
    )
    assert duplicate_source_resp.status_code == 400


@pytest.mark.asyncio
async def test_create_composite_dimension_requires_same_model_sources(
    client: AsyncClient,
):
    token = await register_and_login(client, "composite_model_scope@example.com")
    workspace_id = await create_workspace(client, token)
    model_a_id = await create_model(client, token, workspace_id)
    model_b_id = await create_model(client, token, workspace_id)

    products_id = await create_dimension(client, token, model_a_id, "Products")
    regions_id = await create_dimension(client, token, model_b_id, "Regions")

    resp = await client.post(
        f"/models/{model_a_id}/composite-dimensions",
        json={
            "name": "Product x Region",
            "source_dimension_ids": [products_id, regions_id],
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_composite_dimension_sparse_intersections_created_on_cell_write(
    client: AsyncClient,
):
    token = await register_and_login(client, "composite_sparse@example.com")
    workspace_id = await create_workspace(client, token)
    model_id = await create_model(client, token, workspace_id)

    products_id = await create_dimension(client, token, model_id, "Products")
    regions_id = await create_dimension(client, token, model_id, "Regions")

    p1 = await create_dimension_item(client, token, products_id, "P1", "P1")
    p2 = await create_dimension_item(client, token, products_id, "P2", "P2")
    r1 = await create_dimension_item(client, token, regions_id, "R1", "R1")
    r2 = await create_dimension_item(client, token, regions_id, "R2", "R2")

    composite_resp = await client.post(
        f"/models/{model_id}/composite-dimensions",
        json={
            "name": "Product x Region",
            "source_dimension_ids": [products_id, regions_id],
        },
        headers=auth_headers(token),
    )
    assert composite_resp.status_code == 201
    composite_dimension_id = composite_resp.json()["dimension_id"]

    module_id = await create_module(client, token, model_id)
    line_item_id = await create_line_item(
        client,
        token,
        module_id,
        applies_to_dimensions=[composite_dimension_id],
    )

    write_1 = await client.post(
        "/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": [p1, r1],
            "value": 10.0,
        },
        headers=auth_headers(token),
    )
    assert write_1.status_code == 200
    first_dim_key = write_1.json()["dimension_key"]
    assert len(write_1.json()["dimension_members"]) == 1

    write_1_repeat = await client.post(
        "/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": [r1, p1],
            "value": 20.0,
        },
        headers=auth_headers(token),
    )
    assert write_1_repeat.status_code == 200
    assert write_1_repeat.json()["dimension_key"] == first_dim_key
    assert write_1_repeat.json()["value"] == 20.0

    write_2 = await client.post(
        "/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": [p2, r2],
            "value": 30.0,
        },
        headers=auth_headers(token),
    )
    assert write_2.status_code == 200
    assert write_2.json()["dimension_key"] != first_dim_key

    items_resp = await client.get(
        f"/dimensions/{composite_dimension_id}/items",
        headers=auth_headers(token),
    )
    assert items_resp.status_code == 200
    # Sparse behavior: only intersections with data are materialized.
    assert len(items_resp.json()) == 2

    query_resp = await client.post(
        "/cells/query",
        json={"line_item_id": line_item_id},
        headers=auth_headers(token),
    )
    assert query_resp.status_code == 200
    values = sorted(cell["value"] for cell in query_resp.json())
    assert values == [20.0, 30.0]


@pytest.mark.asyncio
async def test_composite_dimension_cell_write_validates_source_members(client: AsyncClient):
    token = await register_and_login(client, "composite_cell_validation@example.com")
    workspace_id = await create_workspace(client, token)
    model_id = await create_model(client, token, workspace_id)

    products_id = await create_dimension(client, token, model_id, "Products")
    regions_id = await create_dimension(client, token, model_id, "Regions")

    p1 = await create_dimension_item(client, token, products_id, "P1", "P1")
    p2 = await create_dimension_item(client, token, products_id, "P2", "P2")
    r1 = await create_dimension_item(client, token, regions_id, "R1", "R1")

    composite_resp = await client.post(
        f"/models/{model_id}/composite-dimensions",
        json={
            "name": "Product x Region",
            "source_dimension_ids": [products_id, regions_id],
        },
        headers=auth_headers(token),
    )
    assert composite_resp.status_code == 201
    composite_dimension_id = composite_resp.json()["dimension_id"]

    module_id = await create_module(client, token, model_id)
    line_item_id = await create_line_item(
        client,
        token,
        module_id,
        applies_to_dimensions=[composite_dimension_id],
    )

    missing_source_resp = await client.post(
        "/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": [p1],
            "value": 1.0,
        },
        headers=auth_headers(token),
    )
    assert missing_source_resp.status_code == 400

    wrong_source_set_resp = await client.post(
        "/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": [p1, p2],
            "value": 2.0,
        },
        headers=auth_headers(token),
    )
    assert wrong_source_set_resp.status_code == 400

    valid_resp = await client.post(
        "/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": [p1, r1],
            "value": 3.0,
        },
        headers=auth_headers(token),
    )
    assert valid_resp.status_code == 200


@pytest.mark.asyncio
async def test_dimension_api_rejects_direct_composite_creation(client: AsyncClient):
    token = await register_and_login(client, "composite_direct_dimension@example.com")
    workspace_id = await create_workspace(client, token)
    model_id = await create_model(client, token, workspace_id)

    resp = await client.post(
        f"/models/{model_id}/dimensions",
        json={"name": "Invalid Composite", "dimension_type": "composite"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 400
