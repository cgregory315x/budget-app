"""Add normalized merchant rule matching fields and indexes.

Revision ID: 20260819_0003
Revises: 20260814_0002
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260819_0003"
down_revision: str | None = "20260814_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("merchant_rules", sa.Column("pattern_normalized", sa.String(200)))
    # Existing installs only have the dormant Milestone 0 scaffold. This conservative
    # SQL backfill makes those rows usable; application writes use the fuller normalizer.
    op.execute(
        "UPDATE merchant_rules SET pattern_normalized = CASE WHEN match_type = 'REGEX' "
        "THEN upper(trim(regexp_replace(pattern, '\\s+', ' ', 'g'))) ELSE "
        "trim(regexp_replace(regexp_replace(upper(pattern), '[^A-Z0-9 ]+', ' ', 'g'), "
        "'\\s+', ' ', 'g')) END"
    )
    op.alter_column("merchant_rules", "pattern_normalized", nullable=False)
    op.drop_constraint("uq_merchant_rule", "merchant_rules", type_="unique")
    op.create_unique_constraint(
        "uq_merchant_rule", "merchant_rules", ["pattern_normalized", "match_type"]
    )
    op.create_check_constraint(
        "ck_merchant_rule_priority_nonnegative", "merchant_rules", "priority >= 0"
    )
    op.create_index(
        "ix_merchant_rules_enabled_priority",
        "merchant_rules",
        ["enabled", "priority"],
    )


def downgrade() -> None:
    op.drop_index("ix_merchant_rules_enabled_priority", table_name="merchant_rules")
    op.drop_constraint(
        "ck_merchant_rule_priority_nonnegative", "merchant_rules", type_="check"
    )
    op.drop_constraint("uq_merchant_rule", "merchant_rules", type_="unique")
    op.create_unique_constraint("uq_merchant_rule", "merchant_rules", ["pattern", "match_type"])
    op.drop_column("merchant_rules", "pattern_normalized")
