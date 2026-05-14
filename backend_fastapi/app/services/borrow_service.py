from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import Book, BorrowRecord, User
from app.models.enums import BorrowStatus, UserRole


DEFAULT_BORROW_DAYS = 14
MAX_DUE_DATE_DAYS_AHEAD = 90


def borrow_record_to_dict(
    rec: BorrowRecord,
    *,
    book_title: str | None = None,
    user_email: str | None = None,
) -> dict:
    st = rec.status.value if hasattr(rec.status, "value") else str(rec.status)
    dd = rec.due_date.isoformat() if hasattr(rec.due_date, "isoformat") else rec.due_date
    return {
        "id": rec.id,
        "user_id": rec.user_id,
        "book_id": rec.book_id,
        "book_title": book_title or (rec.book.title if rec.book else None),
        "user_email": user_email or (rec.user.email if rec.user else None),
        "borrowed_at": rec.borrowed_at.isoformat() if rec.borrowed_at else None,
        "due_date": dd,
        "returned_at": rec.returned_at.isoformat() if rec.returned_at else None,
        "status": st,
        "notes": rec.notes,
    }


class BorrowService:
    @staticmethod
    def borrow(
        *,
        session: Session,
        user: User,
        book_id: int,
        due_date: date | None,
    ) -> BorrowRecord:
        u = session.get(User, user.id)
        if not u:
            raise ValueError("USER_NOT_FOUND")

        book = session.execute(
            select(Book).where(Book.id == book_id).with_for_update(),
        ).scalar_one_or_none()
        if not book:
            raise ValueError("BOOK_NOT_FOUND")
        if book.available_copies <= 0:
            raise ValueError("BOOK_UNAVAILABLE")

        active_count = session.scalar(
            select(func.count())
            .select_from(BorrowRecord)
            .where(
                BorrowRecord.user_id == u.id,
                BorrowRecord.status == BorrowStatus.BORROWED,
            ),
        )
        if (active_count or 0) >= int(u.max_borrow_limit):
            raise ValueError("LIMIT_REACHED")

        existing = session.execute(
            select(BorrowRecord.id).where(
                BorrowRecord.user_id == u.id,
                BorrowRecord.book_id == book_id,
                BorrowRecord.status == BorrowStatus.BORROWED,
            ),
        ).first()
        if existing:
            raise ValueError("ALREADY_BORROWED")

        today = date.today()
        if due_date is None:
            resolved_due = today + timedelta(days=DEFAULT_BORROW_DAYS)
        else:
            resolved_due = due_date

        borrowed_at = datetime.utcnow()
        record = BorrowRecord(
            user_id=u.id,
            book_id=book.id,
            borrowed_at=borrowed_at,
            due_date=resolved_due,
            returned_at=None,
            status=BorrowStatus.BORROWED,
            notes=None,
        )
        book.available_copies = int(book.available_copies) - 1
        session.add(record)
        session.commit()
        session.refresh(record)
        session.refresh(book)
        return record

    @staticmethod
    def return_book(*, session: Session, actor: User, record_id: int) -> BorrowRecord:
        rec = session.execute(
            select(BorrowRecord)
            .where(BorrowRecord.id == record_id)
            .with_for_update(),
        ).scalar_one_or_none()
        if not rec:
            raise ValueError("RECORD_NOT_FOUND")

        if actor.role != UserRole.ADMIN and rec.user_id != actor.id:
            raise ValueError("NOT_OWNER")

        if rec.status != BorrowStatus.BORROWED:
            raise ValueError("ALREADY_RETURNED")

        book = session.execute(
            select(Book).where(Book.id == rec.book_id).with_for_update(),
        ).scalar_one_or_none()
        if not book:
            raise ValueError("BOOK_NOT_FOUND")

        now = datetime.utcnow()
        rec.returned_at = now
        rec.status = BorrowStatus.RETURNED

        book.available_copies = min(
            int(book.total_copies),
            int(book.available_copies) + 1,
        )
        session.commit()
        session.refresh(rec)
        return rec

    @staticmethod
    def list_for_user(*, session: Session, user_id: int) -> list[dict]:
        rows = (
            session.execute(
                select(BorrowRecord)
                .where(BorrowRecord.user_id == user_id)
                .options(joinedload(BorrowRecord.book))
                .order_by(BorrowRecord.borrowed_at.desc()),
            )
            .scalars()
            .all()
        )
        return [borrow_record_to_dict(r, book_title=r.book.title if r.book else None) for r in rows]

    @staticmethod
    def list_all(
        *,
        session: Session,
        status: BorrowStatus | None = None,
        user_id: int | None = None,
        book_id: int | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict], int]:
        cnt = select(func.count()).select_from(BorrowRecord)
        q = select(BorrowRecord).options(
            joinedload(BorrowRecord.book),
            joinedload(BorrowRecord.user),
        )
        if status is not None:
            cnt = cnt.where(BorrowRecord.status == status)
            q = q.where(BorrowRecord.status == status)
        if user_id is not None:
            cnt = cnt.where(BorrowRecord.user_id == user_id)
            q = q.where(BorrowRecord.user_id == user_id)
        if book_id is not None:
            cnt = cnt.where(BorrowRecord.book_id == book_id)
            q = q.where(BorrowRecord.book_id == book_id)

        total = int(session.scalar(cnt) or 0)

        rows = (
            session.execute(
                q.order_by(BorrowRecord.borrowed_at.desc()).offset(skip).limit(limit),
            )
            .scalars()
            .unique()
            .all()
        )
        items = [
            borrow_record_to_dict(
                r,
                book_title=r.book.title if r.book else None,
                user_email=r.user.email if r.user else None,
            )
            for r in rows
        ]
        return items, int(total)

    @staticmethod
    def get_by_id(*, session: Session, record_id: int) -> BorrowRecord | None:
        return (
            session.scalars(
                select(BorrowRecord)
                .where(BorrowRecord.id == record_id)
                .options(joinedload(BorrowRecord.book), joinedload(BorrowRecord.user)),
            )
            .unique()
            .first()
        )
