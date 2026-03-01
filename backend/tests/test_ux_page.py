"""
Tests for F036: UX page types (Board, Worksheet, Report).

Covers page CRUD, card CRUD, context selectors, publish/unpublish,
reorder, auth guards, and 404 handling.
"""
import uuid

import pytest
from httpx import AsyncClient

# Import the models so they are registered with Base.metadata (needed for
# table creation in conftest setup_database).  We cannot modify
# models/__init__.py, so we do it here.
import app.models.ux_page  # noqa: F401



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def register_and_login(
    client: AsyncClient, email: str, password: str = "testpass123"
) -> str:
    await client.post(
        "/auth/register",
        json={"email": email, "full_name": "Test User", "password": password},
    )
    resp = await client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def create_workspace(
    client: AsyncClient, token: str, name: str = "Test Workspace"
) -> str:
    resp = await client.post(
        "/workspaces/",
        json={"name": name},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_model(
    client: AsyncClient, token: str, workspace_id: str, name: str = "Test Model"
) -> str:
    resp = await client.post(
        "/models",
        json={"name": name, "workspace_id": workspace_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_dimension(
    client: AsyncClient, token: str, model_id: str, name: str = "Region"
) -> str:
    resp = await client.post(
        f"/models/{model_id}/dimensions",
        json={"name": name, "dimension_type": "custom"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_page(
    client: AsyncClient,
    token: str,
    model_id: str,
    name: str = "My Page",
    page_type: str = "board",
) -> dict:
    resp = await client.post(
        f"/models/{model_id}/pages",
        json={"name": name, "page_type": page_type},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def add_card(
    client: AsyncClient,
    token: str,
    page_id: str,
    card_type: str = "kpi",
    title: str = "Revenue",
    position_x: int = 0,
    position_y: int = 0,
    width: int = 3,
    height: int = 2,
) -> dict:
    resp = await client.post(
        f"/pages/{page_id}/cards",
        json={
            "card_type": card_type,
            "title": title,
            "position_x": position_x,
            "position_y": position_y,
            "width": width,
            "height": height,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def _setup(client: AsyncClient, email: str):
    """Register user, create workspace + model, return (token, model_id)."""
    token = await register_and_login(client, email)
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    return token, model_id


# ---------------------------------------------------------------------------
# Page CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_page_board(client: AsyncClient):
    token, model_id = await _setup(client, "ux_create_board@example.com")

    resp = await client.post(
        f"/models/{model_id}/pages",
        json={"name": "Sales Board", "page_type": "board", "description": "Q1 overview"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Sales Board"
    assert data["page_type"] == "board"
    assert data["description"] == "Q1 overview"
    assert data["is_published"] is False
    assert data["model_id"] == model_id
    assert "id" in data


@pytest.mark.asyncio
async def test_create_page_worksheet(client: AsyncClient):
    token, model_id = await _setup(client, "ux_create_ws@example.com")

    resp = await client.post(
        f"/models/{model_id}/pages",
        json={"name": "Data Entry", "page_type": "worksheet"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    assert resp.json()["page_type"] == "worksheet"


@pytest.mark.asyncio
async def test_create_page_report(client: AsyncClient):
    token, model_id = await _setup(client, "ux_create_rpt@example.com")

    resp = await client.post(
        f"/models/{model_id}/pages",
        json={"name": "Exec Report", "page_type": "report"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    assert resp.json()["page_type"] == "report"


@pytest.mark.asyncio
async def test_create_page_requires_auth(client: AsyncClient):
    fake_model_id = str(uuid.uuid4())
    resp = await client.post(
        f"/models/{fake_model_id}/pages",
        json={"name": "No Auth", "page_type": "board"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_pages_empty(client: AsyncClient):
    token, model_id = await _setup(client, "ux_list_empty@example.com")

    resp = await client.get(
        f"/models/{model_id}/pages",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_pages_returns_multiple(client: AsyncClient):
    token, model_id = await _setup(client, "ux_list_multi@example.com")

    await create_page(client, token, model_id, "Page A", "board")
    await create_page(client, token, model_id, "Page B", "worksheet")

    resp = await client.get(
        f"/models/{model_id}/pages",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "Page A" in names
    assert "Page B" in names


@pytest.mark.asyncio
async def test_get_page_detail(client: AsyncClient):
    token, model_id = await _setup(client, "ux_get_detail@example.com")
    page = await create_page(client, token, model_id, "Detail Page")

    resp = await client.get(
        f"/pages/{page['id']}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Detail Page"
    assert "cards" in data
    assert "context_selectors" in data
    assert data["cards"] == []
    assert data["context_selectors"] == []


@pytest.mark.asyncio
async def test_get_page_not_found(client: AsyncClient):
    token = await register_and_login(client, "ux_notfound@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.get(f"/pages/{fake_id}", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_page_forbidden(client: AsyncClient):
    token_a = await register_and_login(client, "ux_forbid_a@example.com")
    token_b = await register_and_login(client, "ux_forbid_b@example.com")

    ws_id = await create_workspace(client, token_a)
    model_id = await create_model(client, token_a, ws_id)
    page = await create_page(client, token_a, model_id)

    resp = await client.get(f"/pages/{page['id']}", headers=auth_headers(token_b))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_page(client: AsyncClient):
    token, model_id = await _setup(client, "ux_update@example.com")
    page = await create_page(client, token, model_id, "Old Name")

    resp = await client.put(
        f"/pages/{page['id']}",
        json={"name": "New Name", "description": "Updated"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"
    assert resp.json()["description"] == "Updated"


@pytest.mark.asyncio
async def test_update_page_forbidden(client: AsyncClient):
    token_a = await register_and_login(client, "ux_upd_a@example.com")
    token_b = await register_and_login(client, "ux_upd_b@example.com")

    ws_id = await create_workspace(client, token_a)
    model_id = await create_model(client, token_a, ws_id)
    page = await create_page(client, token_a, model_id)

    resp = await client.put(
        f"/pages/{page['id']}",
        json={"name": "Hijacked"},
        headers=auth_headers(token_b),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_page(client: AsyncClient):
    token, model_id = await _setup(client, "ux_delete@example.com")
    page = await create_page(client, token, model_id)

    del_resp = await client.delete(
        f"/pages/{page['id']}",
        headers=auth_headers(token),
    )
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/pages/{page['id']}", headers=auth_headers(token))
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_page_forbidden(client: AsyncClient):
    token_a = await register_and_login(client, "ux_del_a@example.com")
    token_b = await register_and_login(client, "ux_del_b@example.com")

    ws_id = await create_workspace(client, token_a)
    model_id = await create_model(client, token_a, ws_id)
    page = await create_page(client, token_a, model_id)

    resp = await client.delete(f"/pages/{page['id']}", headers=auth_headers(token_b))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Publish / unpublish
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_publish_page(client: AsyncClient):
    token, model_id = await _setup(client, "ux_publish@example.com")
    page = await create_page(client, token, model_id)

    resp = await client.put(
        f"/pages/{page['id']}/publish",
        json={"is_published": True},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["is_published"] is True


@pytest.mark.asyncio
async def test_unpublish_page(client: AsyncClient):
    token, model_id = await _setup(client, "ux_unpublish@example.com")
    page = await create_page(client, token, model_id)

    # publish first
    await client.put(
        f"/pages/{page['id']}/publish",
        json={"is_published": True},
        headers=auth_headers(token),
    )
    # then unpublish
    resp = await client.put(
        f"/pages/{page['id']}/publish",
        json={"is_published": False},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["is_published"] is False


# ---------------------------------------------------------------------------
# Card CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_card(client: AsyncClient):
    token, model_id = await _setup(client, "ux_add_card@example.com")
    page = await create_page(client, token, model_id)

    resp = await client.post(
        f"/pages/{page['id']}/cards",
        json={
            "card_type": "kpi",
            "title": "Total Revenue",
            "position_x": 0,
            "position_y": 0,
            "width": 3,
            "height": 2,
            "config": {"module_id": "abc", "line_item_id": "def"},
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["card_type"] == "kpi"
    assert data["title"] == "Total Revenue"
    assert data["config"]["module_id"] == "abc"
    assert "id" in data
    assert "page_id" in data


@pytest.mark.asyncio
async def test_add_card_all_types(client: AsyncClient):
    token, model_id = await _setup(client, "ux_card_types@example.com")
    page = await create_page(client, token, model_id)

    card_types = ["grid", "chart", "kpi", "text", "image", "filter"]
    for i, ct in enumerate(card_types):
        resp = await client.post(
            f"/pages/{page['id']}/cards",
            json={
                "card_type": ct,
                "title": f"{ct} card",
                "position_x": i * 2,
                "position_y": 0,
                "width": 2,
                "height": 2,
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 201, f"Failed for card type: {ct}"
        assert resp.json()["card_type"] == ct


@pytest.mark.asyncio
async def test_card_appears_in_page(client: AsyncClient):
    token, model_id = await _setup(client, "ux_card_appears@example.com")
    page = await create_page(client, token, model_id)

    await add_card(client, token, page["id"], title="KPI 1")
    await add_card(client, token, page["id"], title="KPI 2", position_x=3)

    resp = await client.get(f"/pages/{page['id']}", headers=auth_headers(token))
    assert resp.status_code == 200
    cards = resp.json()["cards"]
    assert len(cards) == 2
    titles = [c["title"] for c in cards]
    assert "KPI 1" in titles
    assert "KPI 2" in titles


@pytest.mark.asyncio
async def test_update_card(client: AsyncClient):
    token, model_id = await _setup(client, "ux_upd_card@example.com")
    page = await create_page(client, token, model_id)
    card = await add_card(client, token, page["id"])

    resp = await client.put(
        f"/cards/{card['id']}",
        json={"position_x": 6, "position_y": 4, "width": 6, "height": 3},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["position_x"] == 6
    assert data["position_y"] == 4
    assert data["width"] == 6
    assert data["height"] == 3


@pytest.mark.asyncio
async def test_update_card_config(client: AsyncClient):
    token, model_id = await _setup(client, "ux_upd_card_cfg@example.com")
    page = await create_page(client, token, model_id)
    card = await add_card(client, token, page["id"], card_type="chart")

    resp = await client.put(
        f"/cards/{card['id']}",
        json={"config": {"chart_type": "bar", "show_legend": True}},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["config"]["chart_type"] == "bar"
    assert resp.json()["config"]["show_legend"] is True


@pytest.mark.asyncio
async def test_update_card_not_found(client: AsyncClient):
    token = await register_and_login(client, "ux_card_nf@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.put(
        f"/cards/{fake_id}",
        json={"position_x": 0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_card_forbidden(client: AsyncClient):
    token_a = await register_and_login(client, "ux_card_fa@example.com")
    token_b = await register_and_login(client, "ux_card_fb@example.com")

    ws_id = await create_workspace(client, token_a)
    model_id = await create_model(client, token_a, ws_id)
    page = await create_page(client, token_a, model_id)
    card = await add_card(client, token_a, page["id"])

    resp = await client.put(
        f"/cards/{card['id']}",
        json={"position_x": 10},
        headers=auth_headers(token_b),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_card(client: AsyncClient):
    token, model_id = await _setup(client, "ux_del_card@example.com")
    page = await create_page(client, token, model_id)
    card = await add_card(client, token, page["id"])

    del_resp = await client.delete(
        f"/cards/{card['id']}",
        headers=auth_headers(token),
    )
    assert del_resp.status_code == 204

    # Card should no longer appear in page
    get_resp = await client.get(f"/pages/{page['id']}", headers=auth_headers(token))
    assert get_resp.status_code == 200
    assert get_resp.json()["cards"] == []


@pytest.mark.asyncio
async def test_delete_card_forbidden(client: AsyncClient):
    token_a = await register_and_login(client, "ux_del_card_a@example.com")
    token_b = await register_and_login(client, "ux_del_card_b@example.com")

    ws_id = await create_workspace(client, token_a)
    model_id = await create_model(client, token_a, ws_id)
    page = await create_page(client, token_a, model_id)
    card = await add_card(client, token_a, page["id"])

    resp = await client.delete(f"/cards/{card['id']}", headers=auth_headers(token_b))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_add_card_requires_auth(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    resp = await client.post(
        f"/pages/{fake_id}/cards",
        json={"card_type": "text", "position_x": 0, "position_y": 0},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Context selectors
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_context_selector(client: AsyncClient):
    token, model_id = await _setup(client, "ux_ctx_add@example.com")
    dim_id = await create_dimension(client, token, model_id, "Region")
    page = await create_page(client, token, model_id)

    resp = await client.post(
        f"/pages/{page['id']}/context-selectors",
        json={
            "dimension_id": dim_id,
            "label": "Select Region",
            "allow_multi_select": True,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["dimension_id"] == dim_id
    assert data["label"] == "Select Region"
    assert data["allow_multi_select"] is True
    assert data["page_id"] == page["id"]


@pytest.mark.asyncio
async def test_context_selector_appears_in_page(client: AsyncClient):
    token, model_id = await _setup(client, "ux_ctx_appears@example.com")
    dim_id = await create_dimension(client, token, model_id, "Product")
    page = await create_page(client, token, model_id)

    await client.post(
        f"/pages/{page['id']}/context-selectors",
        json={"dimension_id": dim_id, "label": "Product Filter"},
        headers=auth_headers(token),
    )

    resp = await client.get(f"/pages/{page['id']}", headers=auth_headers(token))
    assert resp.status_code == 200
    selectors = resp.json()["context_selectors"]
    assert len(selectors) == 1
    assert selectors[0]["label"] == "Product Filter"


@pytest.mark.asyncio
async def test_delete_context_selector(client: AsyncClient):
    token, model_id = await _setup(client, "ux_ctx_del@example.com")
    dim_id = await create_dimension(client, token, model_id, "Channel")
    page = await create_page(client, token, model_id)

    create_resp = await client.post(
        f"/pages/{page['id']}/context-selectors",
        json={"dimension_id": dim_id, "label": "Channel"},
        headers=auth_headers(token),
    )
    selector_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/context-selectors/{selector_id}",
        headers=auth_headers(token),
    )
    assert del_resp.status_code == 204

    # Selector should no longer appear in page
    get_resp = await client.get(f"/pages/{page['id']}", headers=auth_headers(token))
    assert get_resp.json()["context_selectors"] == []


@pytest.mark.asyncio
async def test_delete_context_selector_not_found(client: AsyncClient):
    token = await register_and_login(client, "ux_ctx_nf@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.delete(
        f"/context-selectors/{fake_id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Cascade delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_page_cascades_cards(client: AsyncClient):
    token, model_id = await _setup(client, "ux_cascade@example.com")
    page = await create_page(client, token, model_id)
    card = await add_card(client, token, page["id"])

    await client.delete(f"/pages/{page['id']}", headers=auth_headers(token))

    # Card endpoint should 404
    resp = await client.put(
        f"/cards/{card['id']}",
        json={"position_x": 0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Layout config
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_page_layout_config(client: AsyncClient):
    token, model_id = await _setup(client, "ux_layout@example.com")

    resp = await client.post(
        f"/models/{model_id}/pages",
        json={
            "name": "Layout Page",
            "page_type": "board",
            "layout_config": {"cols": 12, "row_height": 100},
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["layout_config"]["cols"] == 12
    assert data["layout_config"]["row_height"] == 100


# ---------------------------------------------------------------------------
# Reorder
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reorder_cards(client: AsyncClient):
    token, model_id = await _setup(client, "ux_reorder_cards@example.com")
    page = await create_page(client, token, model_id)

    card_a = await add_card(client, token, page["id"], title="A")
    card_b = await add_card(client, token, page["id"], title="B")

    resp = await client.put(
        f"/pages/{page['id']}/cards/reorder",
        json={"card_ids": [card_b["id"], card_a["id"]]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    reordered = resp.json()
    assert reordered[0]["id"] == card_b["id"]
    assert reordered[0]["sort_order"] == 0
    assert reordered[1]["id"] == card_a["id"]
    assert reordered[1]["sort_order"] == 1
