from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class HealthService:
    @staticmethod
    def check_db(session: Session) -> tuple[bool, str | None]:
        try:
            session.execute(text("SELECT 1"))
            return True, None
        except SQLAlchemyError as e:
            return False, e.__class__.__name__

    @staticmethod
    def check_redis(redis_client) -> tuple[bool, str | None]:
        try:
            pong = redis_client.ping()
            return bool(pong), None
        except Exception as e:
            return False, str(e)
