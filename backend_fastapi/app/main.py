from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import select

from app.api.routers import auth_router, books_router, borrow_router, health_router, users_router
from app.core.db import SessionLocal, engine
from app.core.logging_config import get_logger, setup_logging
from app.core.settings import get_settings
from app.models import Base, User
from app.models.enums import UserRole
from app.utils.response import api_response
from werkzeug.security import generate_password_hash

logger = get_logger(__name__)


def _bootstrap_admin() -> None:
    settings = get_settings()
    if not (settings.bootstrap_admin and settings.is_development):
        return

    Base.metadata.create_all(bind=engine)

    email = settings.bootstrap_admin_email.strip().lower()
    with SessionLocal() as session:
        exists = session.execute(select(User.id).where(User.email == email)).first()
        if not exists:
            admin = User(
                full_name="Admin",
                email=email,
                hashed_password=generate_password_hash(settings.bootstrap_admin_password),
                role=UserRole.ADMIN,
                is_active=True,
            )
            session.add(admin)
            session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(logging.DEBUG if get_settings().is_development else logging.INFO)
    _bootstrap_admin()
    yield


def _normalize_http_exception_detail(detail: object) -> tuple[str, object | None]:
    if isinstance(detail, str):
        return detail, None
    return "Request failed", detail


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            log = get_logger("app.request")
            log.exception(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duration_ms, 2),
                    "event": "http_request",
                },
            )
            raise
        duration_ms = (time.perf_counter() - start) * 1000
        status = response.status_code
        log = get_logger("app.request")
        extra = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": status,
            "duration_ms": round(duration_ms, 2),
            "event": "http_request",
        }
        if status >= 500:
            log.error("request_complete", extra=extra)
        elif status >= 400:
            log.warning("request_complete", extra=extra)
        else:
            log.info("request_complete", extra=extra)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_request: Request, exc: StarletteHTTPException):
        msg, err = _normalize_http_exception_detail(exc.detail)
        log = get_logger("app.errors")
        log.warning(
            "http_exception",
            extra={
                "status_code": exc.status_code,
                "detail": msg,
                "event": "http_exception",
            },
        )
        return api_response(message=msg, status_code=exc.status_code, error=err)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_request: Request, exc: RequestValidationError):
        log = get_logger("app.errors")
        log.warning(
            "validation_error",
            extra={"event": "validation_error", "errors": exc.errors()},
        )
        return api_response(
            message="Validation error",
            status_code=422,
            error=exc.errors(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception):
        logger.exception("unhandled_exception", exc_info=exc)
        return api_response(
            message="Internal server error",
            status_code=500,
            error=None,
        )

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(books_router)
    app.include_router(borrow_router)
    app.include_router(users_router)

    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

    return app


app = create_app()
