import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "email": "alice@example.com",
        "full_name": "Alice Smith",
        "password": "secret123",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "alice@example.com"
    assert data["full_name"] == "Alice Smith"
    assert data["role"] == "viewer"
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    payload = {
        "email": "dup@example.com",
        "full_name": "Dup User",
        "password": "secret123",
    }
    resp = await client.post("/auth/register", json=payload)
    assert resp.status_code == 201

    resp2 = await client.post("/auth/register", json=payload)
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_register_with_role(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "email": "admin@example.com",
        "full_name": "Admin User",
        "password": "secret123",
        "role": "admin",
    })
    assert resp.status_code == 201
    assert resp.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    await client.post("/auth/register", json={
        "email": "bob@example.com",
        "full_name": "Bob Jones",
        "password": "mypassword",
    })

    resp = await client.post("/auth/login", json={
        "email": "bob@example.com",
        "password": "mypassword",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post("/auth/register", json={
        "email": "carol@example.com",
        "full_name": "Carol",
        "password": "correct",
    })

    resp = await client.post("/auth/login", json={
        "email": "carol@example.com",
        "password": "wrong",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    resp = await client.post("/auth/login", json={
        "email": "nobody@example.com",
        "password": "nope",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_authenticated(client: AsyncClient):
    await client.post("/auth/register", json={
        "email": "dave@example.com",
        "full_name": "Dave",
        "password": "pass123",
    })
    login_resp = await client.post("/auth/login", json={
        "email": "dave@example.com",
        "password": "pass123",
    })
    token = login_resp.json()["access_token"]

    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "dave@example.com"
    assert data["full_name"] == "Dave"


@pytest.mark.asyncio
async def test_me_no_token(client: AsyncClient):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_invalid_token(client: AsyncClient):
    resp = await client.get("/auth/me", headers={"Authorization": "Bearer bad.token.here"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout(client: AsyncClient):
    resp = await client.post("/auth/logout")
    assert resp.status_code == 200
    assert resp.json()["message"] == "Logged out successfully"
