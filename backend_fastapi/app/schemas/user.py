from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    role: str
    max_borrow_limit: int = 3
    is_active: bool = True


class UserUpdate(BaseModel):
    """Admin updates to a user account."""

    role: str | None = Field(None, description="admin or member")
    max_borrow_limit: int | None = Field(None, ge=0, le=50)
    is_active: bool | None = None


class UserCreateAdmin(BaseModel):
    """Admin creates a user with an explicit role."""

    full_name: str = Field(..., max_length=150)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=256)
    role: str = Field(..., description="admin or member")
    max_borrow_limit: int = Field(default=3, ge=0, le=50)
    is_active: bool = True
