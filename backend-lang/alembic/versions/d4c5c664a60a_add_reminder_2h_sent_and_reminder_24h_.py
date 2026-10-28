"""add password_hash, webhook_secret_encrypted, reminder_sent

Revision ID: d4c5c664a60a
Revises:
Create Date: 2026-10-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d4c5c664a60a"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_column_if_not_exists(table: str, column: str, col_type: str, default: str | None = None) -> None:
    """ADD COLUMN solo si no existe — idempotente."""
    not_null = " NOT NULL" if default is not None else ""
    default_clause = f" DEFAULT {default}" if default is not None else ""
    op.execute(
        f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {col_type}{default_clause}{not_null}"
    )


def upgrade() -> None:
    _add_column_if_not_exists("users", "password_hash", "TEXT")
    _add_column_if_not_exists("channels", "webhook_secret_encrypted", "TEXT")
    _add_column_if_not_exists("appointments", "reminder_sent", "BOOLEAN", "'false'")


def downgrade() -> None:
    op.drop_column("appointments", "reminder_sent")
    op.drop_column("channels", "webhook_secret_encrypted")
    op.drop_column("users", "password_hash")
