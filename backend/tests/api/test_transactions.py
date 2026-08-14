import uuid
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.models import Account, AccountType, Category, CategoryKind
from app.main import create_app
from app.schemas.transactions import TransactionCreate, TransactionUpdate
from app.services import transactions


def references(session: Session) -> tuple[Account, Category]:
    account = Account(
        name="Synthetic Checking",
        institution="Example Credit Union",
        account_type=AccountType.CHECKING,
        currency="USD",
    )
    category = Category(name="Synthetic Groceries", kind=CategoryKind.EXPENSE)
    session.add_all((account, category))
    session.commit()
    return account, category


def transaction_data(
    account: Account,
    category: Category | None,
    *,
    description: str = "Example Market",
    amount: str = "-42.15",
    posted_date: date = date(2026, 8, 14),
) -> TransactionCreate:
    return TransactionCreate.model_validate(
        {
            "account_id": account.id,
            "category_id": category.id if category else None,
            "posted_date": posted_date,
            "description": description,
            "amount": amount,
        }
    )


def test_transaction_api_contract_is_registered() -> None:
    paths = create_app().openapi()["paths"]

    assert set(paths["/api/v1/transactions"]) == {"get", "post"}
    assert set(paths["/api/v1/transactions/{transaction_id}"]) == {
        "get",
        "patch",
        "delete",
    }


def test_create_repeated_transactions_with_stable_occurrences(db_session: Session) -> None:
    account, category = references(db_session)
    data = transaction_data(account, category)

    first = transactions.create_transaction(db_session, data)
    second = transactions.create_transaction(db_session, data)

    assert first.amount == Decimal("-42.15")
    assert first.merchant_normalized == "EXAMPLE MARKET"
    assert (first.occurrence_index, second.occurrence_index) == (1, 2)
    assert first.fingerprint != second.fingerprint


def test_filter_by_account_category_date_status_and_search(db_session: Session) -> None:
    account, category = references(db_session)
    uncategorized = transactions.create_transaction(
        db_session,
        transaction_data(
            account,
            None,
            description="Uncategorized Example",
            posted_date=date(2026, 8, 12),
        ),
    )
    categorized = transactions.create_transaction(
        db_session,
        transaction_data(account, category, description="Example Market"),
    )
    transactions.update_transaction(
        db_session,
        categorized.id,
        TransactionUpdate.model_validate({"excluded_from_budget": True}),
    )

    assert transactions.list_transactions(
        db_session, transactions.TransactionFilters(account_id=account.id)
    ) == [categorized, uncategorized]
    assert transactions.list_transactions(
        db_session, transactions.TransactionFilters(category_id=category.id)
    ) == [categorized]
    assert transactions.list_transactions(
        db_session, transactions.TransactionFilters(uncategorized=True)
    ) == [uncategorized]
    assert transactions.list_transactions(
        db_session, transactions.TransactionFilters(excluded=True)
    ) == [categorized]
    assert transactions.list_transactions(
        db_session,
        transactions.TransactionFilters(
            posted_from=date(2026, 8, 13), search="market"
        ),
    ) == [categorized]


def test_update_recalculates_fingerprint_and_allows_uncategorizing(
    db_session: Session,
) -> None:
    account, category = references(db_session)
    transaction = transactions.create_transaction(
        db_session, transaction_data(account, category)
    )
    original_fingerprint = transaction.fingerprint

    updated = transactions.update_transaction(
        db_session,
        transaction.id,
        TransactionUpdate.model_validate(
            {"description": "Different Merchant", "category_id": None}
        ),
    )
    assert updated.category_id is None
    assert updated.merchant_normalized == "DIFFERENT MERCHANT"
    assert updated.fingerprint != original_fingerprint


def test_delete_transaction(db_session: Session) -> None:
    account, category = references(db_session)
    transaction = transactions.create_transaction(
        db_session, transaction_data(account, category)
    )

    transactions.delete_transaction(db_session, transaction.id)
    with pytest.raises(transactions.TransactionNotFoundError):
        transactions.get_transaction(db_session, transaction.id)


def test_archived_references_are_rejected(db_session: Session) -> None:
    account, category = references(db_session)
    account.archived = True
    db_session.commit()
    with pytest.raises(transactions.TransactionReferenceError):
        transactions.create_transaction(db_session, transaction_data(account, category))

    account.archived = False
    category.archived = True
    db_session.commit()
    with pytest.raises(transactions.TransactionReferenceError):
        transactions.create_transaction(db_session, transaction_data(account, category))


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"description": " "},
        {"amount": "0.00"},
        {"amount": "1.234"},
        {"account_id": None},
        {"posted_date": None},
        {"excluded_from_budget": None},
    ],
)
def test_invalid_transaction_update_is_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        TransactionUpdate.model_validate(changes)


def test_unknown_transaction_is_rejected(db_session: Session) -> None:
    missing_id = uuid.uuid4()
    with pytest.raises(transactions.TransactionNotFoundError):
        transactions.get_transaction(db_session, missing_id)
    with pytest.raises(transactions.TransactionNotFoundError):
        transactions.delete_transaction(db_session, missing_id)
