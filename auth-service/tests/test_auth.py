from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def _register(client, email="user@example.com", password="supersecret123"):
    return await client.post("/auth/register", json={"email": email, "password": password})


async def test_register_creates_user(client):
    r = await _register(client)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "user@example.com"
    assert body["is_active"] is True
    assert "id" in body


async def test_register_duplicate_email_rejected(client):
    await _register(client)
    r2 = await _register(client)
    assert r2.status_code == 409


async def test_login_with_wrong_password_fails(client):
    await _register(client)
    r = await client.post(
        "/auth/login", json={"email": "user@example.com", "password": "wrong-password"}
    )
    assert r.status_code == 401


async def test_login_with_unknown_email_fails_same_as_wrong_password(client):
    r1 = await client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "whatever123"}
    )
    await _register(client)
    r2 = await client.post(
        "/auth/login", json={"email": "user@example.com", "password": "wrong-password"}
    )
    # Both "unknown user" and "wrong password" must look identical to the caller.
    assert r1.status_code == r2.status_code == 401
    assert r1.json() == r2.json()


async def test_login_success_returns_token_pair(client):
    await _register(client)
    r = await client.post(
        "/auth/login", json={"email": "user@example.com", "password": "supersecret123"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert body["access_token"]
    assert body["refresh_token"]


async def test_me_requires_valid_bearer_token(client):
    r = await client.get("/auth/me")
    assert r.status_code == 401

    r2 = await client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert r2.status_code == 401


async def test_me_returns_current_user_with_valid_token(client):
    await _register(client)
    login = await client.post(
        "/auth/login", json={"email": "user@example.com", "password": "supersecret123"}
    )
    access_token = login.json()["access_token"]

    r = await client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "user@example.com"


async def test_refresh_rotates_token_and_old_one_becomes_invalid(client):
    await _register(client)
    login = await client.post(
        "/auth/login", json={"email": "user@example.com", "password": "supersecret123"}
    )
    old_refresh = login.json()["refresh_token"]

    r = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert r.status_code == 200
    new_tokens = r.json()
    assert new_tokens["refresh_token"] != old_refresh

    # Reusing the now-rotated-out token must fail (reuse/theft detection).
    r2 = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert r2.status_code == 401


async def test_refresh_with_garbage_token_fails(client):
    r = await client.post("/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert r.status_code == 401


async def test_logout_revokes_refresh_token(client):
    await _register(client)
    login = await client.post(
        "/auth/login", json={"email": "user@example.com", "password": "supersecret123"}
    )
    refresh_token = login.json()["refresh_token"]

    r = await client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert r.status_code == 200

    r2 = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert r2.status_code == 401


async def test_jwks_endpoint_exposes_public_key(client):
    r = await client.get("/auth/.well-known/jwks.json")
    assert r.status_code == 200
    keys = r.json()["keys"]
    assert len(keys) == 1
    assert keys[0]["kty"] == "RSA"
    assert keys[0]["alg"] == "RS256"
    assert "n" in keys[0] and "e" in keys[0]


async def test_password_too_short_is_rejected(client):
    r = await client.post(
        "/auth/register", json={"email": "shortpass@example.com", "password": "short"}
    )
    assert r.status_code == 422
