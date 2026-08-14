"""Add the stable transaction occurrence index.

Revision ID: 20260814_0002
Revises: 20260814_0001
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260814_0002"
down_revision: str | None = "20260814_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("occurrence_index", sa.Integer(), server_default="1", nullable=False),
    )
    op.alter_column("transactions", "occurrence_index", server_default=None)


def downgrade() -> None:
    op.drop_column("transactions", "occurrence_index")
