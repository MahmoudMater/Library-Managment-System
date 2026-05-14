from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps.auth import admin_only, get_current_user_access
from app.core.db import get_db
from app.core.logging_config import get_logger
from app.core.redis_client import get_redis
from app.core.settings import get_settings
from app.models import User
from app.schemas.book import BookCreate, BookPublic, BookUpdate
from app.services.book_service import BookService, book_to_dict
from app.utils.cache import (
    BOOKS_LIST_KEY,
    book_cache_key,
    cache_get,
    cache_set,
    invalidate_books_cache,
)
from app.utils.response import api_response

router = APIRouter(prefix="/books", tags=["books"])


@router.get("", summary="List books", description="Cache-aside list (Redis). Members and admins.")
def list_books(
    _user: User = Depends(get_current_user_access),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    r = get_redis()
    ttl = settings.books_cache_ttl_seconds
    log = get_logger("app.books")

    cached = cache_get(r, BOOKS_LIST_KEY)
    if cached is not None:
        resp = api_response(message="OK", data={"items": cached})
        resp.headers["X-Cache"] = "HIT"
        return resp

    items = BookService.list_books(session=db)
    cache_set(r, BOOKS_LIST_KEY, items, ttl_seconds=ttl)
    log.info("books_list_db", extra={"event": "books_read", "source": "database"})
    resp = api_response(message="OK", data={"items": items})
    resp.headers["X-Cache"] = "MISS"
    return resp


@router.get("/{book_id}", summary="Get book by ID", description="Cache-aside by primary key.")
def get_book(
    book_id: int,
    _user: User = Depends(get_current_user_access),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    r = get_redis()
    ttl = settings.books_cache_ttl_seconds
    key = book_cache_key(book_id)

    cached = cache_get(r, key)
    if cached is not None:
        resp = api_response(message="OK", data=cached)
        resp.headers["X-Cache"] = "HIT"
        return resp

    book = BookService.get_by_id(session=db, book_id=book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    data = book_to_dict(book)
    cache_set(r, key, data, ttl_seconds=ttl)
    resp = api_response(message="OK", data=data)
    resp.headers["X-Cache"] = "MISS"
    return resp


@router.post("", status_code=201, summary="Create book", description="Admin only; invalidates list cache.")
def create_book(
    body: BookCreate,
    _admin: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    log = get_logger("app.books")
    if body.available_copies > body.total_copies:
        raise HTTPException(
            status_code=400,
            detail="available_copies cannot exceed total_copies",
        )
    try:
        book = BookService.create(session=db, body=body)
    except IntegrityError:
        get_logger("app.books").warning(
            "book_create_conflict",
            extra={"event": "books_create", "isbn": body.isbn},
        )
        raise HTTPException(status_code=409, detail="Book with this ISBN already exists") from None
    invalidate_books_cache(get_redis(), book_id=None)
    log.info(
        "book_created",
        extra={"event": "books_create", "book_id": book.id, "isbn": book.isbn},
    )
    return api_response(
        message="Created",
        data=BookPublic.model_validate(book).model_dump(mode="json"),
        status_code=201,
    )


@router.patch("/{book_id}", summary="Update book", description="Admin only; invalidates caches.")
@router.put("/{book_id}", summary="Update book (PUT)", description="Same as PATCH; invalidates caches.")
def update_book(
    book_id: int,
    body: BookUpdate,
    _admin: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    log = get_logger("app.books")
    book = BookService.get_by_id(session=db, book_id=book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    patch = body.model_dump(exclude_unset=True)
    if "total_copies" in patch or "available_copies" in patch:
        tc = patch.get("total_copies", book.total_copies)
        ac = patch.get("available_copies", book.available_copies)
        if ac > tc:
            raise HTTPException(
                status_code=400,
                detail="available_copies cannot exceed total_copies",
            )
    try:
        book = BookService.update(session=db, book=book, body=body)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="ISBN conflict") from None
    invalidate_books_cache(get_redis(), book_id=book_id)
    log.info("book_updated", extra={"event": "books_update", "book_id": book_id})
    return api_response(
        message="Updated",
        data=BookPublic.model_validate(book).model_dump(mode="json"),
    )


@router.delete("/{book_id}", status_code=204, summary="Delete book", description="Admin only; invalidates caches.")
def delete_book(
    book_id: int,
    _admin: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    log = get_logger("app.books")
    book = BookService.get_by_id(session=db, book_id=book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    BookService.delete(session=db, book=book)
    invalidate_books_cache(get_redis(), book_id=book_id)
    log.info("book_deleted", extra={"event": "books_delete", "book_id": book_id})
    return Response(status_code=204)
