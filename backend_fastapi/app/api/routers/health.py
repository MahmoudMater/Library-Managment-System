from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from redis import Redis
from sqlalchemy.orm import Session

from app.core.redis_client import get_redis
from app.core.db import get_db
from app.services.health_service import HealthService

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Health check",
    description="Verifies Postgres (`SELECT 1`) and Redis (`PING`).",
)
def get_health(
    db: Session = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
) -> JSONResponse:
    db_ok, db_err = HealthService.check_db(db)
    redis_ok, redis_err = HealthService.check_redis(redis_client)

    checks = {
        "database": {"ok": db_ok, **({"error": db_err} if db_err else {})},
        "redis": {"ok": redis_ok, **({"error": redis_err} if redis_err else {})},
    }
    ok = bool(db_ok and redis_ok)
    status = "ok" if ok else "degraded"
    code = 200 if ok else 503
    return JSONResponse(content={"status": status, "checks": checks}, status_code=code)
