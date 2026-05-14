from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .settings import get_settings

_settings = get_settings()

_sqlite = _settings.database_url.startswith("sqlite")


def _engine_kwargs() -> dict:
    if _sqlite:
        return {
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        }
    return {}


engine = create_engine(
    _settings.database_url,
    pool_pre_ping=not _sqlite,
    echo=_settings.sqlalchemy_echo,
    **_engine_kwargs(),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
