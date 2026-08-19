import uuid
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.models import Account, AccountType, LoanTerms
from app.main import create_app
from app.schemas.debt import (
    LoanBalanceCreate,
    LoanBalanceUpdate,
    LoanTermsCreate,
    LoanTermsUpdate,
)
from app.services import loans


def create_account(session: Session, account_type: AccountType = AccountType.LOAN) -> Account:
    account = Account(
        name="Synthetic Auto Loan",
        institution="Example Credit Union",
        account_type=account_type,
        currency="USD",
        current_balance=Decimal("12000.00"),
    )
    session.add(account)
    session.commit()
    return account


def create_loan(session: Session, account: Account | None = None) -> LoanTerms:
    account = account or create_account(session)
    return loans.create_loan(
        session,
        LoanTermsCreate(
            account_id=account.id,
            principal=Decimal("12000.00"),
            annual_rate_basis_points=675,
            minimum_payment=Decimal("325.00"),
            term_months=48,
        ),
    )


def test_debt_crud_api_contract_is_registered() -> None:
    paths = create_app().openapi()["paths"]

    assert set(paths["/api/v1/loans"]) == {"get", "post"}
    assert set(paths["/api/v1/loans/{loan_id}"]) == {"get", "patch", "delete"}
    assert set(paths["/api/v1/loans/{loan_id}/balances"]) == {"get", "post"}
    assert set(paths["/api/v1/loans/{loan_id}/balances/{balance_id}"]) == {
        "patch",
        "delete",
    }


def test_create_list_get_update_and_delete_loan_terms(db_session: Session) -> None:
    account = create_account(db_session)
    loan = create_loan(db_session, account)

    assert loans.list_loans(db_session) == [loan]
    assert loans.get_loan(db_session, loan.id) == loan

    updated = loans.update_loan(
        db_session,
        loan.id,
        LoanTermsUpdate(minimum_payment=Decimal("350.00"), term_months=None),
    )
    assert updated.minimum_payment == Decimal("350.00")
    assert updated.term_months is None

    loans.delete_loan(db_session, loan.id)
    with pytest.raises(loans.LoanNotFoundError):
        loans.get_loan(db_session, loan.id)


def test_loan_terms_require_a_loan_account(db_session: Session) -> None:
    checking = create_account(db_session, AccountType.CHECKING)

    with pytest.raises(loans.LoanAccountError):
        create_loan(db_session, checking)


def test_each_account_can_have_only_one_set_of_terms(db_session: Session) -> None:
    account = create_account(db_session)
    create_loan(db_session, account)

    with pytest.raises(loans.LoanConflictError):
        create_loan(db_session, account)

    assert len(loans.list_loans(db_session)) == 1


def test_balance_history_crud_is_dated_and_newest_first(db_session: Session) -> None:
    loan = create_loan(db_session)
    older = loans.create_balance(
        db_session,
        loan.id,
        LoanBalanceCreate(
            as_of_date=date(2026, 7, 1), balance=Decimal("11750.00"), source=" manual "
        ),
    )
    newer = loans.create_balance(
        db_session,
        loan.id,
        LoanBalanceCreate(
            as_of_date=date(2026, 8, 1), balance=Decimal("11480.25"), source="statement"
        ),
    )

    assert loans.list_balances(db_session, loan.id) == [newer, older]
    assert older.source == "manual"

    updated = loans.update_balance(
        db_session,
        loan.id,
        older.id,
        LoanBalanceUpdate(balance=Decimal("11740.00")),
    )
    assert updated.balance == Decimal("11740.00")

    loans.delete_balance(db_session, loan.id, newer.id)
    assert loans.list_balances(db_session, loan.id) == [older]


def test_duplicate_balance_date_is_rejected_without_losing_existing_data(
    db_session: Session,
) -> None:
    loan = create_loan(db_session)
    payload = LoanBalanceCreate(
        as_of_date=date(2026, 8, 1), balance=Decimal("100.00"), source="manual"
    )
    loans.create_balance(db_session, loan.id, payload)

    with pytest.raises(loans.BalanceConflictError):
        loans.create_balance(db_session, loan.id, payload)

    assert len(loans.list_balances(db_session, loan.id)) == 1


def test_balance_cannot_be_accessed_through_another_loan(db_session: Session) -> None:
    first = create_loan(db_session)
    second = create_loan(db_session)
    snapshot = loans.create_balance(
        db_session,
        first.id,
        LoanBalanceCreate(
            as_of_date=date(2026, 8, 1), balance=Decimal("100.00"), source="manual"
        ),
    )

    with pytest.raises(loans.BalanceNotFoundError):
        loans.get_balance(db_session, second.id, snapshot.id)


def test_deleting_terms_also_deletes_their_balance_history(db_session: Session) -> None:
    loan = create_loan(db_session)
    snapshot = loans.create_balance(
        db_session,
        loan.id,
        LoanBalanceCreate(
            as_of_date=date(2026, 8, 1), balance=Decimal("100.00"), source="manual"
        ),
    )

    loans.delete_loan(db_session, loan.id)

    assert db_session.get(type(snapshot), snapshot.id) is None


@pytest.mark.parametrize(
    "payload",
    [
        {"principal": "-0.01"},
        {"annual_rate_basis_points": -1},
        {"minimum_payment": "1.001"},
        {"term_months": 0},
        {},
    ],
)
def test_invalid_loan_updates_are_rejected(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        LoanTermsUpdate.model_validate(payload)


def test_unknown_loan_and_balance_are_rejected(db_session: Session) -> None:
    missing = uuid.uuid4()

    with pytest.raises(loans.LoanNotFoundError):
        loans.get_loan(db_session, missing)
    with pytest.raises(loans.LoanNotFoundError):
        loans.list_balances(db_session, missing)
