from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request
from redis import Redis
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.logging_config import get_logger
from app.core.jwt_tokens import decode_token
from app.core.redis_client import get_redis
from app.core.settings import get_settings
from app.models import User
from app.models.enums import UserRole


def _is_revoked(redis_client: Redis, jti: str) -> bool:
    return redis_client.get(f"jwt:revoked:{jti}") is not None


def get_current_user_access(request: Request, db: Session = Depends(get_db)) -> User:
    """Validate access JWT from cookie (revocation + token_version)."""
    settings = get_settings()
    token = request.cookies.get(settings.jwt_access_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        claims = decode_token(token, settings.resolved_jwt_secret())
    except Exception:
        get_logger("app.auth").warning(
            "access_token_invalid",
            extra={"event": "auth_token", "phase": "decode"},
        )
        raise HTTPException(status_code=401, detail="Not authenticated") from None

    if claims.get("type") != "access":
        raise HTTPException(status_code=401, detail="Not authenticated")

    jti = claims.get("jti")
    if not jti:
        raise HTTPException(status_code=401, detail="Not authenticated")

    redis_client = get_redis()
    if _is_revoked(redis_client, jti):
        raise HTTPException(status_code=401, detail="Access token revoked")

    user_id = int(claims["sub"])
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if int(claims.get("tv", -1)) != int(user.token_version):
        raise HTTPException(status_code=401, detail="Token expired")

    return user


def get_current_user_refresh(request: Request, db: Session = Depends(get_db)) -> tuple[User, dict]:
    """Validate refresh JWT from cookie."""
    settings = get_settings()
    token = request.cookies.get(settings.jwt_refresh_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        claims = decode_token(token, settings.resolved_jwt_secret())
    except Exception:
        get_logger("app.auth").warning(
            "refresh_token_invalid",
            extra={"event": "auth_token", "phase": "decode"},
        )
        raise HTTPException(status_code=401, detail="Not authenticated") from None

    if claims.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not authenticated")

    jti = claims.get("jti")
    if not jti:
        raise HTTPException(status_code=401, detail="Not authenticated")

    redis_client = get_redis()
    if _is_revoked(redis_client, jti):
        raise HTTPException(status_code=401, detail="Refresh token revoked")

    user_id = int(claims["sub"])
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if int(claims.get("tv", -1)) != int(user.token_version):
        raise HTTPException(status_code=401, detail="Token expired")

    return user, claims


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    allowed = {r.value for r in roles}

    def _dep(user: User = Depends(get_current_user_access)) -> User:
        if user.role.value not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return _dep


admin_only = require_roles(UserRole.ADMIN)
