from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="development", alias="APP_ENV")

    secret_key: str = Field(default="dev-secret-change-me", alias="SECRET_KEY")
    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # Comma-separated string — not `list[str]` so dotenv does not go through JSON decode
    cors_origins_str: str = Field(
        default="http://localhost:3000",
        alias="CORS_ORIGINS",
    )

    jwt_secret_key: str | None = Field(default=None, alias="JWT_SECRET_KEY")
    jwt_access_token_expires_seconds: int = Field(default=900, alias="JWT_ACCESS_TOKEN_EXPIRES_SECONDS")
    jwt_refresh_token_expires_seconds: int = Field(
        default=1_209_600,
        alias="JWT_REFRESH_TOKEN_EXPIRES_SECONDS",
    )
    jwt_cookie_secure: bool = Field(default=False, alias="JWT_COOKIE_SECURE")
    jwt_cookie_samesite: Literal["lax", "strict", "none"] = Field(
        default="lax",
        alias="JWT_COOKIE_SAMESITE",
    )

    @field_validator("jwt_cookie_samesite", mode="before")
    @classmethod
    def normalize_samesite(cls, v: object) -> str:
        if v is None:
            return "lax"
        s = str(v).strip().lower()
        if s not in {"lax", "strict", "none"}:
            raise ValueError("JWT_COOKIE_SAMESITE must be Lax, Strict, or None")
        return s
    jwt_cookie_csrf_protect: bool = Field(default=False, alias="JWT_COOKIE_CSRF_PROTECT")

    # Match Flask-JWT-Extended defaults
    jwt_access_cookie_name: str = Field(default="access_token_cookie", alias="JWT_ACCESS_COOKIE_NAME")
    jwt_refresh_cookie_name: str = Field(default="refresh_token_cookie", alias="JWT_REFRESH_COOKIE_NAME")

    bootstrap_admin: bool = Field(default=True, alias="BOOTSTRAP_ADMIN")
    bootstrap_admin_email: str = Field(default="admin@book.com", alias="BOOTSTRAP_ADMIN_EMAIL")
    bootstrap_admin_password: str = Field(default="admin@password", alias="BOOTSTRAP_ADMIN_PASSWORD")

    api_title: str = Field(default="Library Backend API", alias="API_TITLE")
    api_version: str = Field(default="v1", alias="API_VERSION")

    books_cache_ttl_seconds: int = Field(default=120, alias="BOOKS_CACHE_TTL_SECONDS")
    borrows_cache_ttl_seconds: int = Field(default=60, alias="BORROWS_CACHE_TTL_SECONDS")
    sqlalchemy_echo: bool = Field(default=False, alias="SQLALCHEMY_ECHO")

    @computed_field
    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins_str.split(",") if o.strip()]

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() in {"development", "dev"}

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    def resolved_jwt_secret(self) -> str:
        return self.jwt_secret_key or self.secret_key


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
