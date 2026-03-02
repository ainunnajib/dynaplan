from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from httpx import AsyncClient

from app.services.workspace_security import reset_api_key_rate_limit_cache


@pytest.fixture(autouse=True)
def clear_rate_limit_state():
    reset_api_key_rate_limit_cache()
    yield
    reset_api_key_rate_limit_cache()


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


def api_key_headers(raw_key: str, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    headers = {"X-API-Key": raw_key}
    if extra:
        headers.update(extra)
    return headers


async def create_workspace(
    client: AsyncClient,
    token: str,
    name: str = "Security Workspace",
) -> str:
    resp = await client.post(
        "/workspaces/",
        json={"name": name},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def create_model(
    client: AsyncClient,
    token: str,
    workspace_id: str,
    name: str = "Security Model",
) -> str:
    resp = await client.post(
        "/models",
        json={"name": name, "workspace_id": workspace_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def create_api_key(
    client: AsyncClient,
    token: str,
    scopes,
    rate_limit_per_minute: Optional[int] = None,
) -> dict:
    payload = {"name": "Security Key", "scopes": scopes}
    if rate_limit_per_minute is not None:
        payload["rate_limit_per_minute"] = rate_limit_per_minute

    resp = await client.post(
        "/api-keys",
        json=payload,
        headers=auth_headers(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def make_self_signed_certificate() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Dynaplan Test"),
            x509.NameAttribute(NameOID.COMMON_NAME, "dynaplan.local"),
        ]
    )
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(private_key=key, algorithm=hashes.SHA256())
    )
    return certificate.public_bytes(serialization.Encoding.PEM).decode("utf-8")


@pytest.mark.asyncio
async def test_workspace_security_policy_defaults_created(client: AsyncClient):
    token = await register_and_login(client, "f071_default_policy@example.com")
    workspace_id = await create_workspace(client, token)

    resp = await client.get(
        "/workspaces/%s/security" % workspace_id,
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["workspace_id"] == workspace_id
    assert body["enforce_ip_allowlist"] is False
    assert body["require_client_certificate"] is False
    assert body["ip_allowlist"] is None


@pytest.mark.asyncio
async def test_workspace_security_policy_update_and_fetch(client: AsyncClient):
    token = await register_and_login(client, "f071_policy_update@example.com")
    workspace_id = await create_workspace(client, token)

    update_resp = await client.put(
        "/workspaces/%s/security" % workspace_id,
        json={
            "ip_allowlist": ["203.0.113.0/24", "198.51.100.10"],
            "enforce_ip_allowlist": True,
            "require_client_certificate": True,
        },
        headers=auth_headers(token),
    )
    assert update_resp.status_code == 200, update_resp.text
    updated = update_resp.json()
    assert updated["enforce_ip_allowlist"] is True
    assert updated["require_client_certificate"] is True
    assert "203.0.113.0/24" in updated["ip_allowlist"]
    assert "198.51.100.10/32" in updated["ip_allowlist"]

    fetch_resp = await client.get(
        "/workspaces/%s/security" % workspace_id,
        headers=auth_headers(token),
    )
    assert fetch_resp.status_code == 200
    assert fetch_resp.json()["enforce_ip_allowlist"] is True


@pytest.mark.asyncio
async def test_workspace_security_policy_rejects_empty_allowlist_when_enforced(client: AsyncClient):
    token = await register_and_login(client, "f071_policy_empty_allowlist@example.com")
    workspace_id = await create_workspace(client, token)

    resp = await client.put(
        "/workspaces/%s/security" % workspace_id,
        json={"ip_allowlist": [], "enforce_ip_allowlist": True},
        headers=auth_headers(token),
    )
    assert resp.status_code == 400
    assert "ip_allowlist cannot be empty" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_workspace_security_policy_requires_workspace_owner(client: AsyncClient):
    owner_token = await register_and_login(client, "f071_owner@example.com")
    other_token = await register_and_login(client, "f071_not_owner@example.com")
    workspace_id = await create_workspace(client, owner_token)

    resp = await client.get(
        "/workspaces/%s/security" % workspace_id,
        headers=auth_headers(other_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_workspace_certificate_register_list_and_deactivate(client: AsyncClient):
    token = await register_and_login(client, "f071_cert_crud@example.com")
    workspace_id = await create_workspace(client, token)
    fingerprint = "a" * 64

    create_resp = await client.post(
        "/workspaces/%s/security/certificates" % workspace_id,
        json={"name": "Primary", "fingerprint_sha256": fingerprint},
        headers=auth_headers(token),
    )
    assert create_resp.status_code == 201, create_resp.text
    cert_id = create_resp.json()["id"]

    list_resp = await client.get(
        "/workspaces/%s/security/certificates" % workspace_id,
        headers=auth_headers(token),
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1
    assert list_resp.json()[0]["fingerprint_sha256"] == fingerprint

    delete_resp = await client.delete(
        "/workspaces/%s/security/certificates/%s" % (workspace_id, cert_id),
        headers=auth_headers(token),
    )
    assert delete_resp.status_code == 200
    assert delete_resp.json()["is_active"] is False

    list_active_resp = await client.get(
        "/workspaces/%s/security/certificates" % workspace_id,
        headers=auth_headers(token),
    )
    assert list_active_resp.status_code == 200
    assert list_active_resp.json() == []

    list_all_resp = await client.get(
        "/workspaces/%s/security/certificates?include_inactive=true" % workspace_id,
        headers=auth_headers(token),
    )
    assert list_all_resp.status_code == 200
    assert len(list_all_resp.json()) == 1
    assert list_all_resp.json()[0]["is_active"] is False


@pytest.mark.asyncio
async def test_workspace_certificate_duplicate_rejected(client: AsyncClient):
    token = await register_and_login(client, "f071_cert_duplicate@example.com")
    workspace_id = await create_workspace(client, token)
    fingerprint = "b" * 64

    first_resp = await client.post(
        "/workspaces/%s/security/certificates" % workspace_id,
        json={"fingerprint_sha256": fingerprint},
        headers=auth_headers(token),
    )
    assert first_resp.status_code == 201

    second_resp = await client.post(
        "/workspaces/%s/security/certificates" % workspace_id,
        json={"fingerprint_sha256": fingerprint},
        headers=auth_headers(token),
    )
    assert second_resp.status_code == 409


@pytest.mark.asyncio
async def test_public_api_blocks_non_allowlisted_ip(client: AsyncClient):
    token = await register_and_login(client, "f071_ip_block@example.com")
    workspace_id = await create_workspace(client, token)
    await create_model(client, token, workspace_id)
    key_data = await create_api_key(client, token, scopes=["read:models"])

    update_resp = await client.put(
        "/workspaces/%s/security" % workspace_id,
        json={"ip_allowlist": ["203.0.113.0/24"], "enforce_ip_allowlist": True},
        headers=auth_headers(token),
    )
    assert update_resp.status_code == 200

    resp = await client.get(
        "/api/v1/models?workspace_id=%s" % workspace_id,
        headers=api_key_headers(
            key_data["raw_key"], extra={"X-Forwarded-For": "198.51.100.20"}
        ),
    )
    assert resp.status_code == 403
    assert "allowlist" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_public_api_allows_allowlisted_ip(client: AsyncClient):
    token = await register_and_login(client, "f071_ip_allow@example.com")
    workspace_id = await create_workspace(client, token)
    await create_model(client, token, workspace_id)
    key_data = await create_api_key(client, token, scopes=["read:models"])

    update_resp = await client.put(
        "/workspaces/%s/security" % workspace_id,
        json={"ip_allowlist": ["203.0.113.15"], "enforce_ip_allowlist": True},
        headers=auth_headers(token),
    )
    assert update_resp.status_code == 200

    resp = await client.get(
        "/api/v1/models?workspace_id=%s" % workspace_id,
        headers=api_key_headers(
            key_data["raw_key"], extra={"X-Forwarded-For": "203.0.113.15"}
        ),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_public_api_allowlist_supports_cidr(client: AsyncClient):
    token = await register_and_login(client, "f071_ip_cidr@example.com")
    workspace_id = await create_workspace(client, token)
    await create_model(client, token, workspace_id)
    key_data = await create_api_key(client, token, scopes=["read:models"])

    update_resp = await client.put(
        "/workspaces/%s/security" % workspace_id,
        json={"ip_allowlist": ["10.10.0.0/16"], "enforce_ip_allowlist": True},
        headers=auth_headers(token),
    )
    assert update_resp.status_code == 200

    resp = await client.get(
        "/api/v1/models?workspace_id=%s" % workspace_id,
        headers=api_key_headers(
            key_data["raw_key"], extra={"X-Forwarded-For": "10.10.12.9"}
        ),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_public_api_rejects_missing_certificate_when_required(client: AsyncClient):
    token = await register_and_login(client, "f071_cert_required@example.com")
    workspace_id = await create_workspace(client, token)
    await create_model(client, token, workspace_id)
    key_data = await create_api_key(client, token, scopes=["read:models"])

    update_resp = await client.put(
        "/workspaces/%s/security" % workspace_id,
        json={"require_client_certificate": True},
        headers=auth_headers(token),
    )
    assert update_resp.status_code == 200

    resp = await client.get(
        "/api/v1/models?workspace_id=%s" % workspace_id,
        headers=api_key_headers(key_data["raw_key"]),
    )
    assert resp.status_code == 401
    assert "certificate is required" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_public_api_rejects_unregistered_certificate(client: AsyncClient):
    token = await register_and_login(client, "f071_cert_unknown@example.com")
    workspace_id = await create_workspace(client, token)
    await create_model(client, token, workspace_id)
    key_data = await create_api_key(client, token, scopes=["read:models"])

    update_resp = await client.put(
        "/workspaces/%s/security" % workspace_id,
        json={"require_client_certificate": True},
        headers=auth_headers(token),
    )
    assert update_resp.status_code == 200

    resp = await client.get(
        "/api/v1/models?workspace_id=%s" % workspace_id,
        headers=api_key_headers(
            key_data["raw_key"],
            extra={"X-Client-Cert-Fingerprint": "c" * 64},
        ),
    )
    assert resp.status_code == 401
    assert "not allowlisted" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_public_api_accepts_registered_certificate_fingerprint(client: AsyncClient):
    token = await register_and_login(client, "f071_cert_ok@example.com")
    workspace_id = await create_workspace(client, token)
    await create_model(client, token, workspace_id)
    key_data = await create_api_key(client, token, scopes=["read:models"])
    fingerprint = "d" * 64

    cert_resp = await client.post(
        "/workspaces/%s/security/certificates" % workspace_id,
        json={"fingerprint_sha256": fingerprint},
        headers=auth_headers(token),
    )
    assert cert_resp.status_code == 201

    update_resp = await client.put(
        "/workspaces/%s/security" % workspace_id,
        json={"require_client_certificate": True},
        headers=auth_headers(token),
    )
    assert update_resp.status_code == 200

    resp = await client.get(
        "/api/v1/models?workspace_id=%s" % workspace_id,
        headers=api_key_headers(
            key_data["raw_key"],
            extra={"X-Client-Cert-Fingerprint": fingerprint},
        ),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_certificate_pem_registration_and_header_auth(client: AsyncClient):
    token = await register_and_login(client, "f071_cert_pem@example.com")
    workspace_id = await create_workspace(client, token)
    await create_model(client, token, workspace_id)
    key_data = await create_api_key(client, token, scopes=["read:models"])
    certificate_pem = make_self_signed_certificate()

    create_resp = await client.post(
        "/workspaces/%s/security/certificates" % workspace_id,
        json={"name": "PEM cert", "certificate_pem": certificate_pem},
        headers=auth_headers(token),
    )
    assert create_resp.status_code == 201, create_resp.text
    assert create_resp.json()["subject"] is not None

    update_resp = await client.put(
        "/workspaces/%s/security" % workspace_id,
        json={"require_client_certificate": True},
        headers=auth_headers(token),
    )
    assert update_resp.status_code == 200

    cert_header_value = certificate_pem.replace("\n", "\\n")
    resp = await client.get(
        "/api/v1/models?workspace_id=%s" % workspace_id,
        headers=api_key_headers(
            key_data["raw_key"], extra={"X-Client-Cert": cert_header_value}
        ),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_public_api_rate_limit_enforced_per_key(client: AsyncClient, monkeypatch):
    from app.services import workspace_security as workspace_security_service

    monkeypatch.setattr(workspace_security_service.time, "time", lambda: 1_700_000_000)

    token = await register_and_login(client, "f071_rate_limit@example.com")
    workspace_id = await create_workspace(client, token)
    await create_model(client, token, workspace_id)
    key_data = await create_api_key(
        client,
        token,
        scopes=["read:models"],
        rate_limit_per_minute=2,
    )

    first = await client.get(
        "/api/v1/models?workspace_id=%s" % workspace_id,
        headers=api_key_headers(key_data["raw_key"]),
    )
    second = await client.get(
        "/api/v1/models?workspace_id=%s" % workspace_id,
        headers=api_key_headers(key_data["raw_key"]),
    )
    third = await client.get(
        "/api/v1/models?workspace_id=%s" % workspace_id,
        headers=api_key_headers(key_data["raw_key"]),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert "rate limit exceeded" in third.json()["detail"].lower()
    assert third.headers.get("Retry-After") is not None


@pytest.mark.asyncio
async def test_public_api_rate_limit_isolated_per_key(client: AsyncClient, monkeypatch):
    from app.services import workspace_security as workspace_security_service

    monkeypatch.setattr(workspace_security_service.time, "time", lambda: 1_700_000_000)

    token = await register_and_login(client, "f071_rate_key_isolation@example.com")
    workspace_id = await create_workspace(client, token)
    await create_model(client, token, workspace_id)

    key_one = await create_api_key(
        client,
        token,
        scopes=["read:models"],
        rate_limit_per_minute=1,
    )
    key_two = await create_api_key(
        client,
        token,
        scopes=["read:models"],
        rate_limit_per_minute=1,
    )

    first_key_one = await client.get(
        "/api/v1/models?workspace_id=%s" % workspace_id,
        headers=api_key_headers(key_one["raw_key"]),
    )
    second_key_one = await client.get(
        "/api/v1/models?workspace_id=%s" % workspace_id,
        headers=api_key_headers(key_one["raw_key"]),
    )
    first_key_two = await client.get(
        "/api/v1/models?workspace_id=%s" % workspace_id,
        headers=api_key_headers(key_two["raw_key"]),
    )

    assert first_key_one.status_code == 200
    assert second_key_one.status_code == 429
    assert first_key_two.status_code == 200
