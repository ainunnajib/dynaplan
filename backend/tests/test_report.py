import uuid

import pytest
from httpx import AsyncClient

# Register report models with Base.metadata so tables are created by conftest
import app.models.report  # noqa: F401


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


async def create_report(
    client: AsyncClient,
    token: str,
    model_id: str,
    name: str = "My Report",
    description: str = None,
) -> dict:
    payload = {"name": name}
    if description:
        payload["description"] = description
    resp = await client.post(
        f"/models/{model_id}/reports",
        json=payload,
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def add_section(
    client: AsyncClient,
    token: str,
    report_id: str,
    section_type: str = "narrative",
    title: str = "Section Title",
    sort_order: int = 0,
) -> dict:
    resp = await client.post(
        f"/reports/{report_id}/sections",
        json={
            "section_type": section_type,
            "title": title,
            "sort_order": sort_order,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def setup_env(client: AsyncClient, email: str):
    """Register user, create workspace & model, return (token, model_id)."""
    token = await register_and_login(client, email)
    ws_id = await create_workspace(client, token)
    model_id = await create_model(client, token, ws_id)
    return token, model_id


# ---------------------------------------------------------------------------
# Test: Create report
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_report(client: AsyncClient):
    token, model_id = await setup_env(client, "rpt_create@example.com")

    resp = await client.post(
        f"/models/{model_id}/reports",
        json={"name": "Q1 Report", "description": "Quarterly summary"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Q1 Report"
    assert data["description"] == "Quarterly summary"
    assert data["model_id"] == model_id
    assert data["is_published"] is False
    assert data["page_size"] == "a4"
    assert data["orientation"] == "portrait"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_report_custom_page_settings(client: AsyncClient):
    token, model_id = await setup_env(client, "rpt_custom@example.com")

    resp = await client.post(
        f"/models/{model_id}/reports",
        json={
            "name": "Wide Report",
            "page_size": "letter",
            "orientation": "landscape",
            "margin_top": 10.0,
            "margin_right": 10.0,
            "margin_bottom": 10.0,
            "margin_left": 10.0,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["page_size"] == "letter"
    assert data["orientation"] == "landscape"
    assert data["margin_top"] == 10.0


@pytest.mark.asyncio
async def test_create_report_no_description(client: AsyncClient):
    token, model_id = await setup_env(client, "rpt_nodesc@example.com")

    resp = await client.post(
        f"/models/{model_id}/reports",
        json={"name": "Minimal Report"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    assert resp.json()["description"] is None


@pytest.mark.asyncio
async def test_create_report_requires_auth(client: AsyncClient):
    fake_model_id = str(uuid.uuid4())
    resp = await client.post(
        f"/models/{fake_model_id}/reports",
        json={"name": "Unauthorized"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Test: List reports
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_reports_empty(client: AsyncClient):
    token, model_id = await setup_env(client, "rpt_list_empty@example.com")

    resp = await client.get(
        f"/models/{model_id}/reports",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_reports_returns_multiple(client: AsyncClient):
    token, model_id = await setup_env(client, "rpt_list_multi@example.com")

    await create_report(client, token, model_id, "Report A")
    await create_report(client, token, model_id, "Report B")

    resp = await client.get(
        f"/models/{model_id}/reports",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    names = [r["name"] for r in resp.json()]
    assert "Report A" in names
    assert "Report B" in names


@pytest.mark.asyncio
async def test_list_reports_requires_auth(client: AsyncClient):
    fake_model_id = str(uuid.uuid4())
    resp = await client.get(f"/models/{fake_model_id}/reports")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Test: Get report with sections
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_report(client: AsyncClient):
    token, model_id = await setup_env(client, "rpt_get@example.com")
    report = await create_report(client, token, model_id, "My Board")
    report_id = report["id"]

    resp = await client.get(
        f"/reports/{report_id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "My Board"
    assert "sections" in data
    assert data["sections"] == []


@pytest.mark.asyncio
async def test_get_report_not_found(client: AsyncClient):
    token = await register_and_login(client, "rpt_notfound@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.get(f"/reports/{fake_id}", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_report_forbidden(client: AsyncClient):
    token_a = await register_and_login(client, "rpt_forbid_a@example.com")
    token_b = await register_and_login(client, "rpt_forbid_b@example.com")

    ws_id = await create_workspace(client, token_a)
    model_id = await create_model(client, token_a, ws_id)
    report = await create_report(client, token_a, model_id)
    report_id = report["id"]

    resp = await client.get(f"/reports/{report_id}", headers=auth_headers(token_b))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test: Update report
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_report_name(client: AsyncClient):
    token, model_id = await setup_env(client, "rpt_update@example.com")
    report = await create_report(client, token, model_id, "Old Name")
    report_id = report["id"]

    resp = await client.put(
        f"/reports/{report_id}",
        json={"name": "New Name"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_update_report_margins(client: AsyncClient):
    token, model_id = await setup_env(client, "rpt_margins@example.com")
    report = await create_report(client, token, model_id)
    report_id = report["id"]

    resp = await client.put(
        f"/reports/{report_id}",
        json={"margin_top": 30.0, "margin_bottom": 30.0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["margin_top"] == 30.0
    assert data["margin_bottom"] == 30.0


@pytest.mark.asyncio
async def test_update_report_forbidden(client: AsyncClient):
    token_a = await register_and_login(client, "rpt_upd_a@example.com")
    token_b = await register_and_login(client, "rpt_upd_b@example.com")

    ws_id = await create_workspace(client, token_a)
    model_id = await create_model(client, token_a, ws_id)
    report = await create_report(client, token_a, model_id)
    report_id = report["id"]

    resp = await client.put(
        f"/reports/{report_id}",
        json={"name": "Hijacked"},
        headers=auth_headers(token_b),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test: Delete report
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_report(client: AsyncClient):
    token, model_id = await setup_env(client, "rpt_delete@example.com")
    report = await create_report(client, token, model_id)
    report_id = report["id"]

    del_resp = await client.delete(
        f"/reports/{report_id}",
        headers=auth_headers(token),
    )
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/reports/{report_id}", headers=auth_headers(token))
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_report_forbidden(client: AsyncClient):
    token_a = await register_and_login(client, "rpt_del_a@example.com")
    token_b = await register_and_login(client, "rpt_del_b@example.com")

    ws_id = await create_workspace(client, token_a)
    model_id = await create_model(client, token_a, ws_id)
    report = await create_report(client, token_a, model_id)
    report_id = report["id"]

    resp = await client.delete(f"/reports/{report_id}", headers=auth_headers(token_b))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_report_cascades_sections(client: AsyncClient):
    token, model_id = await setup_env(client, "rpt_cascade@example.com")
    report = await create_report(client, token, model_id)
    report_id = report["id"]

    section = await add_section(client, token, report_id)
    section_id = section["id"]

    await client.delete(f"/reports/{report_id}", headers=auth_headers(token))

    resp = await client.put(
        f"/sections/{section_id}",
        json={"title": "Should fail"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test: Add section
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_section(client: AsyncClient):
    token, model_id = await setup_env(client, "sec_add@example.com")
    report = await create_report(client, token, model_id)
    report_id = report["id"]

    resp = await client.post(
        f"/reports/{report_id}/sections",
        json={
            "section_type": "narrative",
            "title": "Executive Summary",
            "content_config": {"html": "<p>Hello</p>"},
            "sort_order": 0,
            "height_mm": 50.0,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["section_type"] == "narrative"
    assert data["title"] == "Executive Summary"
    assert data["content_config"]["html"] == "<p>Hello</p>"
    assert data["height_mm"] == 50.0
    assert "id" in data
    assert "report_id" in data


@pytest.mark.asyncio
async def test_add_section_all_types(client: AsyncClient):
    token, model_id = await setup_env(client, "sec_types@example.com")
    report = await create_report(client, token, model_id)
    report_id = report["id"]

    section_types = ["narrative", "grid", "chart", "kpi_row", "page_break", "spacer"]
    for i, st in enumerate(section_types):
        resp = await client.post(
            f"/reports/{report_id}/sections",
            json={"section_type": st, "title": f"{st} section", "sort_order": i},
            headers=auth_headers(token),
        )
        assert resp.status_code == 201, f"Failed for section type: {st}"
        assert resp.json()["section_type"] == st


@pytest.mark.asyncio
async def test_add_section_appears_in_report(client: AsyncClient):
    token, model_id = await setup_env(client, "sec_appears@example.com")
    report = await create_report(client, token, model_id)
    report_id = report["id"]

    await add_section(client, token, report_id, title="Section A", sort_order=0)
    await add_section(client, token, report_id, section_type="chart", title="Section B", sort_order=1)

    resp = await client.get(f"/reports/{report_id}", headers=auth_headers(token))
    assert resp.status_code == 200
    sections = resp.json()["sections"]
    assert len(sections) == 2
    titles = [s["title"] for s in sections]
    assert "Section A" in titles
    assert "Section B" in titles


@pytest.mark.asyncio
async def test_add_section_requires_auth(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    resp = await client.post(
        f"/reports/{fake_id}/sections",
        json={"section_type": "narrative"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Test: Update section
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_section(client: AsyncClient):
    token, model_id = await setup_env(client, "sec_update@example.com")
    report = await create_report(client, token, model_id)
    report_id = report["id"]
    section = await add_section(client, token, report_id)
    section_id = section["id"]

    resp = await client.put(
        f"/sections/{section_id}",
        json={"title": "Updated Title", "height_mm": 100.0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Updated Title"
    assert data["height_mm"] == 100.0


@pytest.mark.asyncio
async def test_update_section_not_found(client: AsyncClient):
    token = await register_and_login(client, "sec_notfound@example.com")
    fake_id = str(uuid.uuid4())

    resp = await client.put(
        f"/sections/{fake_id}",
        json={"title": "X"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_section_forbidden(client: AsyncClient):
    token_a = await register_and_login(client, "sec_upd_a@example.com")
    token_b = await register_and_login(client, "sec_upd_b@example.com")

    ws_id = await create_workspace(client, token_a)
    model_id = await create_model(client, token_a, ws_id)
    report = await create_report(client, token_a, model_id)
    section = await add_section(client, token_a, report["id"])
    section_id = section["id"]

    resp = await client.put(
        f"/sections/{section_id}",
        json={"title": "Hijacked"},
        headers=auth_headers(token_b),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test: Delete section
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_section(client: AsyncClient):
    token, model_id = await setup_env(client, "sec_delete@example.com")
    report = await create_report(client, token, model_id)
    report_id = report["id"]
    section = await add_section(client, token, report_id)
    section_id = section["id"]

    del_resp = await client.delete(
        f"/sections/{section_id}",
        headers=auth_headers(token),
    )
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/reports/{report_id}", headers=auth_headers(token))
    assert get_resp.status_code == 200
    assert get_resp.json()["sections"] == []


# ---------------------------------------------------------------------------
# Test: Reorder sections
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reorder_sections(client: AsyncClient):
    token, model_id = await setup_env(client, "sec_reorder@example.com")
    report = await create_report(client, token, model_id)
    report_id = report["id"]

    s1 = await add_section(client, token, report_id, title="First", sort_order=0)
    s2 = await add_section(client, token, report_id, title="Second", sort_order=1)
    s3 = await add_section(client, token, report_id, title="Third", sort_order=2)

    # Reverse order
    resp = await client.post(
        f"/reports/{report_id}/sections/reorder",
        json={"section_ids": [s3["id"], s2["id"], s1["id"]]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["id"] == s3["id"]
    assert data[0]["sort_order"] == 0
    assert data[1]["id"] == s2["id"]
    assert data[1]["sort_order"] == 1
    assert data[2]["id"] == s1["id"]
    assert data[2]["sort_order"] == 2


# ---------------------------------------------------------------------------
# Test: Export lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initiate_export(client: AsyncClient):
    token, model_id = await setup_env(client, "exp_init@example.com")
    report = await create_report(client, token, model_id)
    report_id = report["id"]

    resp = await client.post(
        f"/reports/{report_id}/export",
        json={"format": "pdf"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["format"] == "pdf"
    assert data["status"] == "pending"
    assert data["report_id"] == report_id
    assert data["file_path"] is None


@pytest.mark.asyncio
async def test_initiate_export_xlsx(client: AsyncClient):
    token, model_id = await setup_env(client, "exp_xlsx@example.com")
    report = await create_report(client, token, model_id)
    report_id = report["id"]

    resp = await client.post(
        f"/reports/{report_id}/export",
        json={"format": "xlsx"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    assert resp.json()["format"] == "xlsx"


@pytest.mark.asyncio
async def test_list_exports(client: AsyncClient):
    token, model_id = await setup_env(client, "exp_list@example.com")
    report = await create_report(client, token, model_id)
    report_id = report["id"]

    await client.post(
        f"/reports/{report_id}/export",
        json={"format": "pdf"},
        headers=auth_headers(token),
    )
    await client.post(
        f"/reports/{report_id}/export",
        json={"format": "pptx"},
        headers=auth_headers(token),
    )

    resp = await client.get(
        f"/reports/{report_id}/exports",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    exports = resp.json()
    assert len(exports) == 2
    formats = {e["format"] for e in exports}
    assert "pdf" in formats
    assert "pptx" in formats


@pytest.mark.asyncio
async def test_export_requires_auth(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    resp = await client.post(
        f"/reports/{fake_id}/export",
        json={"format": "pdf"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Test: Publish / unpublish
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_publish_report(client: AsyncClient):
    token, model_id = await setup_env(client, "rpt_publish@example.com")
    report = await create_report(client, token, model_id)
    report_id = report["id"]

    resp = await client.put(
        f"/reports/{report_id}/publish",
        json={"is_published": True},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["is_published"] is True


@pytest.mark.asyncio
async def test_unpublish_report(client: AsyncClient):
    token, model_id = await setup_env(client, "rpt_unpub@example.com")
    report = await create_report(client, token, model_id)
    report_id = report["id"]

    # Publish first
    await client.put(
        f"/reports/{report_id}/publish",
        json={"is_published": True},
        headers=auth_headers(token),
    )

    # Unpublish
    resp = await client.put(
        f"/reports/{report_id}/publish",
        json={"is_published": False},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["is_published"] is False


@pytest.mark.asyncio
async def test_publish_forbidden(client: AsyncClient):
    token_a = await register_and_login(client, "rpt_pub_a@example.com")
    token_b = await register_and_login(client, "rpt_pub_b@example.com")

    ws_id = await create_workspace(client, token_a)
    model_id = await create_model(client, token_a, ws_id)
    report = await create_report(client, token_a, model_id)
    report_id = report["id"]

    resp = await client.put(
        f"/reports/{report_id}/publish",
        json={"is_published": True},
        headers=auth_headers(token_b),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test: Header/footer HTML
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_report_header_footer(client: AsyncClient):
    token, model_id = await setup_env(client, "rpt_hf@example.com")

    resp = await client.post(
        f"/models/{model_id}/reports",
        json={
            "name": "With Header",
            "header_html": "<h1>Company Report</h1>",
            "footer_html": "<p>Page {page}</p>",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["header_html"] == "<h1>Company Report</h1>"
    assert data["footer_html"] == "<p>Page {page}</p>"
