import hashlib
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.categorization.merchant import normalize_merchant
from app.db.models import Account, CategorizationSource, Category, Transaction
from app.schemas.transactions import TransactionCreate, TransactionUpdate


class TransactionNotFoundError(Exception):
    pass


class TransactionConflictError(Exception):
    pass


class TransactionReferenceError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class TransactionFilters:
    account_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    posted_from: date | None = None
    posted_to: date | None = None
    uncategorized: bool | None = None
    excluded: bool | None = None
    search: str | None = None


def list_transactions(session: Session, filters: TransactionFilters) -> list[Transaction]:
    statement: Select[tuple[Transaction]] = select(Transaction)
    if filters.account_id is not None:
        statement = statement.where(Transaction.account_id == filters.account_id)
    if filters.category_id is not None:
        statement = statement.where(Transaction.category_id == filters.category_id)
    if filters.posted_from is not None:
        statement = statement.where(Transaction.posted_date >= filters.posted_from)
    if filters.posted_to is not None:
        statement = statement.where(Transaction.posted_date <= filters.posted_to)
    if filters.uncategorized is True:
        statement = statement.where(Transaction.category_id.is_(None))
    elif filters.uncategorized is False:
        statement = statement.where(Transaction.category_id.is_not(None))
    if filters.excluded is not None:
        statement = statement.where(Transaction.excluded_from_budget.is_(filters.excluded))
    if filters.search:
        escaped = (
            filters.search.strip()
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        statement = statement.where(Transaction.description.ilike(f"%{escaped}%", escape="\\"))
    statement = statement.order_by(
        Transaction.posted_date.desc(), Transaction.created_at.desc(), Transaction.id
    )
    return list(session.scalars(statement))


def get_transaction(session: Session, transaction_id: uuid.UUID) -> Transaction:
    transaction = session.get(Transaction, transaction_id)
    if transaction is None:
        raise TransactionNotFoundError
    return transaction


def _validate_account(session: Session, account_id: uuid.UUID) -> None:
    account = session.get(Account, account_id)
    if account is None or account.archived:
        raise TransactionReferenceError("Account is unavailable")


def _validate_category(session: Session, category_id: uuid.UUID | None) -> None:
    if category_id is None:
        return
    category = session.get(Category, category_id)
    if category is None or category.archived:
        raise TransactionReferenceError("Category is unavailable")


def _next_occurrence(
    session: Session,
    *,
    account_id: uuid.UUID,
    posted_date: date,
    merchant_normalized: str,
    amount: Decimal,
    excluding: uuid.UUID | None = None,
) -> int:
    statement = select(Transaction.occurrence_index).where(
        Transaction.account_id == account_id,
        Transaction.posted_date == posted_date,
        Transaction.merchant_normalized == merchant_normalized,
        Transaction.amount == amount,
    )
    if excluding is not None:
        statement = statement.where(Transaction.id != excluding)
    used = set(session.scalars(statement))
    occurrence = 1
    while occurrence in used:
        occurrence += 1
    return occurrence


def build_fingerprint(
    account_id: uuid.UUID,
    posted_date: date,
    merchant_normalized: str,
    amount: Decimal,
    occurrence: int,
) -> str:
    source = "|".join(
        (
            str(account_id),
            posted_date.isoformat(),
            merchant_normalized,
            format(amount, ".2f"),
            str(occurrence),
        )
    )
    return hashlib.sha256(source.encode()).hexdigest()


def _set_fingerprint(session: Session, transaction: Transaction) -> None:
    merchant = normalize_merchant(transaction.description)
    occurrence = _next_occurrence(
        session,
        account_id=transaction.account_id,
        posted_date=transaction.posted_date,
        merchant_normalized=merchant,
        amount=transaction.amount,
        excluding=transaction.id,
    )
    transaction.merchant_normalized = merchant
    transaction.occurrence_index = occurrence
    transaction.fingerprint = build_fingerprint(
        transaction.account_id,
        transaction.posted_date,
        merchant,
        transaction.amount,
        occurrence,
    )


def _commit(session: Session, transaction: Transaction) -> Transaction:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise TransactionConflictError from error
    session.refresh(transaction)
    return transaction


def create_transaction(session: Session, data: TransactionCreate) -> Transaction:
    _validate_account(session, data.account_id)
    _validate_category(session, data.category_id)
    transaction = Transaction(
        **data.model_dump(),
        fingerprint="",
        occurrence_index=1,
        categorization_source=(
            CategorizationSource.MANUAL if data.category_id is not None else None
        ),
        categorization_rule_id=None,
    )
    session.add(transaction)
    _set_fingerprint(session, transaction)
    return _commit(session, transaction)


def update_transaction(
    session: Session, transaction_id: uuid.UUID, data: TransactionUpdate
) -> Transaction:
    transaction = get_transaction(session, transaction_id)
    changes = data.model_dump(exclude_unset=True)
    previous_category_id = transaction.category_id
    if "account_id" in changes:
        _validate_account(session, changes["account_id"])
    if "category_id" in changes:
        _validate_category(session, changes["category_id"])
    fingerprint_fields = {"account_id", "posted_date", "description", "amount"}
    for field, value in changes.items():
        setattr(transaction, field, value)
    if "category_id" in changes:
        if changes["category_id"] is None:
            transaction.categorization_source = None
            transaction.categorization_rule_id = None
        elif changes["category_id"] != previous_category_id:
            transaction.categorization_source = CategorizationSource.MANUAL
            transaction.categorization_rule_id = None
    if fingerprint_fields & changes.keys():
        _set_fingerprint(session, transaction)
    return _commit(session, transaction)


def delete_transaction(session: Session, transaction_id: uuid.UUID) -> None:
    transaction = get_transaction(session, transaction_id)
    session.delete(transaction)
    session.commit()
