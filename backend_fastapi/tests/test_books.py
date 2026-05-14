from __future__ import annotations

from fastapi.testclient import TestClient


def _sample_book_payload(**kwargs):
    base = {
        "title": "Test Book",
        "author": "Author",
        "isbn": "ISBN-TEST-001",
        "publisher": "Pub",
        "published_year": 2020,
        "total_copies": 3,
        "available_copies": 3,
    }
    base.update(kwargs)
    return base


def test_list_books_cache_miss_then_hit(member_client: TestClient, admin_client: TestClient) -> None:
    r = admin_client.post("/books", json=_sample_book_payload(isbn="ISBN-CACHE-1"))
    assert r.status_code == 201

    r1 = member_client.get("/books")
    assert r1.headers.get("X-Cache") == "MISS"

    r2 = member_client.get("/books")
    assert r2.headers.get("X-Cache") == "HIT"


def test_create_book_admin_only(admin_client: TestClient, member_client: TestClient) -> None:
    r = admin_client.post("/books", json=_sample_book_payload(isbn="ISBN-ADMIN-1"))
    assert r.status_code == 201

    r = member_client.post("/books", json=_sample_book_payload(isbn="ISBN-FAIL-1"))
    assert r.status_code == 403


def test_update_delete_admin(admin_client: TestClient) -> None:
    r = admin_client.post("/books", json=_sample_book_payload(isbn="ISBN-EDIT-1"))
    assert r.status_code == 201
    book_id = r.json()["data"]["id"]

    r = admin_client.patch(f"/books/{book_id}", json={"title": "Updated"})
    assert r.status_code == 200
    assert r.json()["data"]["title"] == "Updated"

    r = admin_client.delete(f"/books/{book_id}")
    assert r.status_code == 204


def test_book_not_found(admin_client: TestClient) -> None:
    assert admin_client.patch("/books/99999", json={"title": "x"}).status_code == 404


def test_validation_negative_copies(admin_client: TestClient) -> None:
    r = admin_client.post(
        "/books",
        json=_sample_book_payload(isbn="ISBN-NEG", total_copies=-1, available_copies=-1),
    )
    assert r.status_code == 422


def test_duplicate_isbn(admin_client: TestClient) -> None:
    p = _sample_book_payload(isbn="ISBN-DUP")
    assert admin_client.post("/books", json=p).status_code == 201
    r = admin_client.post("/books", json=p)
    assert r.status_code == 409
