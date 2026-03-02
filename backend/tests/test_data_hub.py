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
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": "Bearer %s" % token}


async def create_workspace(client: AsyncClient, token: str) -> str:
    resp = await client.post(
        "/workspaces/",
        json={"name": "Data Hub Workspace"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_model(client: AsyncClient, token: str, workspace_id: str) -> str:
    resp = await client.post(
        "/models",
        json={"name": "Data Hub Model", "workspace_id": workspace_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_module(client: AsyncClient, token: str, model_id: str) -> str:
    resp = await client.post(
        "/models/%s/modules" % model_id,
        json={"name": "Sales Module"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_dimension(client: AsyncClient, token: str, model_id: str) -> str:
    resp = await client.post(
        "/models/%s/dimensions" % model_id,
        json={"name": "Product", "dimension_type": "custom"},
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
        "/dimensions/%s/items" % dimension_id,
        json={"name": name, "code": code},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def create_line_item(
    client: AsyncClient,
    token: str,
    module_id: str,
    name: str,
    applies_to_dimensions=None,
) -> str:
    payload = {
        "name": name,
        "format": "number",
    }
    if applies_to_dimensions is not None:
        payload["applies_to_dimensions"] = applies_to_dimensions
    resp = await client.post(
        "/modules/%s/line-items" % module_id,
        json=payload,
        headers=auth_headers(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def create_data_hub_table(
    client: AsyncClient,
    token: str,
    model_id: str,
    name: str = "staging_sales",
    schema_definition=None,
) -> dict:
    payload = {"name": name}
    if schema_definition is not None:
        payload["schema_definition"] = schema_definition
    resp = await client.post(
        "/models/%s/data-hub/tables" % model_id,
        json=payload,
        headers=auth_headers(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_data_hub_table_crud_flow(client: AsyncClient):
    token = await register_and_login(client, "datahub_crud@example.com")
    workspace_id = await create_workspace(client, token)
    model_id = await create_model(client, token, workspace_id)

    table_resp = await client.post(
        "/models/%s/data-hub/tables" % model_id,
        json={
            "name": "staging_sales",
            "description": "Initial staging table",
            "schema_definition": [
                {"name": "product_code", "data_type": "text", "nullable": False},
                {"name": "amount", "data_type": "number", "nullable": False},
            ],
        },
        headers=auth_headers(token),
    )
    assert table_resp.status_code == 201
    table = table_resp.json()
    table_id = table["id"]
    assert table["name"] == "staging_sales"
    assert table["row_count"] == 0

    list_resp = await client.get(
        "/models/%s/data-hub/tables" % model_id,
        headers=auth_headers(token),
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    get_resp = await client.get(
        "/data-hub/tables/%s" % table_id,
        headers=auth_headers(token),
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == table_id

    update_resp = await client.patch(
        "/data-hub/tables/%s" % table_id,
        json={"name": "staging_sales_v2", "description": "Renamed"},
        headers=auth_headers(token),
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "staging_sales_v2"
    assert update_resp.json()["description"] == "Renamed"

    delete_resp = await client.delete(
        "/data-hub/tables/%s" % table_id,
        headers=auth_headers(token),
    )
    assert delete_resp.status_code == 204

    get_after_delete = await client.get(
        "/data-hub/tables/%s" % table_id,
        headers=auth_headers(token),
    )
    assert get_after_delete.status_code == 404


@pytest.mark.asyncio
async def test_data_hub_rows_replace_and_append_with_schema_validation(client: AsyncClient):
    token = await register_and_login(client, "datahub_rows@example.com")
    workspace_id = await create_workspace(client, token)
    model_id = await create_model(client, token, workspace_id)
    table = await create_data_hub_table(
        client,
        token,
        model_id,
        schema_definition=[
            {"name": "region", "data_type": "text", "nullable": False},
            {"name": "amount", "data_type": "number", "nullable": False},
        ],
    )
    table_id = table["id"]

    replace_resp = await client.put(
        "/data-hub/tables/%s/rows" % table_id,
        json={
            "rows": [
                {"region": "US", "amount": 10},
                {"region": "EU", "amount": "20.5"},
            ]
        },
        headers=auth_headers(token),
    )
    assert replace_resp.status_code == 200
    assert replace_resp.json()["row_count"] == 2

    rows_resp = await client.get(
        "/data-hub/tables/%s/rows" % table_id,
        headers=auth_headers(token),
    )
    assert rows_resp.status_code == 200
    body = rows_resp.json()
    assert body["total_count"] == 2
    assert body["rows"][0]["row_data"]["amount"] == 10.0
    assert body["rows"][1]["row_data"]["amount"] == 20.5

    append_resp = await client.post(
        "/data-hub/tables/%s/rows/append" % table_id,
        json={"rows": [{"region": "APAC", "amount": 7}]},
        headers=auth_headers(token),
    )
    assert append_resp.status_code == 200
    assert append_resp.json()["row_count"] == 3

    bad_append_resp = await client.post(
        "/data-hub/tables/%s/rows/append" % table_id,
        json={"rows": [{"region": "LATAM"}]},
        headers=auth_headers(token),
    )
    assert bad_append_resp.status_code == 400
    assert "required" in bad_append_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_data_hub_import_from_local_file_connector(client: AsyncClient, tmp_path):
    token = await register_and_login(client, "datahub_import_local@example.com")
    workspace_id = await create_workspace(client, token)
    model_id = await create_model(client, token, workspace_id)
    table = await create_data_hub_table(client, token, model_id, name="staging_import")
    table_id = table["id"]

    source_path = tmp_path / "data_hub_import.csv"
    source_path.write_text(
        "sku,qty\nA,10\nB,20\n",
        encoding="utf-8",
    )

    import_resp = await client.post(
        "/data-hub/tables/%s/import" % table_id,
        json={
            "connector_type": "local_file",
            "connector_config": {"path": str(source_path), "format": "csv"},
            "replace_existing": True,
            "infer_schema": True,
        },
        headers=auth_headers(token),
    )
    assert import_resp.status_code == 200, import_resp.text
    payload = import_resp.json()
    assert payload["rows_imported"] == 2
    assert payload["table"]["row_count"] == 2
    assert {col["name"] for col in payload["table"]["schema_definition"]} == {"sku", "qty"}

    rows_resp = await client.get(
        "/data-hub/tables/%s/rows" % table_id,
        headers=auth_headers(token),
    )
    assert rows_resp.status_code == 200
    rows = rows_resp.json()["rows"]
    assert len(rows) == 2
    assert rows[0]["row_data"]["sku"] == "A"
    assert rows[0]["row_data"]["qty"] == 10


@pytest.mark.asyncio
async def test_data_hub_import_from_cloudworks_connection(client: AsyncClient, tmp_path):
    token = await register_and_login(client, "datahub_import_conn@example.com")
    workspace_id = await create_workspace(client, token)
    model_id = await create_model(client, token, workspace_id)
    table = await create_data_hub_table(client, token, model_id, name="from_connection")
    table_id = table["id"]

    source_path = tmp_path / "data_hub_conn_import.csv"
    source_path.write_text(
        "name,value\nRevenue,125\n",
        encoding="utf-8",
    )

    connection_resp = await client.post(
        "/models/%s/connections" % model_id,
        json={
            "name": "Local staging source",
            "connector_type": "local_file",
            "config": {"path": str(source_path), "format": "csv"},
        },
        headers=auth_headers(token),
    )
    assert connection_resp.status_code == 201, connection_resp.text
    connection_id = connection_resp.json()["id"]

    import_resp = await client.post(
        "/data-hub/tables/%s/import" % table_id,
        json={"connection_id": connection_id},
        headers=auth_headers(token),
    )
    assert import_resp.status_code == 200, import_resp.text
    assert import_resp.json()["rows_imported"] == 1
    assert import_resp.json()["table"]["row_count"] == 1


@pytest.mark.asyncio
async def test_data_hub_transform_operations(client: AsyncClient):
    token = await register_and_login(client, "datahub_transform@example.com")
    workspace_id = await create_workspace(client, token)
    model_id = await create_model(client, token, workspace_id)
    table = await create_data_hub_table(client, token, model_id, name="transform_source")
    table_id = table["id"]

    seed_resp = await client.put(
        "/data-hub/tables/%s/rows" % table_id,
        json={
            "rows": [
                {"status": "active", "amount": "10"},
                {"status": "inactive", "amount": "5"},
                {"status": "active", "amount": "2"},
            ],
            "infer_schema": True,
        },
        headers=auth_headers(token),
    )
    assert seed_resp.status_code == 200, seed_resp.text

    transform_resp = await client.post(
        "/data-hub/tables/%s/transform" % table_id,
        json={
            "operations": [
                {
                    "operation_type": "transform",
                    "config": {"casts": {"amount": "float"}},
                },
                {
                    "operation_type": "filter",
                    "config": {"expression": "status == 'active'"},
                },
                {
                    "operation_type": "aggregate",
                    "config": {
                        "group_by": ["status"],
                        "aggregations": {"amount": "sum"},
                    },
                },
            ],
            "replace_existing": True,
        },
        headers=auth_headers(token),
    )
    assert transform_resp.status_code == 200, transform_resp.text
    transformed = transform_resp.json()
    assert transformed["rows_before"] == 3
    assert transformed["rows_after"] == 1
    assert transformed["table"]["row_count"] == 1

    rows_resp = await client.get(
        "/data-hub/tables/%s/rows" % table_id,
        headers=auth_headers(token),
    )
    assert rows_resp.status_code == 200
    rows = rows_resp.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["row_data"]["status"] == "active"
    assert rows[0]["row_data"]["amount"] == 12.0


@pytest.mark.asyncio
async def test_data_hub_publish_writes_cells_and_tracks_lineage(client: AsyncClient):
    token = await register_and_login(client, "datahub_publish@example.com")
    workspace_id = await create_workspace(client, token)
    model_id = await create_model(client, token, workspace_id)
    module_id = await create_module(client, token, model_id)
    dimension_id = await create_dimension(client, token, model_id)
    p1_id = await create_dimension_item(client, token, dimension_id, "Product 1", "P1")
    p2_id = await create_dimension_item(client, token, dimension_id, "Product 2", "P2")
    line_item_id = await create_line_item(
        client,
        token,
        module_id,
        "Revenue",
        applies_to_dimensions=[dimension_id],
    )

    table = await create_data_hub_table(
        client,
        token,
        model_id,
        name="publish_source",
        schema_definition=[
            {"name": "product_code", "data_type": "text", "nullable": False},
            {"name": "amount", "data_type": "number", "nullable": False},
        ],
    )
    table_id = table["id"]

    seed_resp = await client.put(
        "/data-hub/tables/%s/rows" % table_id,
        json={
            "rows": [
                {"product_code": "P1", "amount": 100},
                {"product_code": "P2", "amount": 200},
            ]
        },
        headers=auth_headers(token),
    )
    assert seed_resp.status_code == 200

    publish_resp = await client.post(
        "/data-hub/tables/%s/publish" % table_id,
        json={
            "module_id": module_id,
            "line_item_map": {"amount": line_item_id},
            "dimension_columns": ["product_code"],
            "dimension_member_map": {
                "product_code": {
                    "P1": p1_id,
                    "P2": p2_id,
                }
            },
            "batch_size": 200,
        },
        headers=auth_headers(token),
    )
    assert publish_resp.status_code == 200, publish_resp.text
    publish_data = publish_resp.json()
    assert publish_data["rows_processed"] == 2
    assert publish_data["cells_written"] == 2
    assert publish_data["target_module_id"] == module_id

    lineage_resp = await client.get(
        "/data-hub/tables/%s/lineage" % table_id,
        headers=auth_headers(token),
    )
    assert lineage_resp.status_code == 200
    lineage = lineage_resp.json()
    assert len(lineage) == 1
    assert lineage[0]["target_module_id"] == module_id
    assert lineage[0]["records_published"] == 2

    module_cells_resp = await client.get(
        "/modules/%s/cells" % module_id,
        headers=auth_headers(token),
    )
    assert module_cells_resp.status_code == 200
    module_cells = module_cells_resp.json()
    assert len(module_cells) == 2
    values = sorted(float(row["value"]) for row in module_cells)
    assert values == [100.0, 200.0]
