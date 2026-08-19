from __future__ import annotations

import enum
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    extract,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class AccountType(enum.StrEnum):
    CHECKING = "checking"
    CREDIT_CARD = "credit_card"
    LOAN = "loan"


class CategoryKind(enum.StrEnum):
    EXPENSE = "expense"
    INCOME = "income"
    TRANSFER = "transfer"


class ImportStatus(enum.StrEnum):
    UPLOADED = "uploaded"
    PARSED = "parsed"
    NEEDS_REVIEW = "needs_review"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class RuleMatchType(enum.StrEnum):
    EXACT = "exact"
    CONTAINS = "contains"
    REGEX = "regex"


class Account(TimestampMixin, Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    institution: Mapped[str] = mapped_column(String(120))
    account_type: Mapped[AccountType] = mapped_column(Enum(AccountType, native_enum=False))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    current_balance: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    archived: Mapped[bool] = mapped_column(Boolean, default=False)

    transactions: Mapped[list[Transaction]] = relationship(back_populates="account")
    imports: Mapped[list[StatementImport]] = relationship(back_populates="account")
    loan_terms: Mapped[LoanTerms | None] = relationship(back_populates="account")


class Category(TimestampMixin, Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[CategoryKind] = mapped_column(Enum(CategoryKind, native_enum=False))
    color: Mapped[str] = mapped_column(String(7), default="#667085")
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (Index("uq_categories_name_lower", func.lower(name), unique=True),)

    transactions: Mapped[list[Transaction]] = relationship(back_populates="category")
    budgets: Mapped[list[MonthlyBudget]] = relationship(back_populates="category")
    merchant_rules: Mapped[list[MerchantRule]] = relationship(back_populates="category")


class StatementImport(TimestampMixin, Base):
    __tablename__ = "statement_imports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    adapter: Mapped[str] = mapped_column(String(80))
    file_sha256: Mapped[str] = mapped_column(String(64), unique=True)
    statement_start: Mapped[date | None] = mapped_column(Date)
    statement_end: Mapped[date | None] = mapped_column(Date)
    status: Mapped[ImportStatus] = mapped_column(Enum(ImportStatus, native_enum=False))
    warnings: Mapped[str | None] = mapped_column(Text)

    account: Mapped[Account] = relationship(back_populates="imports")
    transactions: Mapped[list[Transaction]] = relationship(back_populates="statement_import")


class Transaction(TimestampMixin, Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_account_posted", "account_id", "posted_date"),
        UniqueConstraint("account_id", "fingerprint", name="uq_transaction_fingerprint"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id"))
    statement_import_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("statement_imports.id")
    )
    posted_date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(500))
    merchant_normalized: Mapped[str | None] = mapped_column(String(200))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    fingerprint: Mapped[str] = mapped_column(String(64))
    occurrence_index: Mapped[int] = mapped_column(Integer, default=1)
    excluded_from_budget: Mapped[bool] = mapped_column(Boolean, default=False)
    categorization_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))

    account: Mapped[Account] = relationship(back_populates="transactions")
    category: Mapped[Category | None] = relationship(back_populates="transactions")
    statement_import: Mapped[StatementImport | None] = relationship(
        back_populates="transactions"
    )


class MerchantRule(TimestampMixin, Base):
    __tablename__ = "merchant_rules"
    __table_args__ = (
        UniqueConstraint("pattern_normalized", "match_type", name="uq_merchant_rule"),
        CheckConstraint("priority >= 0", name="ck_merchant_rule_priority_nonnegative"),
        Index("ix_merchant_rules_enabled_priority", "enabled", "priority"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    pattern: Mapped[str] = mapped_column(String(200))
    pattern_normalized: Mapped[str] = mapped_column(String(200))
    match_type: Mapped[RuleMatchType] = mapped_column(Enum(RuleMatchType, native_enum=False))
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id"))
    priority: Mapped[int] = mapped_column(Integer, default=100)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    category: Mapped[Category] = relationship(back_populates="merchant_rules")


class MonthlyBudget(TimestampMixin, Base):
    __tablename__ = "monthly_budgets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    month: Mapped[date] = mapped_column(Date)
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id"))
    limit_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    __table_args__ = (
        UniqueConstraint("month", "category_id", name="uq_budget_month_category"),
        CheckConstraint(limit_amount >= 0, name="ck_budget_limit_nonnegative"),
        CheckConstraint(extract("day", month) == 1, name="ck_budget_month_first_day"),
    )

    category: Mapped[Category] = relationship(back_populates="budgets")


class MonthlyIncome(TimestampMixin, Base):
    __tablename__ = "monthly_income"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    month: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(String(160))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    __table_args__ = (
        CheckConstraint(amount >= 0, name="ck_income_nonnegative"),
        CheckConstraint(extract("day", month) == 1, name="ck_income_month_first_day"),
    )


class LoanTerms(TimestampMixin, Base):
    __tablename__ = "loan_terms"
    __table_args__ = (
        CheckConstraint("principal >= 0", name="ck_loan_principal_nonnegative"),
        CheckConstraint("annual_rate_basis_points >= 0", name="ck_loan_rate_nonnegative"),
        CheckConstraint("minimum_payment >= 0", name="ck_loan_payment_nonnegative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id"), unique=True
    )
    principal: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    annual_rate_basis_points: Mapped[int] = mapped_column(Integer)
    minimum_payment: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    term_months: Mapped[int | None] = mapped_column(Integer)

    account: Mapped[Account] = relationship(back_populates="loan_terms")
    balance_snapshots: Mapped[list[LoanBalanceSnapshot]] = relationship(
        back_populates="loan_terms"
    )


class LoanBalanceSnapshot(TimestampMixin, Base):
    __tablename__ = "loan_balance_snapshots"
    __table_args__ = (
        UniqueConstraint("loan_terms_id", "as_of_date", name="uq_loan_snapshot_date"),
        CheckConstraint("balance >= 0", name="ck_loan_balance_nonnegative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    loan_terms_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("loan_terms.id"))
    as_of_date: Mapped[date] = mapped_column(Date)
    balance: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    source: Mapped[str] = mapped_column(String(80), default="manual")

    loan_terms: Mapped[LoanTerms] = relationship(back_populates="balance_snapshots")
