from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ApiResponseEnvelope(BaseModel):
    model_config = ConfigDict(extra="allow")

    success: bool
    message: str | None = None
    data: Any = None
    error: Any = None
    meta: dict[str, Any] | None = None


class RegisterRequest(BaseModel):
    full_name: str = Field(..., description="User full name")
    email: EmailStr = Field(..., description="Unique email")
    password: str = Field(..., description="Plain password")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: int
    full_name: str
    email: str
    role: str = Field(..., description="admin or member")
