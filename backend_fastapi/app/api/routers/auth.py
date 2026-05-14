from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user_access, get_current_user_refresh
from app.core.db import get_db
from app.core.cookies import set_access_cookie_only, set_jwt_cookies, unset_jwt_cookies
from app.core.logging_config import get_logger
from app.core.redis_client import get_redis
from app.core.settings import get_settings
from app.models import User
from app.schemas.common import LoginRequest, RegisterRequest
from app.services.auth_service import AuthService
from app.utils.response import api_response

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


@router.post(
    "/register",
    status_code=201,
    summary="Register",
    description="Register a new user (role member). Does not log in automatically.",
)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    log = get_logger("app.auth")
    try:
        user = AuthService.register(
            session=db,
            full_name=body.full_name,
            email=body.email,
            password=body.password,
        )
    except ValueError as e:
        if str(e) == "EMAIL_EXISTS":
            log.warning(
                "register_email_exists",
                extra={"event": "auth_register", "email": body.email},
            )
            return api_response(message="Email already exists", status_code=409)
        return api_response(message="Invalid request", status_code=400)

    log.info(
        "user_registered",
        extra={
            "event": "auth_register",
            "user_id": user.id,
            "email": user.email,
        },
    )
    payload = {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role.value,
    }
    return api_response(message="Registered", data=payload, status_code=201)


@router.post("/login", summary="Login", description="Login and set access + refresh HttpOnly cookies.")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    settings = get_settings()
    log = get_logger("app.auth")
    try:
        user = AuthService.login(session=db, email=body.email, password=body.password)
    except ValueError as e:
        code = str(e)
        if code == "USER_DISABLED":
            log.warning(
                "login_user_disabled",
                extra={"event": "auth_login", "email": body.email},
            )
            return api_response(message="User disabled", status_code=403)
        log.warning(
            "login_failed",
            extra={"event": "auth_login", "email": body.email},
        )
        return api_response(message="Invalid credentials", status_code=401)

    log.info(
        "login_ok",
        extra={"event": "auth_login", "user_id": user.id, "email": user.email},
    )
    tokens = AuthService.make_tokens(settings=settings, user=user)
    resp = api_response(
        message="Logged in",
        data={
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
        },
    )
    set_jwt_cookies(
        resp,
        settings=settings,
        access_token=tokens.access,
        refresh_token=tokens.refresh,
    )
    return resp


@router.post("/logout", summary="Logout", description="Clear JWT cookies (client-side logout).")
def logout():
    settings = get_settings()
    resp = api_response(message="Logged out")
    unset_jwt_cookies(resp, settings=settings)
    return resp


@router.post(
    "/refresh",
    summary="Refresh access token",
    description="Requires refresh cookie; sets a new access cookie.",
)
def refresh(
    ctx: tuple[User, dict] = Depends(get_current_user_refresh),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    user, _claims = ctx
    u = db.get(User, user.id)
    if not u:
        return api_response(message="User not found", status_code=404)

    access = AuthService.refresh_access(settings=settings, user=u)
    resp = api_response(message="Refreshed")
    set_access_cookie_only(resp, settings=settings, access_token=access)
    return resp


@router.post(
    "/revoke",
    summary="Revoke refresh token",
    description="Revokes current refresh jti in Redis, bumps token_version, clears cookies.",
)
def revoke(
    ctx: tuple[User, dict] = Depends(get_current_user_refresh),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    user, claims = ctx
    u = db.get(User, user.id)
    if not u:
        return api_response(message="User not found", status_code=404)

    jti = claims.get("jti")
    if not jti:
        return api_response(message="Invalid token", status_code=401)

    ttl = int(settings.jwt_refresh_token_expires_seconds)
    get_redis().setex(f"jwt:revoked:{jti}", ttl, "1")
    AuthService.revoke_refresh_and_bump_version(session=db, user=u)

    resp = api_response(message="Revoked")
    unset_jwt_cookies(resp, settings=settings)
    return resp


@router.get("/me", summary="Current user", description="Profile from access token cookie.")
def me(user: User = Depends(get_current_user_access)):
    return api_response(
        message="OK",
        data={
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
        },
    )
