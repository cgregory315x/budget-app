"""Add transaction categorization provenance.

Revision ID: 20260819_0004
Revises: 20260819_0003
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260819_0004"
down_revision: str | None = "20260819_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "categorization_source",
            sa.Enum("MANUAL", "MERCHANT_RULE", name="categorizationsource", native_enum=False),
            nullable=True,
        ),
    )
    op.add_column(
        "transactions",
        sa.Column("categorization_rule_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_transactions_categorization_rule",
        "transactions",
        "merchant_rules",
        ["categorization_rule_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        "UPDATE transactions SET categorization_source = 'MANUAL' "
        "WHERE category_id IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_transactions_categorization_rule", "transactions", type_="foreignkey"
    )
    op.drop_column("transactions", "categorization_rule_id")
    op.drop_column("transactions", "categorization_source")
