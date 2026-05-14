from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps.auth import admin_only, get_current_user_access
from app.core.db import get_db
from app.core.logging_config import get_logger
from app.core.redis_client import get_redis
from app.core.settings import get_settings
from app.models import User
from app.models.enums import BorrowStatus, UserRole
from app.schemas.borrow import BorrowCreate, BorrowRecordPublic
from app.services.borrow_service import BorrowService, borrow_record_to_dict
from app.utils.cache import (
    borrow_user_history_key,
    cache_get,
    cache_set,
    invalidate_books_cache,
    invalidate_borrow_user_cache,
)
from app.utils.response import Pagination, api_response, paginated_response

router = APIRouter(prefix="/borrow", tags=["borrow"])


def _borrow_http_exception(code: str) -> HTTPException:
    mapping: dict[str, tuple[int, str]] = {
        "BOOK_NOT_FOUND": (404, "Book not found"),
        "USER_NOT_FOUND": (404, "User not found"),
        "BOOK_UNAVAILABLE": (409, "No copies available to borrow"),
        "LIMIT_REACHED": (409, "Maximum active borrows reached for this account"),
        "ALREADY_BORROWED": (409, "You already have an active borrow for this book"),
        "RECORD_NOT_FOUND": (404, "Borrow record not found"),
        "NOT_OWNER": (403, "You can only return your own borrows"),
        "ALREADY_RETURNED": (409, "This borrow is already completed"),
    }
    status, detail = mapping.get(code, (400, code))
    return HTTPException(status_code=status, detail=detail)


def _parse_status(raw: str | None) -> BorrowStatus | None:
    if raw is None or raw == "":
        return None
    try:
        return BorrowStatus(raw.strip().lower())
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid status: {raw}") from None


@router.post("", status_code=201, summary="Borrow a book")
def borrow_book(
    body: BorrowCreate,
    user: User = Depends(get_current_user_access),
    db: Session = Depends(get_db),
):
    log = get_logger("app.borrow")
    try:
        rec = BorrowService.borrow(
            session=db,
            user=user,
            book_id=body.book_id,
            due_date=body.due_date,
        )
    except ValueError as e:
        raise _borrow_http_exception(str(e)) from None

    r = get_redis()
    invalidate_books_cache(r, book_id=body.book_id)
    invalidate_borrow_user_cache(r, user.id)

    log.info(
        "borrow_created",
        extra={
            "event": "borrow_create",
            "user_id": user.id,
            "book_id": body.book_id,
            "record_id": rec.id,
        },
    )
    full = BorrowService.get_by_id(session=db, record_id=rec.id)
    assert full is not None
    data = borrow_record_to_dict(
        full,
        book_title=full.book.title if full.book else None,
        user_email=full.user.email if full.user else None,
    )
    return api_response(
        message="Borrowed",
        data=BorrowRecordPublic.model_validate(data).model_dump(mode="json"),
        status_code=201,
    )


@router.post("/{record_id}/return", summary="Return a borrowed book")
def return_book(
    record_id: int,
    user: User = Depends(get_current_user_access),
    db: Session = Depends(get_db),
):
    log = get_logger("app.borrow")
    try:
        rec = BorrowService.return_book(session=db, actor=user, record_id=record_id)
    except ValueError as e:
        raise _borrow_http_exception(str(e)) from None

    r = get_redis()
    invalidate_books_cache(r, book_id=rec.book_id)
    invalidate_borrow_user_cache(r, rec.user_id)

    log.info(
        "borrow_returned",
        extra={
            "event": "borrow_return",
            "user_id": rec.user_id,
            "book_id": rec.book_id,
            "record_id": record_id,
        },
    )
    full = BorrowService.get_by_id(session=db, record_id=rec.id)
    assert full is not None
    data = borrow_record_to_dict(
        full,
        book_title=full.book.title if full.book else None,
        user_email=full.user.email if full.user else None,
    )
    return api_response(
        message="Returned",
        data=BorrowRecordPublic.model_validate(data).model_dump(mode="json"),
    )


@router.get("/me", summary="My borrowing history")
def list_my_borrows(
    user: User = Depends(get_current_user_access),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    r = get_redis()
    ttl = settings.borrows_cache_ttl_seconds
    key = borrow_user_history_key(user.id)

    cached = cache_get(r, key)
    if cached is not None:
        resp = api_response(message="OK", data={"items": cached})
        resp.headers["X-Cache"] = "HIT"
        return resp

    items = BorrowService.list_for_user(session=db, user_id=user.id)
    cache_set(r, key, items, ttl_seconds=ttl)
    resp = api_response(message="OK", data={"items": items})
    resp.headers["X-Cache"] = "MISS"
    return resp


@router.get("", summary="List borrow records (admin)")
def list_borrow_records(
    db: Session = Depends(get_db),
    _admin: User = Depends(admin_only),
    status_q: Annotated[str | None, Query(alias="status")] = None,
    user_id: Annotated[int | None, Query()] = None,
    book_id: Annotated[int | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
):
    st = _parse_status(status_q)
    skip = (page - 1) * page_size
    items, total = BorrowService.list_all(
        session=db,
        status=st,
        user_id=user_id,
        book_id=book_id,
        skip=skip,
        limit=page_size,
    )
    pagination = Pagination(page=page, page_size=page_size, total=total)
    return paginated_response(items=items, pagination=pagination, message="OK")


@router.get("/{record_id}", summary="Borrow record detail")
def get_borrow_record(
    record_id: int,
    user: User = Depends(get_current_user_access),
    db: Session = Depends(get_db),
):
    rec = BorrowService.get_by_id(session=db, record_id=record_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Borrow record not found")
    if user.role != UserRole.ADMIN and rec.user_id != user.id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    data = borrow_record_to_dict(
        rec,
        book_title=rec.book.title if rec.book else None,
        user_email=rec.user.email if rec.user else None,
    )
    return api_response(
        message="OK",
        data=BorrowRecordPublic.model_validate(data).model_dump(mode="json"),
    )
