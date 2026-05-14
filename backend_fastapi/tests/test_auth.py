from __future__ import annotations

from fastapi.testclient import TestClient


def test_register_and_login(client: TestClient) -> None:
    r = client.post(
        "/auth/register",
        json={
            "full_name": "Alice",
            "email": "alice@example.com",
            "password": "alicepassword",
        },
    )
    assert r.status_code == 201
    assert r.json()["success"] is True
    assert r.json()["data"]["email"] == "alice@example.com"

    r = client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "alicepassword"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["role"] == "member"


def test_register_duplicate_email(client: TestClient) -> None:
    body = {
        "full_name": "A",
        "email": "dup@example.com",
        "password": "p",
    }
    assert client.post("/auth/register", json=body).status_code == 201
    r = client.post("/auth/register", json=body)
    assert r.status_code == 409


def test_login_invalid_credentials(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={"full_name": "Bob", "email": "bob@example.com", "password": "bobpass"},
    )
    r = client.post(
        "/auth/login",
        json={"email": "bob@example.com", "password": "wrong"},
    )
    assert r.status_code == 401


def test_me_requires_auth(client: TestClient) -> None:
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_me_authenticated(member_client: TestClient) -> None:
    r = member_client.get("/auth/me")
    assert r.status_code == 200
    assert r.json()["data"]["email"] == "member@test.com"


def test_refresh_flow(admin_client: TestClient) -> None:
    r = admin_client.post("/auth/refresh")
    assert r.status_code == 200


def test_revoke_logs_out(admin_client: TestClient) -> None:
    assert admin_client.post("/auth/revoke").status_code == 200
    assert admin_client.get("/auth/me").status_code == 401
