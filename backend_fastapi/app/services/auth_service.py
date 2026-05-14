from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash

from app.core.jwt_tokens import create_access_token, create_refresh_token
from app.core.settings import Settings, get_settings
from app.models import User
from app.models.enums import UserRole


@dataclass(frozen=True)
class TokenPair:
    access: str
    refresh: str


class AuthService:
    @staticmethod
    def register(*, session: Session, full_name: str, email: str, password: str) -> User:
        email = email.strip().lower()
        if session.execute(select(User.id).where(User.email == email)).first():
            raise ValueError("EMAIL_EXISTS")

        user = User(
            full_name=full_name.strip(),
            email=email,
            hashed_password=generate_password_hash(password),
            role=UserRole.MEMBER,
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    @staticmethod
    def login(*, session: Session, email: str, password: str) -> User:
        email = email.strip().lower()
        user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if not user or not check_password_hash(user.hashed_password, password):
            raise ValueError("INVALID_CREDENTIALS")
        if not user.is_active:
            raise ValueError("USER_DISABLED")
        return user

    @staticmethod
    def make_tokens(*, settings: Settings | None = None, user: User) -> TokenPair:
        s = settings or get_settings()
        secret = s.resolved_jwt_secret()
        claims = {"role": user.role.value, "tv": user.token_version}
        access = create_access_token(
            user_id=user.id,
            role=claims["role"],
            token_version=int(claims["tv"]),
            secret=secret,
            expires_seconds=s.jwt_access_token_expires_seconds,
        )
        refresh = create_refresh_token(
            user_id=user.id,
            role=claims["role"],
            token_version=int(claims["tv"]),
            secret=secret,
            expires_seconds=s.jwt_refresh_token_expires_seconds,
        )
        return TokenPair(access=access, refresh=refresh)

    @staticmethod
    def refresh_access(*, settings: Settings | None = None, user: User) -> str:
        s = settings or get_settings()
        secret = s.resolved_jwt_secret()
        return create_access_token(
            user_id=user.id,
            role=user.role.value,
            token_version=int(user.token_version),
            secret=secret,
            expires_seconds=s.jwt_access_token_expires_seconds,
        )

    @staticmethod
    def revoke_refresh_and_bump_version(*, session: Session, user: User) -> None:
        user.token_version = int(user.token_version) + 1
        session.commit()
