from __future__ import annotations

from fastapi.testclient import TestClient


def _book(admin_client: TestClient, *, isbn: str, copies: int = 2):
    r = admin_client.post(
        "/books",
        json={
            "title": "Borrow Me",
            "author": "A",
            "isbn": isbn,
            "total_copies": copies,
            "available_copies": copies,
        },
    )
    assert r.status_code == 201
    return r.json()["data"]["id"]


def test_borrow_happy_path(member_client: TestClient, admin_client: TestClient) -> None:
    bid = _book(admin_client, isbn="ISBN-BORROW-1")
    r = member_client.post("/borrow", json={"book_id": bid})
    assert r.status_code == 201
    assert r.json()["data"]["book_id"] == bid

    r = admin_client.get(f"/books/{bid}")
    assert r.json()["data"]["available_copies"] == 1


def test_already_borrowed_same_book(member_client: TestClient, admin_client: TestClient) -> None:
    bid = _book(admin_client, isbn="ISBN-BORROW-2")
    assert member_client.post("/borrow", json={"book_id": bid}).status_code == 201
    r = member_client.post("/borrow", json={"book_id": bid})
    assert r.status_code == 409


def test_unavailable_book(member_client: TestClient, admin_client: TestClient) -> None:
    bid = _book(admin_client, isbn="ISBN-BORROW-3", copies=1)
    assert member_client.post("/borrow", json={"book_id": bid}).status_code == 201
    client = member_client
    client.post("/auth/logout")
    client.post(
        "/auth/register",
        json={"full_name": "Other", "email": "other@test.com", "password": "pw"},
    )
    client.post("/auth/login", json={"email": "other@test.com", "password": "pw"})
    r = client.post("/borrow", json={"book_id": bid})
    assert r.status_code == 409


def test_return_and_permissions(member_client: TestClient, admin_client: TestClient) -> None:
    bid = _book(admin_client, isbn="ISBN-BORROW-4")
    r = member_client.post("/borrow", json={"book_id": bid})
    rid = r.json()["data"]["id"]

    # Another member cannot return
    member_client.post("/auth/logout")
    member_client.post(
        "/auth/register",
        json={"full_name": "X", "email": "x@test.com", "password": "pw"},
    )
    member_client.post("/auth/login", json={"email": "x@test.com", "password": "pw"})
    assert member_client.post(f"/borrow/{rid}/return").status_code == 403

    member_client.post("/auth/logout")
    member_client.post(
        "/auth/login",
        json={"email": "member@test.com", "password": "memberpassword"},
    )
    assert member_client.post(f"/borrow/{rid}/return").status_code == 200


def test_max_borrow_limit(client: TestClient, admin_client: TestClient) -> None:
    ids = [_book(admin_client, isbn=f"ISBN-LIM-{i}") for i in range(4)]
    client.post(
        "/auth/register",
        json={"full_name": "Lim", "email": "lim@test.com", "password": "pw"},
    )
    client.post("/auth/login", json={"email": "lim@test.com", "password": "pw"})
    for bid in ids[:3]:
        assert client.post("/borrow", json={"book_id": bid}).status_code == 201
    assert client.post("/borrow", json={"book_id": ids[3]}).status_code == 409


def test_borrow_me_cache_header(member_client: TestClient, admin_client: TestClient) -> None:
    bid = _book(admin_client, isbn="ISBN-MECACHE")
    member_client.post("/borrow", json={"book_id": bid})
    assert member_client.get("/borrow/me").headers.get("X-Cache") == "MISS"
    assert member_client.get("/borrow/me").headers.get("X-Cache") == "HIT"
