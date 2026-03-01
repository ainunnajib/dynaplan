import uuid

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


async def create_workspace(client: AsyncClient, token: str, name: str = "Test Workspace") -> str:
    resp = await client.post(
        "/workspaces/",
        json={"name": name},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_model(client: AsyncClient, token: str, workspace_id: str, name: str = "Test Model") -> str:
    resp = await client.post(
        "/models",
        json={"name": name, "workspace_id": workspace_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_dashboard(
    client: AsyncClient,
    token: str,
    model_id: str,
    name: str = "My Dashboard",
    description: str = None,
) -> dict:
    payload = {"name": name}
    if description:
        payload["description"] = description
    resp = await client.post(
        f"/models/{model_id}/dashboards",
        json=payload,
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def add_widget(
    client: AsyncClient,
    token: str,
    dashboard_id: str,
    widget_type: str = "kpi_card",
    title: str = "Revenue",
    position_x: int = 0,
    position_y: int = 0,
    width: int = 3,
    height: int = 2,
) -> dict:
    resp = await client.post(
        f"/dashboards/{dashboard_id}/widgets",
        json={
            "widget_type": widget_type,
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


# ---------------------------------------------------------------------------
# Test: Create dashboard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_dashboard(client: AsyncClient):
    token = await register_and_login(client, "dash_create@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await client.post(
        f"/models/{model_id}/dashboards",
        json={"name": "Sales Dashboard", "description": "Q1 view"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Sales Dashboard"
    assert data["description"] == "Q1 view"
    assert data["model_id"] == model_id
    assert data["is_published"] is False
    assert "id" in data
    assert "owner_id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_dashboard_no_description(client: AsyncClient):
    token = await register_and_login(client, "dash_nodesc@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await client.post(
        f"/models/{model_id}/dashboards",
        json={"name": "Minimal Dashboard"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Minimal Dashboard"
    assert data["description"] is None


@pytest.mark.asyncio
async def test_create_dashboard_requires_auth(client: AsyncClient):
    fake_model_id = str(uuid.uuid4())
    resp = await client.post(
        f"/models/{fake_model_id}/dashboards",
        json={"name": "Unauthorized"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Test: List dashboards
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_dashboards_empty(client: AsyncClient):
    token = await register_and_login(client, "dash_list_empty@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await client.get(
        f"/models/{model_id}/dashboards",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_dashboards_returns_multiple(client: AsyncClient):
    token = await register_and_login(client, "dash_list_multi@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    await create_dashboard(client, token, model_id, "Dashboard A")
    await create_dashboard(client, token, model_id, "Dashboard B")

    resp = await client.get(
        f"/models/{model_id}/dashboards",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    names = [d["name"] for d in resp.json()]
    assert "Dashboard A" in names
    assert "Dashboard B" in names


@pytest.mark.asyncio
async def test_list_dashboards_requires_auth(client: AsyncClient):
    fake_model_id = str(uuid.uuid4())
    resp = await client.get(f"/models/{fake_model_id}/dashboards")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Test: Get dashboard with widgets
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_dashboard(client: AsyncClient):
    token = await register_and_login(client, "dash_get@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dashboard = await create_dashboard(client, token, model_id, "My Board")
    dashboard_id = dashboard["id"]

    resp = await client.get(
        f"/dashboards/{dashboard_id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "My Board"
    assert "widgets" in data
    assert data["widgets"] == []


@pytest.mark.asyncio
async def test_get_dashboard_not_found(client: AsyncClient):
    token = await register_and_login(client, "dash_notfound@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.get(f"/dashboards/{fake_id}", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_dashboard_forbidden(client: AsyncClient):
    token_a = await register_and_login(client, "dash_forbid_a@example.com")
    token_b = await register_and_login(client, "dash_forbid_b@example.com")

    ws_id = await create_workspace(client, token_a)
    model_id = await create_model(client, token_a, ws_id)
    dashboard = await create_dashboard(client, token_a, model_id)
    dashboard_id = dashboard["id"]

    resp = await client.get(f"/dashboards/{dashboard_id}", headers=auth_headers(token_b))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test: Update dashboard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_dashboard_name(client: AsyncClient):
    token = await register_and_login(client, "dash_update@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dashboard = await create_dashboard(client, token, model_id, "Old Name")
    dashboard_id = dashboard["id"]

    resp = await client.patch(
        f"/dashboards/{dashboard_id}",
        json={"name": "New Name"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_update_dashboard_publish(client: AsyncClient):
    token = await register_and_login(client, "dash_publish@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dashboard = await create_dashboard(client, token, model_id)
    dashboard_id = dashboard["id"]

    resp = await client.patch(
        f"/dashboards/{dashboard_id}",
        json={"is_published": True},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["is_published"] is True


@pytest.mark.asyncio
async def test_update_dashboard_forbidden(client: AsyncClient):
    token_a = await register_and_login(client, "dash_upd_a@example.com")
    token_b = await register_and_login(client, "dash_upd_b@example.com")

    ws_id = await create_workspace(client, token_a)
    model_id = await create_model(client, token_a, ws_id)
    dashboard = await create_dashboard(client, token_a, model_id)
    dashboard_id = dashboard["id"]

    resp = await client.patch(
        f"/dashboards/{dashboard_id}",
        json={"name": "Hijacked"},
        headers=auth_headers(token_b),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test: Delete dashboard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_dashboard(client: AsyncClient):
    token = await register_and_login(client, "dash_delete@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dashboard = await create_dashboard(client, token, model_id)
    dashboard_id = dashboard["id"]

    del_resp = await client.delete(
        f"/dashboards/{dashboard_id}",
        headers=auth_headers(token),
    )
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/dashboards/{dashboard_id}", headers=auth_headers(token))
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_dashboard_forbidden(client: AsyncClient):
    token_a = await register_and_login(client, "dash_del_a@example.com")
    token_b = await register_and_login(client, "dash_del_b@example.com")

    ws_id = await create_workspace(client, token_a)
    model_id = await create_model(client, token_a, ws_id)
    dashboard = await create_dashboard(client, token_a, model_id)
    dashboard_id = dashboard["id"]

    resp = await client.delete(f"/dashboards/{dashboard_id}", headers=auth_headers(token_b))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test: Add widget
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_widget(client: AsyncClient):
    token = await register_and_login(client, "widget_add@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dashboard = await create_dashboard(client, token, model_id)
    dashboard_id = dashboard["id"]

    resp = await client.post(
        f"/dashboards/{dashboard_id}/widgets",
        json={
            "widget_type": "kpi_card",
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
    assert data["widget_type"] == "kpi_card"
    assert data["title"] == "Total Revenue"
    assert data["position_x"] == 0
    assert data["position_y"] == 0
    assert data["width"] == 3
    assert data["height"] == 2
    assert data["config"]["module_id"] == "abc"
    assert "id" in data
    assert "dashboard_id" in data


@pytest.mark.asyncio
async def test_add_chart_widget(client: AsyncClient):
    token = await register_and_login(client, "widget_chart@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dashboard = await create_dashboard(client, token, model_id)
    dashboard_id = dashboard["id"]

    resp = await client.post(
        f"/dashboards/{dashboard_id}/widgets",
        json={
            "widget_type": "chart",
            "title": "Revenue Trend",
            "position_x": 0,
            "position_y": 2,
            "width": 6,
            "height": 4,
            "config": {"chart_type": "line"},
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["widget_type"] == "chart"
    assert data["config"]["chart_type"] == "line"


@pytest.mark.asyncio
async def test_add_widget_appears_in_dashboard(client: AsyncClient):
    token = await register_and_login(client, "widget_appears@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dashboard = await create_dashboard(client, token, model_id)
    dashboard_id = dashboard["id"]

    await add_widget(client, token, dashboard_id, title="KPI 1")
    await add_widget(client, token, dashboard_id, title="KPI 2", position_x=3)

    resp = await client.get(f"/dashboards/{dashboard_id}", headers=auth_headers(token))
    assert resp.status_code == 200
    widgets = resp.json()["widgets"]
    assert len(widgets) == 2
    titles = [w["title"] for w in widgets]
    assert "KPI 1" in titles
    assert "KPI 2" in titles


@pytest.mark.asyncio
async def test_add_widget_requires_auth(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    resp = await client.post(
        f"/dashboards/{fake_id}/widgets",
        json={"widget_type": "text", "position_x": 0, "position_y": 0},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Test: Update widget
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_widget_position(client: AsyncClient):
    token = await register_and_login(client, "widget_update@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dashboard = await create_dashboard(client, token, model_id)
    dashboard_id = dashboard["id"]
    widget = await add_widget(client, token, dashboard_id)
    widget_id = widget["id"]

    resp = await client.patch(
        f"/widgets/{widget_id}",
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
async def test_update_widget_config(client: AsyncClient):
    token = await register_and_login(client, "widget_config@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dashboard = await create_dashboard(client, token, model_id)
    dashboard_id = dashboard["id"]
    widget = await add_widget(client, token, dashboard_id, widget_type="chart")
    widget_id = widget["id"]

    resp = await client.patch(
        f"/widgets/{widget_id}",
        json={"config": {"chart_type": "bar", "show_legend": True}},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["config"]["chart_type"] == "bar"
    assert data["config"]["show_legend"] is True


@pytest.mark.asyncio
async def test_update_widget_forbidden(client: AsyncClient):
    token_a = await register_and_login(client, "widget_upd_a@example.com")
    token_b = await register_and_login(client, "widget_upd_b@example.com")

    ws_id = await create_workspace(client, token_a)
    model_id = await create_model(client, token_a, ws_id)
    dashboard = await create_dashboard(client, token_a, model_id)
    dashboard_id = dashboard["id"]
    widget = await add_widget(client, token_a, dashboard_id)
    widget_id = widget["id"]

    resp = await client.patch(
        f"/widgets/{widget_id}",
        json={"position_x": 10},
        headers=auth_headers(token_b),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_widget_not_found(client: AsyncClient):
    token = await register_and_login(client, "widget_notfound@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.patch(
        f"/widgets/{fake_id}",
        json={"position_x": 0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test: Delete widget
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_widget(client: AsyncClient):
    token = await register_and_login(client, "widget_delete@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dashboard = await create_dashboard(client, token, model_id)
    dashboard_id = dashboard["id"]
    widget = await add_widget(client, token, dashboard_id)
    widget_id = widget["id"]

    del_resp = await client.delete(
        f"/widgets/{widget_id}",
        headers=auth_headers(token),
    )
    assert del_resp.status_code == 204

    # Widget should no longer appear in the dashboard
    get_resp = await client.get(f"/dashboards/{dashboard_id}", headers=auth_headers(token))
    assert get_resp.status_code == 200
    assert get_resp.json()["widgets"] == []


@pytest.mark.asyncio
async def test_delete_widget_forbidden(client: AsyncClient):
    token_a = await register_and_login(client, "widget_del_a@example.com")
    token_b = await register_and_login(client, "widget_del_b@example.com")

    ws_id = await create_workspace(client, token_a)
    model_id = await create_model(client, token_a, ws_id)
    dashboard = await create_dashboard(client, token_a, model_id)
    dashboard_id = dashboard["id"]
    widget = await add_widget(client, token_a, dashboard_id)
    widget_id = widget["id"]

    resp = await client.delete(f"/widgets/{widget_id}", headers=auth_headers(token_b))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test: All widget types
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_all_widget_types(client: AsyncClient):
    token = await register_and_login(client, "all_widget_types@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dashboard = await create_dashboard(client, token, model_id)
    dashboard_id = dashboard["id"]

    widget_types = ["grid", "chart", "kpi_card", "text", "image"]
    for i, wt in enumerate(widget_types):
        resp = await client.post(
            f"/dashboards/{dashboard_id}/widgets",
            json={
                "widget_type": wt,
                "title": f"{wt} widget",
                "position_x": i * 2,
                "position_y": 0,
                "width": 2,
                "height": 2,
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 201, f"Failed for widget type: {wt}"
        assert resp.json()["widget_type"] == wt


@pytest.mark.asyncio
async def test_dashboard_layout_field(client: AsyncClient):
    token = await register_and_login(client, "dash_layout@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)

    resp = await client.post(
        f"/models/{model_id}/dashboards",
        json={
            "name": "Layout Dashboard",
            "layout": {"cols": 12, "row_height": 100},
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["layout"]["cols"] == 12
    assert data["layout"]["row_height"] == 100


@pytest.mark.asyncio
async def test_delete_dashboard_cascades_widgets(client: AsyncClient):
    """Deleting a dashboard should cascade-delete all its widgets."""
    token = await register_and_login(client, "dash_cascade@example.com")
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    dashboard = await create_dashboard(client, token, model_id)
    dashboard_id = dashboard["id"]

    widget = await add_widget(client, token, dashboard_id)
    widget_id = widget["id"]

    # Delete the dashboard
    await client.delete(f"/dashboards/{dashboard_id}", headers=auth_headers(token))

    # The widget endpoint should 404 now
    resp = await client.patch(
        f"/widgets/{widget_id}",
        json={"position_x": 0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404
