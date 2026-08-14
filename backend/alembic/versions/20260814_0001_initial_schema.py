"""Create the initial application schema.

Revision ID: 20260814_0001
Revises:
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260814_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> tuple[sa.Column[object], sa.Column[object]]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("institution", sa.String(length=120), nullable=False),
        sa.Column(
            "account_type",
            sa.Enum("CHECKING", "CREDIT_CARD", "LOAN", name="accounttype", native_enum=False),
            nullable=False,
        ),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("current_balance", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("archived", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("EXPENSE", "INCOME", "TRANSFER", name="categorykind", native_enum=False),
            nullable=False,
        ),
        sa.Column("color", sa.String(length=7), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_categories_name_lower", "categories", [sa.text("lower(name)")], unique=True)
    op.create_table(
        "monthly_income",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=160), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("amount >= 0", name="ck_income_nonnegative"),
        sa.CheckConstraint("EXTRACT(DAY FROM month) = 1", name="ck_income_month_first_day"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_monthly_income_month", "monthly_income", ["month"], unique=False)
    op.create_table(
        "loan_terms",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("principal", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("annual_rate_basis_points", sa.Integer(), nullable=False),
        sa.Column("minimum_payment", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("term_months", sa.Integer(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("annual_rate_basis_points >= 0", name="ck_loan_rate_nonnegative"),
        sa.CheckConstraint("minimum_payment >= 0", name="ck_loan_payment_nonnegative"),
        sa.CheckConstraint("principal >= 0", name="ck_loan_principal_nonnegative"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id"),
    )
    op.create_table(
        "statement_imports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("adapter", sa.String(length=80), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("statement_start", sa.Date(), nullable=True),
        sa.Column("statement_end", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "UPLOADED",
                "PARSED",
                "NEEDS_REVIEW",
                "CONFIRMED",
                "FAILED",
                "CANCELLED",
                "EXPIRED",
                name="importstatus",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("warnings", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_sha256"),
    )
    op.create_table(
        "loan_balance_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("loan_terms_id", sa.Uuid(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("balance", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("balance >= 0", name="ck_loan_balance_nonnegative"),
        sa.ForeignKeyConstraint(["loan_terms_id"], ["loan_terms.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("loan_terms_id", "as_of_date", name="uq_loan_snapshot_date"),
    )
    op.create_table(
        "merchant_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pattern", sa.String(length=200), nullable=False),
        sa.Column(
            "match_type",
            sa.Enum("EXACT", "CONTAINS", "REGEX", name="rulematchtype", native_enum=False),
            nullable=False,
        ),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pattern", "match_type", name="uq_merchant_rule"),
    )
    op.create_table(
        "monthly_budgets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("limit_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("EXTRACT(DAY FROM month) = 1", name="ck_budget_month_first_day"),
        sa.CheckConstraint("limit_amount >= 0", name="ck_budget_limit_nonnegative"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("month", "category_id", name="uq_budget_month_category"),
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("statement_import_id", sa.Uuid(), nullable=True),
        sa.Column("posted_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("merchant_normalized", sa.String(length=200), nullable=True),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("excluded_from_budget", sa.Boolean(), nullable=False),
        sa.Column("categorization_confidence", sa.Numeric(precision=4, scale=3), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["statement_import_id"], ["statement_imports.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "fingerprint", name="uq_transaction_fingerprint"),
    )
    op.create_index(
        "ix_transactions_account_posted",
        "transactions",
        ["account_id", "posted_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_account_posted", table_name="transactions")
    op.drop_table("transactions")
    op.drop_table("monthly_budgets")
    op.drop_table("merchant_rules")
    op.drop_table("loan_balance_snapshots")
    op.drop_table("statement_imports")
    op.drop_table("loan_terms")
    op.drop_index("ix_monthly_income_month", table_name="monthly_income")
    op.drop_table("monthly_income")
    op.drop_index("uq_categories_name_lower", table_name="categories")
    op.drop_table("categories")
    op.drop_table("accounts")
