import uuid
from typing import List, Optional

import pytest
from httpx import AsyncClient


async def register_and_login(
    client: AsyncClient,
    email: str,
    password: str = "testpass123",
) -> str:
    await client.post(
        "/auth/register",
        json={
            "email": email,
            "full_name": "Module Cells User",
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


async def create_model(client: AsyncClient, token: str, workspace_id: str, name: str) -> str:
    resp = await client.post(
        "/models",
        json={"name": name, "workspace_id": workspace_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_module(client: AsyncClient, token: str, model_id: str, name: str) -> str:
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
    applies_to_dimensions: Optional[List[str]] = None,
) -> str:
    resp = await client.post(
        f"/modules/{module_id}/line-items",
        json={
            "name": name,
            "format": "number",
            "summary_method": "sum",
            "applies_to_dimensions": applies_to_dimensions or [],
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_get_module_cells_returns_dimension_member_ids(client: AsyncClient):
    token = await register_and_login(client, f"module_cells_get_{uuid.uuid4()}@example.com")
    workspace_id = await create_workspace(client, token, "Cells Workspace")
    model_id = await create_model(client, token, workspace_id, "Cells Model")
    module_id = await create_module(client, token, model_id, "Cells Module")

    dimension_resp = await client.post(
        f"/models/{model_id}/dimensions",
        json={"name": "Product", "dimension_type": "custom"},
        headers=auth_headers(token),
    )
    assert dimension_resp.status_code == 201
    dimension_id = dimension_resp.json()["id"]

    item_a_resp = await client.post(
        f"/dimensions/{dimension_id}/items",
        json={"name": "A", "code": "A"},
        headers=auth_headers(token),
    )
    item_b_resp = await client.post(
        f"/dimensions/{dimension_id}/items",
        json={"name": "B", "code": "B"},
        headers=auth_headers(token),
    )
    assert item_a_resp.status_code == 201
    assert item_b_resp.status_code == 201
    item_a_id = item_a_resp.json()["id"]
    item_b_id = item_b_resp.json()["id"]

    line_item_id = await create_line_item(
        client,
        token,
        module_id,
        "Revenue",
        applies_to_dimensions=[dimension_id],
    )

    seed_resp = await client.post(
        "/cells/bulk",
        json={
            "cells": [
                {
                    "line_item_id": line_item_id,
                    "dimension_members": [item_a_id],
                    "value": 10,
                },
                {
                    "line_item_id": line_item_id,
                    "dimension_members": [item_b_id],
                    "value": 20,
                },
            ]
        },
        headers=auth_headers(token),
    )
    assert seed_resp.status_code == 200

    resp = await client.get(
        f"/modules/{module_id}/cells",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200

    payload = resp.json()
    assert len(payload) == 2

    members_seen = {row["dimension_member_ids"][0] for row in payload}
    assert members_seen == {item_a_id, item_b_id}
    assert {row["value"] for row in payload} == {10.0, 20.0}


@pytest.mark.asyncio
async def test_get_module_cells_empty_when_no_cells_exist(client: AsyncClient):
    token = await register_and_login(client, f"module_cells_empty_{uuid.uuid4()}@example.com")
    workspace_id = await create_workspace(client, token, "Cells Empty Workspace")
    model_id = await create_model(client, token, workspace_id, "Cells Empty Model")
    module_id = await create_module(client, token, model_id, "Cells Empty Module")
    await create_line_item(client, token, module_id, "Revenue")

    resp = await client.get(
        f"/modules/{module_id}/cells",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_put_module_cells_upserts_and_get_roundtrip(client: AsyncClient):
    token = await register_and_login(client, f"module_cells_put_{uuid.uuid4()}@example.com")
    workspace_id = await create_workspace(client, token, "Cells Put Workspace")
    model_id = await create_model(client, token, workspace_id, "Cells Put Model")
    module_id = await create_module(client, token, model_id, "Cells Put Module")
    line_item_id = await create_line_item(client, token, module_id, "Revenue")

    put_resp = await client.put(
        f"/modules/{module_id}/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_member_ids": [],
            "value": 123,
        },
        headers=auth_headers(token),
    )
    assert put_resp.status_code == 200
    put_payload = put_resp.json()
    assert put_payload["line_item_id"] == line_item_id
    assert put_payload["dimension_member_ids"] == []
    assert put_payload["value"] == 123.0

    get_resp = await client.get(
        f"/modules/{module_id}/cells",
        headers=auth_headers(token),
    )
    assert get_resp.status_code == 200
    get_payload = get_resp.json()
    assert len(get_payload) == 1
    assert get_payload[0]["line_item_id"] == line_item_id
    assert get_payload[0]["dimension_member_ids"] == []
    assert get_payload[0]["value"] == 123.0


@pytest.mark.asyncio
async def test_put_module_cells_rejects_line_item_from_other_module(client: AsyncClient):
    token = await register_and_login(client, f"module_cells_wrong_mod_{uuid.uuid4()}@example.com")
    workspace_id = await create_workspace(client, token, "Cells Guard Workspace")
    model_id = await create_model(client, token, workspace_id, "Cells Guard Model")
    module_a_id = await create_module(client, token, model_id, "Cells Guard A")
    module_b_id = await create_module(client, token, model_id, "Cells Guard B")
    line_item_b_id = await create_line_item(client, token, module_b_id, "Revenue B")

    put_resp = await client.put(
        f"/modules/{module_a_id}/cells",
        json={
            "line_item_id": line_item_b_id,
            "dimension_member_ids": [],
            "value": 99,
        },
        headers=auth_headers(token),
    )
    assert put_resp.status_code == 400
    assert "does not belong to module" in put_resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_module_cells_page_supports_pagination(client: AsyncClient):
    token = await register_and_login(client, f"module_cells_page_{uuid.uuid4()}@example.com")
    workspace_id = await create_workspace(client, token, "Cells Page Workspace")
    model_id = await create_model(client, token, workspace_id, "Cells Page Model")
    module_id = await create_module(client, token, model_id, "Cells Page Module")

    dimension_resp = await client.post(
        f"/models/{model_id}/dimensions",
        json={"name": "Product", "dimension_type": "custom"},
        headers=auth_headers(token),
    )
    assert dimension_resp.status_code == 201
    dimension_id = dimension_resp.json()["id"]

    member_ids: List[str] = []
    for idx in range(5):
        item_resp = await client.post(
            f"/dimensions/{dimension_id}/items",
            json={"name": f"P{idx}", "code": f"P{idx}"},
            headers=auth_headers(token),
        )
        assert item_resp.status_code == 201
        member_ids.append(item_resp.json()["id"])

    line_item_id = await create_line_item(
        client,
        token,
        module_id,
        "Revenue",
        applies_to_dimensions=[dimension_id],
    )

    seed_resp = await client.post(
        "/cells/bulk",
        json={
            "cells": [
                {
                    "line_item_id": line_item_id,
                    "dimension_members": [member_id],
                    "value": float(index),
                }
                for index, member_id in enumerate(member_ids)
            ]
        },
        headers=auth_headers(token),
    )
    assert seed_resp.status_code == 200

    page_one_resp = await client.get(
        f"/modules/{module_id}/cells/page?offset=0&limit=2",
        headers=auth_headers(token),
    )
    assert page_one_resp.status_code == 200
    page_one = page_one_resp.json()
    assert page_one["total_count"] == 5
    assert page_one["offset"] == 0
    assert page_one["limit"] == 2
    assert page_one["has_more"] is True
    assert len(page_one["cells"]) == 2

    page_two_resp = await client.get(
        f"/modules/{module_id}/cells/page?offset=2&limit=2",
        headers=auth_headers(token),
    )
    assert page_two_resp.status_code == 200
    page_two = page_two_resp.json()
    assert page_two["total_count"] == 5
    assert page_two["offset"] == 2
    assert page_two["limit"] == 2
    assert page_two["has_more"] is True
    assert len(page_two["cells"]) == 2

    page_three_resp = await client.get(
        f"/modules/{module_id}/cells/page?offset=4&limit=2",
        headers=auth_headers(token),
    )
    assert page_three_resp.status_code == 200
    page_three = page_three_resp.json()
    assert page_three["total_count"] == 5
    assert page_three["offset"] == 4
    assert page_three["limit"] == 2
    assert page_three["has_more"] is False
    assert len(page_three["cells"]) == 1
