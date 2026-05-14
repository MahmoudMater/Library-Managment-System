from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BorrowCreate(BaseModel):
    """Request body for borrowing a book."""

    book_id: int = Field(..., ge=1)
    due_date: date | None = Field(
        None,
        description="If omitted, defaults to today + 14 days. Must be within 90 days ahead.",
    )

    @model_validator(mode="after")
    def validate_due_window(self) -> BorrowCreate:
        if self.due_date is None:
            return self
        today = date.today()
        if self.due_date < today:
            raise ValueError("due_date cannot be in the past")
        if self.due_date > date.fromordinal(today.toordinal() + 90):
            raise ValueError("due_date cannot be more than 90 days ahead")
        return self


class BorrowRecordPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    book_id: int
    book_title: str | None = None
    user_email: str | None = None
    borrowed_at: datetime
    due_date: date
    returned_at: datetime | None
    status: Literal["borrowed", "returned", "overdue"]
    notes: str | None
