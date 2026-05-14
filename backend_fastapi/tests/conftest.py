from __future__ import annotations

import os

# Must be set before importing app modules that resolve Settings / engine.
os.environ.setdefault("SECRET_KEY", "test-secret-for-pytest")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-for-pytest")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("BOOTSTRAP_ADMIN", "true")
os.environ.setdefault("BOOTSTRAP_ADMIN_EMAIL", "admin@book.com")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "admin@password")

import fakeredis  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402
from app.models import Base  # noqa: E402
from app.core import db as db_mod  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_database() -> None:
    Base.metadata.drop_all(bind=db_mod.engine)
    Base.metadata.create_all(bind=db_mod.engine)
    yield


@pytest.fixture
def redis_client() -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture(autouse=True)
def _patch_redis(redis_client: fakeredis.FakeRedis, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.core.redis_client as rc

    rc.get_redis.cache_clear()
    monkeypatch.setattr(rc, "get_redis", lambda: redis_client)


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app):
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture
def admin_client(app) -> TestClient:
    """Separate cookie jar from member_client — do not share one TestClient for both roles."""
    with TestClient(app, raise_server_exceptions=True) as c:
        r = c.post(
            "/auth/login",
            json={"email": "admin@book.com", "password": "admin@password"},
        )
        assert r.status_code == 200, r.json()
        assert r.json().get("success") is True
        yield c


@pytest.fixture
def member_client(app) -> TestClient:
    with TestClient(app, raise_server_exceptions=True) as c:
        c.post(
            "/auth/register",
            json={
                "full_name": "Test Member",
                "email": "member@test.com",
                "password": "memberpassword",
            },
        )
        r = c.post(
            "/auth/login",
            json={"email": "member@test.com", "password": "memberpassword"},
        )
        assert r.status_code == 200, r.json()
        yield c
