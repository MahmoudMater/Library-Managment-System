from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Book
from app.schemas.book import BookCreate, BookUpdate


def book_to_dict(book: Book) -> dict:
    return {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "isbn": book.isbn,
        "publisher": book.publisher,
        "published_year": book.published_year,
        "description": book.description,
        "total_copies": book.total_copies,
        "available_copies": book.available_copies,
        "shelf_location": book.shelf_location,
        "created_at": book.created_at.isoformat() if book.created_at else None,
        "updated_at": book.updated_at.isoformat() if book.updated_at else None,
    }


class BookService:
    @staticmethod
    def list_books(*, session: Session) -> list[dict]:
        rows = session.execute(select(Book).order_by(Book.id)).scalars().all()
        return [book_to_dict(b) for b in rows]

    @staticmethod
    def get_by_id(*, session: Session, book_id: int) -> Book | None:
        return session.get(Book, book_id)

    @staticmethod
    def create(*, session: Session, body: BookCreate) -> Book:
        book = Book(
            title=body.title.strip(),
            author=body.author.strip(),
            isbn=body.isbn.strip(),
            publisher=body.publisher.strip() if body.publisher else None,
            published_year=body.published_year,
            description=body.description,
            total_copies=body.total_copies,
            available_copies=body.available_copies,
            shelf_location=body.shelf_location.strip() if body.shelf_location else None,
        )
        session.add(book)
        session.commit()
        session.refresh(book)
        return book

    @staticmethod
    def update(*, session: Session, book: Book, body: BookUpdate) -> Book:
        data = body.model_dump(exclude_unset=True)
        for key, value in data.items():
            if value is None:
                setattr(book, key, None)
            elif isinstance(value, str):
                setattr(book, key, value.strip())
            else:
                setattr(book, key, value)
        session.commit()
        session.refresh(book)
        return book

    @staticmethod
    def delete(*, session: Session, book: Book) -> None:
        session.delete(book)
        session.commit()
