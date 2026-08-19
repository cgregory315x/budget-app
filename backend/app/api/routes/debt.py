import calendar
import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.debt import (
    AmortizationPaymentResponse,
    AmortizationProjectionRequest,
    AmortizationProjectionResponse,
    LoanBalanceCreate,
    LoanBalanceResponse,
    LoanBalanceUpdate,
    LoanTermsCreate,
    LoanTermsResponse,
    LoanTermsUpdate,
    ProjectionAssumptions,
    ScenarioComparisonResponse,
    ScenarioDebtPaymentResponse,
    ScenarioMonthResponse,
    ScenarioProjectionRequest,
    ScenarioResultResponse,
)
from app.services import debt, loans

router = APIRouter()
projection_router = APIRouter()
SessionDependency = Annotated[Session, Depends(get_db_session)]


def _loan_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Loan not found")


def _balance_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Balance snapshot not found")


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=409, detail=detail)


def _projection_error(error: debt.AmortizationError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(error))


def _payment_date(first_payment_date: date, offset: int) -> date:
    month_index = first_payment_date.month - 1 + offset
    year = first_payment_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(first_payment_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _assumptions(max_months: int) -> ProjectionAssumptions:
    return ProjectionAssumptions(
        apr_treatment="Fixed nominal APR where 100 basis points equals 1% APR.",
        periodic_rate="APR divided by 12; no daily-interest calculation.",
        compounding="Interest compounds monthly.",
        payment_timing="Monthly interest accrues before that month's payment.",
        currency_rounding="Interest and balances round to cents using ROUND_HALF_UP.",
        final_payment="The final payment is clamped to principal plus accrued interest.",
        maximum_months=max_months,
        disclaimer="Projections are estimates, not financial advice or payoff guarantees.",
    )


@router.get("", response_model=list[LoanTermsResponse])
def list_all(session: SessionDependency) -> list[LoanTermsResponse]:
    return [LoanTermsResponse.model_validate(item) for item in loans.list_loans(session)]


@router.post("", response_model=LoanTermsResponse, status_code=status.HTTP_201_CREATED)
def create(data: LoanTermsCreate, session: SessionDependency) -> LoanTermsResponse:
    try:
        loan = loans.create_loan(session, data)
    except loans.LoanAccountError as error:
        raise _conflict("Loan terms require an existing loan account") from error
    except loans.LoanConflictError as error:
        raise _conflict("The account already has loan terms") from error
    return LoanTermsResponse.model_validate(loan)


@router.get("/{loan_id}", response_model=LoanTermsResponse)
def get(loan_id: uuid.UUID, session: SessionDependency) -> LoanTermsResponse:
    try:
        loan = loans.get_loan(session, loan_id)
    except loans.LoanNotFoundError as error:
        raise _loan_not_found() from error
    return LoanTermsResponse.model_validate(loan)


@router.patch("/{loan_id}", response_model=LoanTermsResponse)
def update(
    loan_id: uuid.UUID, data: LoanTermsUpdate, session: SessionDependency
) -> LoanTermsResponse:
    try:
        loan = loans.update_loan(session, loan_id, data)
    except loans.LoanNotFoundError as error:
        raise _loan_not_found() from error
    return LoanTermsResponse.model_validate(loan)


@router.delete("/{loan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(loan_id: uuid.UUID, session: SessionDependency) -> Response:
    try:
        loans.delete_loan(session, loan_id)
    except loans.LoanNotFoundError as error:
        raise _loan_not_found() from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{loan_id}/balances", response_model=list[LoanBalanceResponse])
def list_balance_history(
    loan_id: uuid.UUID, session: SessionDependency
) -> list[LoanBalanceResponse]:
    try:
        snapshots = loans.list_balances(session, loan_id)
    except loans.LoanNotFoundError as error:
        raise _loan_not_found() from error
    return [LoanBalanceResponse.model_validate(item) for item in snapshots]


@router.post(
    "/{loan_id}/balances",
    response_model=LoanBalanceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_balance(
    loan_id: uuid.UUID, data: LoanBalanceCreate, session: SessionDependency
) -> LoanBalanceResponse:
    try:
        snapshot = loans.create_balance(session, loan_id, data)
    except loans.LoanNotFoundError as error:
        raise _loan_not_found() from error
    except loans.BalanceConflictError as error:
        raise _conflict("A balance already exists for this loan and date") from error
    return LoanBalanceResponse.model_validate(snapshot)


@router.patch(
    "/{loan_id}/balances/{balance_id}", response_model=LoanBalanceResponse
)
def update_balance(
    loan_id: uuid.UUID,
    balance_id: uuid.UUID,
    data: LoanBalanceUpdate,
    session: SessionDependency,
) -> LoanBalanceResponse:
    try:
        snapshot = loans.update_balance(session, loan_id, balance_id, data)
    except loans.BalanceNotFoundError as error:
        raise _balance_not_found() from error
    except loans.BalanceConflictError as error:
        raise _conflict("A balance already exists for this loan and date") from error
    return LoanBalanceResponse.model_validate(snapshot)


@router.delete(
    "/{loan_id}/balances/{balance_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_balance(
    loan_id: uuid.UUID, balance_id: uuid.UUID, session: SessionDependency
) -> Response:
    try:
        loans.delete_balance(session, loan_id, balance_id)
    except loans.BalanceNotFoundError as error:
        raise _balance_not_found() from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@projection_router.post(
    "/amortization", response_model=AmortizationProjectionResponse
)
def project_amortization(
    data: AmortizationProjectionRequest,
) -> AmortizationProjectionResponse:
    try:
        schedule = debt.calculate_amortization(
            principal=data.principal,
            annual_rate_basis_points=data.annual_rate_basis_points,
            monthly_payment=data.monthly_payment,
            max_months=data.max_months,
        )
    except debt.AmortizationError as error:
        raise _projection_error(error) from error

    payments = [
        AmortizationPaymentResponse(
            month=row.month,
            payment_date=_payment_date(data.first_payment_date, row.month - 1),
            starting_balance=row.starting_balance,
            interest=row.interest,
            payment=row.payment,
            principal=row.principal,
            ending_balance=row.ending_balance,
        )
        for row in schedule.payments
    ]
    return AmortizationProjectionResponse(
        assumptions=_assumptions(data.max_months),
        payments=payments,
        total_interest=schedule.total_interest,
        total_paid=schedule.total_paid,
        months=schedule.months,
        payoff_date=payments[-1].payment_date if payments else None,
        annual_rate_basis_points=schedule.annual_rate_basis_points,
        monthly_rate=schedule.monthly_rate,
    )


def _scenario_response(
    scenario: debt.PayoffScenario,
    first_payment_date: date,
    *,
    baseline_months: int,
    baseline_interest: Decimal,
) -> ScenarioResultResponse:
    schedule = [
        ScenarioMonthResponse(
            month=row.month,
            payment_date=_payment_date(first_payment_date, row.month - 1),
            extra_payment_targets=list(row.extra_payment_targets),
            payments=[
                ScenarioDebtPaymentResponse(
                    debt_id=payment.debt_id,
                    starting_balance=payment.starting_balance,
                    interest=payment.interest,
                    minimum_payment=payment.minimum_payment,
                    strategy_payment=payment.strategy_payment,
                    total_payment=payment.total_payment,
                    principal=payment.principal,
                    ending_balance=payment.ending_balance,
                )
                for payment in row.payments
            ],
            total_payment=row.total_payment,
            remaining_balance=row.remaining_balance,
        )
        for row in scenario.schedule
    ]
    return ScenarioResultResponse(
        strategy=scenario.strategy,
        payoff_order=list(scenario.payoff_order),
        extra_monthly_payment=scenario.extra_monthly_payment,
        monthly_payment_budget=scenario.monthly_payment_budget,
        schedule=schedule,
        total_interest=scenario.total_interest,
        total_paid=scenario.total_paid,
        months=scenario.months,
        payoff_date=schedule[-1].payment_date if schedule else None,
        months_saved=baseline_months - scenario.months,
        interest_saved=baseline_interest - scenario.total_interest,
    )


@projection_router.post("/scenarios", response_model=ScenarioComparisonResponse)
def project_scenarios(data: ScenarioProjectionRequest) -> ScenarioComparisonResponse:
    scenario_debts = tuple(
        debt.ScenarioDebt(
            debt_id=item.debt_id,
            balance=item.balance,
            annual_rate_basis_points=item.annual_rate_basis_points,
            minimum_payment=item.minimum_payment,
        )
        for item in data.debts
    )
    custom_order = tuple(data.custom_order) if data.custom_order is not None else None
    try:
        projections = [
            debt.calculate_payoff_scenario(
                debts=scenario_debts,
                strategy=strategy,
                extra_monthly_payment=data.extra_monthly_payment,
                custom_order=custom_order if strategy == debt.PayoffStrategy.CUSTOM else None,
                max_months=data.max_months,
            )
            for strategy in data.strategies
        ]
    except debt.AmortizationError as error:
        raise _projection_error(error) from error

    baseline = max(
        projections,
        key=lambda item: (item.months, item.total_interest, item.strategy.value),
    )
    return ScenarioComparisonResponse(
        assumptions=_assumptions(data.max_months),
        comparison_baseline=baseline.strategy,
        scenarios=[
            _scenario_response(
                scenario,
                data.first_payment_date,
                baseline_months=baseline.months,
                baseline_interest=baseline.total_interest,
            )
            for scenario in projections
        ],
    )
