"""Indexes for borrow_records.

Revision ID: 002_borrow_indexes
Revises: 001_initial
Create Date: 2026-04-27

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_borrow_indexes"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_borrow_records_user_id", "borrow_records", ["user_id"], unique=False)
    op.create_index("ix_borrow_records_book_id", "borrow_records", ["book_id"], unique=False)
    bind = op.get_bind()
    dialect = bind.dialect.name if bind else ""
    # One active borrow per user+book at DB level (aligned with application checks).
    if dialect == "postgresql":
        op.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_borrow_active_user_book
            ON borrow_records (user_id, book_id)
            WHERE status = 'BORROWED';
            """
        )
    elif dialect == "sqlite":
        op.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_borrow_active_user_book
            ON borrow_records (user_id, book_id)
            WHERE status = 'BORROWED';
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name if bind else ""
    if dialect in ("postgresql", "sqlite"):
        op.execute("DROP INDEX IF EXISTS ux_borrow_active_user_book")
    op.drop_index("ix_borrow_records_book_id", table_name="borrow_records")
    op.drop_index("ix_borrow_records_user_id", table_name="borrow_records")
