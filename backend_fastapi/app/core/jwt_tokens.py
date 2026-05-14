from __future__ import annotations

import time
import uuid

import jwt

JWT_ALGORITHM = "HS256"


def create_access_token(
    *,
    user_id: int,
    role: str,
    token_version: int,
    secret: str,
    expires_seconds: int,
) -> str:
    return _create_token(
        sub=str(user_id),
        token_type="access",
        role=role,
        tv=token_version,
        secret=secret,
        expires_seconds=expires_seconds,
    )


def create_refresh_token(
    *,
    user_id: int,
    role: str,
    token_version: int,
    secret: str,
    expires_seconds: int,
) -> str:
    return _create_token(
        sub=str(user_id),
        token_type="refresh",
        role=role,
        tv=token_version,
        secret=secret,
        expires_seconds=expires_seconds,
    )


def _create_token(
    *,
    sub: str,
    token_type: str,
    role: str,
    tv: int,
    secret: str,
    expires_seconds: int,
) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "role": role,
        "tv": tv,
        "type": token_type,
        "fresh": False,
        "iat": now,
        "nbf": now,
        "jti": str(uuid.uuid4()),
        "exp": now + int(expires_seconds),
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def decode_token(token: str, secret: str) -> dict:
    return jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
