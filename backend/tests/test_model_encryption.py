import base64
import uuid
from typing import Dict, List, Optional, Tuple

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.cell import CellValue
from tests.conftest import TestSession


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


def auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": "Bearer %s" % token}


async def create_workspace(
    client: AsyncClient, token: str, name: str = "Encryption Workspace"
) -> str:
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
    name: str = "Encryption Model",
) -> str:
    resp = await client.post(
        "/models",
        json={"name": name, "workspace_id": workspace_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def create_module(
    client: AsyncClient,
    token: str,
    model_id: str,
    name: str = "Encryption Module",
) -> str:
    resp = await client.post(
        "/models/%s/modules" % model_id,
        json={"name": name},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def create_line_item(
    client: AsyncClient,
    token: str,
    module_id: str,
    name: str = "Encrypted Line Item",
) -> str:
    resp = await client.post(
        "/modules/%s/line-items" % module_id,
        json={"name": name, "format": "number"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def setup_line_item(client: AsyncClient, email_suffix: str) -> Tuple[str, str, str, str]:
    token = await register_and_login(client, "f070_%s@example.com" % email_suffix)
    workspace_id = await create_workspace(client, token)
    model_id = await create_model(client, token, workspace_id)
    module_id = await create_module(client, token, model_id)
    line_item_id = await create_line_item(client, token, module_id)
    return token, model_id, module_id, line_item_id


async def write_cell(
    client: AsyncClient,
    token: str,
    line_item_id: str,
    value,
    dimension_member: Optional[str] = None,
) -> None:
    member = dimension_member or str(uuid.uuid4())
    resp = await client.post(
        "/cells",
        json={
            "line_item_id": line_item_id,
            "dimension_members": [member],
            "value": value,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text


async def query_cells(client: AsyncClient, token: str, line_item_id: str) -> List[dict]:
    resp = await client.post(
        "/cells/query",
        json={"line_item_id": line_item_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def enable_encryption(
    client: AsyncClient,
    token: str,
    model_id: str,
    payload: Optional[dict] = None,
) -> dict:
    resp = await client.post(
        "/models/%s/encryption/enable" % model_id,
        json=payload or {},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def rotate_encryption(
    client: AsyncClient,
    token: str,
    model_id: str,
    payload: Optional[dict] = None,
) -> dict:
    resp = await client.post(
        "/models/%s/encryption/rotate" % model_id,
        json=payload or {},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def fetch_single_cell_row(line_item_id: str) -> CellValue:
    async with TestSession() as db:
        result = await db.execute(
            select(CellValue).where(CellValue.line_item_id == uuid.UUID(line_item_id))
        )
        rows = list(result.scalars().all())
        assert len(rows) == 1
        return rows[0]


@pytest.mark.asyncio
async def test_model_encryption_status_defaults_disabled(client: AsyncClient):
    token, model_id, _module_id, _line_item_id = await setup_line_item(client, "status_default")

    resp = await client.get(
        "/models/%s/encryption" % model_id,
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["model_id"] == model_id
    assert body["encryption_enabled"] is False
    assert body["active_key_version"] is None
    assert body["key_count"] == 0


@pytest.mark.asyncio
async def test_enable_model_encryption_and_status(client: AsyncClient):
    token, model_id, _module_id, _line_item_id = await setup_line_item(client, "enable_status")

    body = await enable_encryption(client, token, model_id)
    assert body["encryption_enabled"] is True
    assert body["active_key_version"] == 1
    assert body["kms_provider"] == "local"
    assert body["key_count"] == 1

    status_resp = await client.get(
        "/models/%s/encryption" % model_id,
        headers=auth_headers(token),
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["encryption_enabled"] is True


@pytest.mark.asyncio
async def test_enable_model_encryption_rejects_duplicate_enable(client: AsyncClient):
    token, model_id, _module_id, _line_item_id = await setup_line_item(client, "enable_duplicate")
    await enable_encryption(client, token, model_id)

    resp = await client.post(
        "/models/%s/encryption/enable" % model_id,
        json={},
        headers=auth_headers(token),
    )
    assert resp.status_code == 400
    assert "already enabled" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_encrypted_model_stores_ciphertext_at_rest(client: AsyncClient):
    token, model_id, _module_id, line_item_id = await setup_line_item(client, "ciphertext_rest")
    await enable_encryption(client, token, model_id)

    dimension_member = str(uuid.uuid4())
    secret_value = "top-secret-plan-value"
    await write_cell(
        client,
        token,
        line_item_id=line_item_id,
        value=secret_value,
        dimension_member=dimension_member,
    )

    cells = await query_cells(client, token, line_item_id)
    assert len(cells) == 1
    assert cells[0]["value"] == secret_value
    assert cells[0]["value_type"] == "text"

    row = await fetch_single_cell_row(line_item_id)
    assert row.value_text is None
    assert row.value_number is None
    assert row.value_boolean is None
    assert row.value_encrypted is not None
    assert secret_value not in str(row.value_encrypted)
    assert row.encryption_key_id is not None


@pytest.mark.asyncio
async def test_enable_encryption_encrypts_existing_plaintext_cells(client: AsyncClient):
    token, model_id, _module_id, line_item_id = await setup_line_item(client, "encrypt_existing")

    dimension_member = str(uuid.uuid4())
    await write_cell(
        client,
        token,
        line_item_id=line_item_id,
        value=123.45,
        dimension_member=dimension_member,
    )

    before_row = await fetch_single_cell_row(line_item_id)
    assert before_row.value_number == 123.45
    assert before_row.value_encrypted is None

    await enable_encryption(client, token, model_id)

    after_row = await fetch_single_cell_row(line_item_id)
    assert after_row.value_number is None
    assert after_row.value_encrypted is not None
    assert after_row.encryption_key_id is not None

    cells = await query_cells(client, token, line_item_id)
    assert len(cells) == 1
    assert cells[0]["value"] == 123.45
    assert cells[0]["value_type"] == "number"


@pytest.mark.asyncio
async def test_rotate_model_encryption_key_reencrypts_cells(client: AsyncClient):
    token, model_id, _module_id, line_item_id = await setup_line_item(client, "rotate")
    await enable_encryption(client, token, model_id)

    await write_cell(
        client,
        token,
        line_item_id=line_item_id,
        value=True,
        dimension_member=str(uuid.uuid4()),
    )

    row_before = await fetch_single_cell_row(line_item_id)
    encrypted_before = row_before.value_encrypted
    key_before = row_before.encryption_key_id

    status = await rotate_encryption(client, token, model_id)
    assert status["encryption_enabled"] is True
    assert status["active_key_version"] == 2
    assert status["key_count"] == 2

    row_after = await fetch_single_cell_row(line_item_id)
    assert row_after.value_encrypted is not None
    assert row_after.value_encrypted != encrypted_before
    assert row_after.encryption_key_id is not None
    assert row_after.encryption_key_id != key_before

    cells = await query_cells(client, token, line_item_id)
    assert len(cells) == 1
    assert cells[0]["value"] is True
    assert cells[0]["value_type"] == "boolean"


@pytest.mark.asyncio
async def test_rotate_requires_encryption_enabled(client: AsyncClient):
    token, model_id, _module_id, _line_item_id = await setup_line_item(client, "rotate_not_enabled")

    resp = await client.post(
        "/models/%s/encryption/rotate" % model_id,
        json={},
        headers=auth_headers(token),
    )
    assert resp.status_code == 400
    assert "not enabled" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_aws_kms_provider_path_with_mocked_provider(client: AsyncClient, monkeypatch):
    from app.services import model_encryption as encryption_service

    def fake_wrap_key(raw_data_key: bytes, kms_key_id: str) -> str:
        assert kms_key_id == "arn:aws:kms:us-east-1:123456789012:key/test"
        return base64.b64encode(raw_data_key).decode("ascii")

    def fake_unwrap_key(wrapped_key: str) -> bytes:
        return base64.b64decode(wrapped_key.encode("ascii"))

    monkeypatch.setattr(encryption_service, "_aws_wrap_key", fake_wrap_key)
    monkeypatch.setattr(encryption_service, "_aws_unwrap_key", fake_unwrap_key)
    encryption_service.clear_model_encryption_key_cache()

    token, model_id, _module_id, line_item_id = await setup_line_item(client, "aws_provider")
    status = await enable_encryption(
        client,
        token,
        model_id,
        payload={
            "kms_provider": "aws_kms",
            "kms_key_id": "arn:aws:kms:us-east-1:123456789012:key/test",
        },
    )
    assert status["kms_provider"] == "aws_kms"
    assert status["kms_key_id"] == "arn:aws:kms:us-east-1:123456789012:key/test"

    await write_cell(client, token, line_item_id=line_item_id, value=88.0)
    cells = await query_cells(client, token, line_item_id)
    assert len(cells) == 1
    assert cells[0]["value"] == 88.0


@pytest.mark.asyncio
async def test_module_cells_endpoint_reads_decrypted_values(client: AsyncClient):
    token, model_id, module_id, line_item_id = await setup_line_item(client, "module_cells")
    await enable_encryption(client, token, model_id)

    dimension_member = str(uuid.uuid4())
    write_resp = await client.put(
        "/modules/%s/cells" % module_id,
        json={
            "line_item_id": line_item_id,
            "dimension_member_ids": [dimension_member],
            "value": "module-visible",
        },
        headers=auth_headers(token),
    )
    assert write_resp.status_code == 200, write_resp.text

    list_resp = await client.get(
        "/modules/%s/cells" % module_id,
        headers=auth_headers(token),
    )
    assert list_resp.status_code == 200, list_resp.text
    rows = list_resp.json()
    assert len(rows) == 1
    assert rows[0]["line_item_id"] == line_item_id
    assert rows[0]["value"] == "module-visible"


@pytest.mark.asyncio
async def test_list_model_encryption_keys_returns_versions(client: AsyncClient):
    token, model_id, _module_id, _line_item_id = await setup_line_item(client, "list_keys")
    await enable_encryption(client, token, model_id)
    await rotate_encryption(client, token, model_id)

    resp = await client.get(
        "/models/%s/encryption/keys" % model_id,
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    keys = resp.json()
    assert len(keys) == 2
    versions = sorted(key["key_version"] for key in keys)
    assert versions == [1, 2]
    active_keys = [key for key in keys if key["is_active"]]
    assert len(active_keys) == 1
    assert active_keys[0]["key_version"] == 2
