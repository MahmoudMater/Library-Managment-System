from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BookCreate(BaseModel):
    title: str = Field(..., max_length=255)
    author: str = Field(..., max_length=150)
    isbn: str = Field(..., max_length=30)
    publisher: str | None = Field(None, max_length=150)
    published_year: int | None = None
    description: str | None = None
    total_copies: int = Field(default=1, ge=0)
    available_copies: int = Field(default=1, ge=0)
    shelf_location: str | None = Field(None, max_length=50)

    @model_validator(mode="after")
    def copies_consistent(self) -> BookCreate:
        if self.available_copies > self.total_copies:
            raise ValueError("available_copies cannot exceed total_copies")
        return self


class BookUpdate(BaseModel):
    title: str | None = Field(None, max_length=255)
    author: str | None = Field(None, max_length=150)
    isbn: str | None = Field(None, max_length=30)
    publisher: str | None = Field(None, max_length=150)
    published_year: int | None = None
    description: str | None = None
    total_copies: int | None = Field(None, ge=0)
    available_copies: int | None = Field(None, ge=0)
    shelf_location: str | None = Field(None, max_length=50)


class BookPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    author: str
    isbn: str
    publisher: str | None
    published_year: int | None
    description: str | None
    total_copies: int
    available_copies: int
    shelf_location: str | None
    created_at: datetime | None
    updated_at: datetime | None
