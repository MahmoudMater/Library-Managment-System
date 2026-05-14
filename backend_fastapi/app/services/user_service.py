from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash

from app.models import User
from app.models.enums import UserRole
from app.schemas.user import UserCreateAdmin, UserUpdate


def user_to_public_dict(user: User) -> dict:
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        "max_borrow_limit": user.max_borrow_limit,
        "is_active": user.is_active,
    }


class UserService:
    @staticmethod
    def create_user(*, session: Session, body: UserCreateAdmin) -> User:
        email = body.email.strip().lower()
        if session.execute(select(User.id).where(User.email == email)).first():
            raise ValueError("EMAIL_EXISTS")

        try:
            role = UserRole(body.role.strip().lower())
        except ValueError as e:
            raise ValueError("INVALID_ROLE") from e

        user = User(
            full_name=body.full_name.strip(),
            email=email,
            hashed_password=generate_password_hash(body.password),
            role=role,
            is_active=bool(body.is_active),
            max_borrow_limit=int(body.max_borrow_limit),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    @staticmethod
    def list_users(
        *,
        session: Session,
        search: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict], int]:
        q = select(User)
        cnt = select(func.count()).select_from(User)
        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            cond = or_(func.lower(User.email).like(term), func.lower(User.full_name).like(term))
            q = q.where(cond)
            cnt = cnt.where(cond)

        total = int(session.scalar(cnt) or 0)
        rows = session.execute(q.order_by(User.id).offset(skip).limit(limit)).scalars().all()
        return [user_to_public_dict(u) for u in rows], total

    @staticmethod
    def update_user(*, session: Session, user: User, body: UserUpdate) -> User:
        data = body.model_dump(exclude_unset=True)
        if "role" in data and data["role"] is not None:
            try:
                user.role = UserRole(data["role"].strip().lower())
            except ValueError as e:
                raise ValueError("INVALID_ROLE") from e
        if "max_borrow_limit" in data and data["max_borrow_limit"] is not None:
            user.max_borrow_limit = int(data["max_borrow_limit"])
        if "is_active" in data and data["is_active"] is not None:
            user.is_active = bool(data["is_active"])
        session.commit()
        session.refresh(user)
        return user
