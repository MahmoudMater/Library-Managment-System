from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps.auth import admin_only, get_current_user_access
from app.core.db import get_db
from app.core.logging_config import get_logger
from app.core.redis_client import get_redis
from app.models import User
from app.schemas.user import UserCreateAdmin, UserProfile, UserUpdate
from app.services.user_service import UserService, user_to_public_dict
from app.utils.cache import cache_delete_pattern
from app.utils.response import Pagination, api_response, paginated_response

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", summary="Current user profile")
def users_me(user: User = Depends(get_current_user_access)):
    return api_response(
        message="OK",
        data=UserProfile.model_validate(user_to_public_dict(user)).model_dump(mode="json"),
    )


@router.get("", summary="List users (admin)")
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(admin_only),
    q: Annotated[str | None, Query(description="Search email or full name")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
):
    skip = (page - 1) * page_size
    items, total = UserService.list_users(session=db, search=q, skip=skip, limit=page_size)
    pagination = Pagination(page=page, page_size=page_size, total=total)
    return paginated_response(items=items, pagination=pagination, message="OK")


@router.post("", status_code=201, summary="Create user (admin)")
def create_user(
    body: UserCreateAdmin,
    db: Session = Depends(get_db),
    _admin: User = Depends(admin_only),
):
    log = get_logger("app.users")
    try:
        user = UserService.create_user(session=db, body=body)
    except ValueError as e:
        code = str(e)
        if code == "EMAIL_EXISTS":
            return api_response(message="Email already exists", status_code=409)
        if code == "INVALID_ROLE":
            raise HTTPException(status_code=422, detail="role must be admin or member") from None
        raise HTTPException(status_code=400, detail="Invalid request") from None

    cache_delete_pattern(get_redis(), "borrow:user:*")
    log.info("user_created", extra={"event": "users_create", "target_user_id": user.id})
    return api_response(
        message="Created",
        data=UserProfile.model_validate(user_to_public_dict(user)).model_dump(mode="json"),
        status_code=201,
    )


@router.patch("/{user_id}", summary="Update user (admin)")
@router.put("/{user_id}", summary="Update user (PUT, admin)")
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(admin_only),
):
    log = get_logger("app.users")
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    old_role = target.role.value
    try:
        UserService.update_user(session=db, user=target, body=body)
    except ValueError as e:
        if str(e) == "INVALID_ROLE":
            raise HTTPException(status_code=422, detail="role must be admin or member") from None
        raise HTTPException(status_code=400, detail=str(e)) from None

    # Invalidate all borrow:user:* caches if limits or activity might affect listings
    if body.max_borrow_limit is not None or body.is_active is not None or (
        body.role is not None and body.role != old_role
    ):
        cache_delete_pattern(get_redis(), "borrow:user:*")

    log.info(
        "user_updated",
        extra={"event": "users_update", "target_user_id": user_id},
    )
    return api_response(
        message="Updated",
        data=UserProfile.model_validate(user_to_public_dict(target)).model_dump(mode="json"),
    )
