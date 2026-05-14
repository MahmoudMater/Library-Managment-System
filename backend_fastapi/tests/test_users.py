from __future__ import annotations

from fastapi.testclient import TestClient


def test_users_list_admin_only(admin_client: TestClient, member_client: TestClient) -> None:
    assert admin_client.get("/users").status_code == 200
    assert member_client.get("/users").status_code == 403


def test_users_me(member_client: TestClient) -> None:
    r = member_client.get("/users/me")
    assert r.status_code == 200
    assert r.json()["data"]["email"] == "member@test.com"


def test_admin_patch_user(admin_client: TestClient, member_client: TestClient) -> None:
    r = member_client.get("/users/me")
    uid = r.json()["data"]["id"]
    r = admin_client.patch(f"/users/{uid}", json={"max_borrow_limit": 5})
    assert r.status_code == 200
    assert r.json()["data"]["max_borrow_limit"] == 5


def test_admin_create_user_with_role(admin_client: TestClient) -> None:
    r = admin_client.post(
        "/users",
        json={
            "full_name": "New Admin",
            "email": "newadmin@test.com",
            "password": "strongpassword",
            "role": "admin",
            "max_borrow_limit": 10,
            "is_active": True,
        },
    )
    assert r.status_code == 201, r.json()
    assert r.json()["data"]["email"] == "newadmin@test.com"
    assert r.json()["data"]["role"] == "admin"
