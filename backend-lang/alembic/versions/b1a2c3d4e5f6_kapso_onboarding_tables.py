"""add kapso_customers table and kapso columns to channels

Revision ID: b1a2c3d4e5f6
Revises: d4c5c664a60a
Create Date: 2026-10-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b1a2c3d4e5f6"
down_revision: Union[str, None] = "d4c5c664a60a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tabla kapso_customers — enlaza workspace con customer de Kapso
    op.execute("""
        CREATE TABLE IF NOT EXISTS kapso_customers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL UNIQUE REFERENCES workspaces(id) ON DELETE CASCADE,
            kapso_customer_id TEXT NOT NULL,
            setup_link_id TEXT,
            setup_link_url TEXT,
            setup_link_expires_at TIMESTAMPTZ,
            setup_status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # Columnas faltantes en channels
    op.execute("ALTER TABLE channels ADD COLUMN IF NOT EXISTS connection_type TEXT DEFAULT 'coexistence'")
    op.execute("ALTER TABLE channels ADD COLUMN IF NOT EXISTS webhook_token TEXT")
    op.execute("ALTER TABLE channels ADD COLUMN IF NOT EXISTS kapso_webhook_id TEXT")


def downgrade() -> None:
    op.drop_column("channels", "kapso_webhook_id")
    op.drop_column("channels", "webhook_token")
    op.drop_column("channels", "connection_type")
    op.execute("DROP TABLE IF EXISTS kapso_customers")
