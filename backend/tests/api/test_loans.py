import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.routes.debt import project_amortization, project_scenarios
from app.db.models import Account, AccountType, LoanTerms
from app.main import create_app
from app.schemas.debt import (
    AmortizationProjectionRequest,
    LoanBalanceCreate,
    LoanBalanceUpdate,
    LoanTermsCreate,
    LoanTermsUpdate,
    ScenarioProjectionRequest,
)
from app.services import loans
from app.services.debt import PayoffStrategy


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
    assert set(paths["/api/v1/debt/amortization"]) == {"post"}
    assert set(paths["/api/v1/debt/scenarios"]) == {"post"}


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


def test_amortization_projection_exposes_dates_totals_and_assumptions() -> None:
    response = project_amortization(
        AmortizationProjectionRequest(
            principal=Decimal("1000.00"),
            annual_rate_basis_points=1200,
            monthly_payment=Decimal("100.00"),
            first_payment_date=date(2026, 1, 31),
        )
    )

    assert response.months == 11
    assert response.payoff_date == date(2026, 11, 30)
    assert response.total_interest == Decimal("58.98")
    assert response.payments[1].payment_date == date(2026, 2, 28)
    assert response.assumptions.maximum_months == 1200
    assert "ROUND_HALF_UP" in response.assumptions.currency_rounding
    assert "not financial advice" in response.assumptions.disclaimer


def test_amortization_projection_returns_a_clear_calculation_error() -> None:
    request = AmortizationProjectionRequest(
        principal=Decimal("1000.00"),
        annual_rate_basis_points=1200,
        monthly_payment=Decimal("10.00"),
        first_payment_date=date(2026, 1, 1),
    )

    with pytest.raises(HTTPException) as captured:
        project_amortization(request)

    assert captured.value.status_code == 422
    assert "must exceed" in captured.value.detail


def test_scenario_projection_compares_requested_strategies() -> None:
    first_id = uuid.UUID(int=1)
    second_id = uuid.UUID(int=2)
    response = project_scenarios(
        ScenarioProjectionRequest.model_validate(
            {
                "debts": [
                    {
                        "debt_id": first_id,
                        "balance": "800.00",
                        "annual_rate_basis_points": 500,
                        "minimum_payment": "60.00",
                    },
                    {
                        "debt_id": second_id,
                        "balance": "1200.00",
                        "annual_rate_basis_points": 1900,
                        "minimum_payment": "75.00",
                    },
                ],
                "strategies": ["snowball", "avalanche"],
                "extra_monthly_payment": "100.00",
                "first_payment_date": "2026-09-15",
            }
        )
    )

    assert [item.strategy for item in response.scenarios] == [
        PayoffStrategy.SNOWBALL,
        PayoffStrategy.AVALANCHE,
    ]
    assert response.comparison_baseline in {
        PayoffStrategy.SNOWBALL,
        PayoffStrategy.AVALANCHE,
    }
    assert all(item.payoff_date is not None for item in response.scenarios)
    assert all(item.months_saved >= 0 for item in response.scenarios)
    assert all(item.monthly_payment_budget == Decimal("235.00") for item in response.scenarios)
    assert response.scenarios[0].schedule[0].payment_date == date(2026, 9, 15)
    assert response.scenarios[0].schedule[0].payments
    baseline = next(
        item
        for item in response.scenarios
        if item.strategy == response.comparison_baseline
    )
    assert baseline.months_saved == 0
    assert baseline.interest_saved == Decimal("0.00")


def test_scenario_request_requires_consistent_custom_configuration() -> None:
    debt_id = uuid.UUID(int=1)
    base = {
        "debts": [
            {
                "debt_id": debt_id,
                "balance": "100.00",
                "annual_rate_basis_points": 0,
                "minimum_payment": "10.00",
            }
        ],
        "first_payment_date": "2026-09-01",
    }

    with pytest.raises(ValidationError, match="custom_order is required"):
        ScenarioProjectionRequest.model_validate({**base, "strategies": ["custom"]})
    with pytest.raises(ValidationError, match="requires the custom strategy"):
        ScenarioProjectionRequest.model_validate(
            {**base, "strategies": ["snowball"], "custom_order": [debt_id]}
        )


def test_projection_requests_do_not_accept_unbounded_schedules() -> None:
    with pytest.raises(ValidationError):
        AmortizationProjectionRequest(
            principal=Decimal("100.00"),
            annual_rate_basis_points=0,
            monthly_payment=Decimal("1.00"),
            first_payment_date=date(2026, 1, 1),
            max_months=1201,
        )
