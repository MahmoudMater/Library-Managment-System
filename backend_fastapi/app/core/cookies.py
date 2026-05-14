from __future__ import annotations

from starlette.responses import Response

from .settings import Settings


def set_jwt_cookies(
    response: Response,
    *,
    settings: Settings,
    access_token: str,
    refresh_token: str,
) -> None:
    response.set_cookie(
        key=settings.jwt_access_cookie_name,
        value=access_token,
        max_age=settings.jwt_access_token_expires_seconds,
        httponly=True,
        secure=settings.jwt_cookie_secure,
        samesite=settings.jwt_cookie_samesite,
        path="/",
    )
    response.set_cookie(
        key=settings.jwt_refresh_cookie_name,
        value=refresh_token,
        max_age=settings.jwt_refresh_token_expires_seconds,
        httponly=True,
        secure=settings.jwt_cookie_secure,
        samesite=settings.jwt_cookie_samesite,
        path="/",
    )


def set_access_cookie_only(
    response: Response,
    *,
    settings: Settings,
    access_token: str,
) -> None:
    response.set_cookie(
        key=settings.jwt_access_cookie_name,
        value=access_token,
        max_age=settings.jwt_access_token_expires_seconds,
        httponly=True,
        secure=settings.jwt_cookie_secure,
        samesite=settings.jwt_cookie_samesite,
        path="/",
    )


def unset_jwt_cookies(response: Response, *, settings: Settings) -> None:
    common = {
        "path": "/",
        "secure": settings.jwt_cookie_secure,
        "httponly": True,
        "samesite": settings.jwt_cookie_samesite,
    }
    response.delete_cookie(settings.jwt_access_cookie_name, **common)
    response.delete_cookie(settings.jwt_refresh_cookie_name, **common)
