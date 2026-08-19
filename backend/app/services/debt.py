"""Pure, deterministic debt projection calculations.

The calculator treats an APR in basis points as a fixed nominal annual rate. Interest
compounds monthly at ``APR / 12`` and is rounded to cents using ``ROUND_HALF_UP`` before
each payment is applied. Payments are also rounded to cents, and the final payment is
clamped to the amount due so a projection never overpays the loan.
"""

import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

CENT = Decimal("0.01")
BASIS_POINTS_PER_ONE = Decimal("10000")
MONTHS_PER_YEAR = Decimal("12")
DEFAULT_MAX_MONTHS = 1200


class AmortizationError(ValueError):
    """Base error for an invalid or non-converging projection."""


class InsufficientPaymentError(AmortizationError):
    """Raised when the payment cannot reduce the loan balance."""


class NonConvergingScheduleError(AmortizationError):
    """Raised when a loan is not paid off within the explicit iteration bound."""


class PayoffStrategy(StrEnum):
    SNOWBALL = "snowball"
    AVALANCHE = "avalanche"
    CUSTOM = "custom"


@dataclass(frozen=True)
class AmortizationPayment:
    month: int
    starting_balance: Decimal
    interest: Decimal
    payment: Decimal
    principal: Decimal
    ending_balance: Decimal


@dataclass(frozen=True)
class AmortizationSchedule:
    payments: tuple[AmortizationPayment, ...]
    total_interest: Decimal
    total_paid: Decimal
    months: int
    annual_rate_basis_points: int
    monthly_rate: Decimal
    rounding_mode: str = "ROUND_HALF_UP"
    compounding: str = "monthly"


@dataclass(frozen=True)
class ScenarioDebt:
    debt_id: uuid.UUID
    balance: Decimal
    annual_rate_basis_points: int
    minimum_payment: Decimal


@dataclass(frozen=True)
class ScenarioDebtPayment:
    debt_id: uuid.UUID
    starting_balance: Decimal
    interest: Decimal
    minimum_payment: Decimal
    strategy_payment: Decimal
    total_payment: Decimal
    principal: Decimal
    ending_balance: Decimal


@dataclass(frozen=True)
class ScenarioMonth:
    month: int
    extra_payment_targets: tuple[uuid.UUID, ...]
    payments: tuple[ScenarioDebtPayment, ...]
    total_payment: Decimal
    remaining_balance: Decimal


@dataclass(frozen=True)
class PayoffScenario:
    strategy: PayoffStrategy
    payoff_order: tuple[uuid.UUID, ...]
    extra_monthly_payment: Decimal
    monthly_payment_budget: Decimal
    schedule: tuple[ScenarioMonth, ...]
    total_interest: Decimal
    total_paid: Decimal
    months: int
    rounding_mode: str = "ROUND_HALF_UP"
    compounding: str = "monthly"


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_amortization(
    *,
    principal: Decimal,
    annual_rate_basis_points: int,
    monthly_payment: Decimal,
    max_months: int = DEFAULT_MAX_MONTHS,
) -> AmortizationSchedule:
    """Return a month-by-month fixed-rate amortization projection.

    All monetary inputs and outputs are cents. A zero balance has an empty schedule;
    otherwise the payment must be positive and must exceed first-month interest.
    """
    if principal < 0:
        raise AmortizationError("principal must not be negative")
    if annual_rate_basis_points < 0:
        raise AmortizationError("annual rate must not be negative")
    if monthly_payment < 0:
        raise AmortizationError("monthly payment must not be negative")
    if max_months <= 0:
        raise AmortizationError("max_months must be positive")

    balance = _money(principal)
    payment_amount = _money(monthly_payment)
    monthly_rate = (
        Decimal(annual_rate_basis_points) / BASIS_POINTS_PER_ONE / MONTHS_PER_YEAR
    )

    if balance == 0:
        return AmortizationSchedule(
            payments=(),
            total_interest=Decimal("0.00"),
            total_paid=Decimal("0.00"),
            months=0,
            annual_rate_basis_points=annual_rate_basis_points,
            monthly_rate=monthly_rate,
        )
    if payment_amount == 0:
        raise InsufficientPaymentError("monthly payment must be positive")

    first_interest = _money(balance * monthly_rate)
    if payment_amount <= first_interest:
        raise InsufficientPaymentError(
            "monthly payment must exceed accrued monthly interest"
        )

    rows: list[AmortizationPayment] = []
    total_interest = Decimal("0.00")
    total_paid = Decimal("0.00")

    for month in range(1, max_months + 1):
        starting_balance = balance
        interest = _money(starting_balance * monthly_rate)
        amount_due = starting_balance + interest
        actual_payment = min(payment_amount, amount_due)
        principal_paid = actual_payment - interest
        balance = _money(amount_due - actual_payment)

        rows.append(
            AmortizationPayment(
                month=month,
                starting_balance=starting_balance,
                interest=interest,
                payment=actual_payment,
                principal=principal_paid,
                ending_balance=balance,
            )
        )
        total_interest += interest
        total_paid += actual_payment
        if balance == 0:
            return AmortizationSchedule(
                payments=tuple(rows),
                total_interest=_money(total_interest),
                total_paid=_money(total_paid),
                months=month,
                annual_rate_basis_points=annual_rate_basis_points,
                monthly_rate=monthly_rate,
            )

    raise NonConvergingScheduleError(
        f"loan did not pay off within the {max_months}-month projection limit"
    )


def _payoff_order(
    debts: tuple[ScenarioDebt, ...],
    strategy: PayoffStrategy,
    custom_order: tuple[uuid.UUID, ...] | None,
) -> tuple[uuid.UUID, ...]:
    debt_ids = [debt.debt_id for debt in debts]
    if len(set(debt_ids)) != len(debt_ids):
        raise AmortizationError("each debt must appear exactly once")

    if strategy == PayoffStrategy.CUSTOM:
        if custom_order is None or len(custom_order) != len(debt_ids):
            raise AmortizationError("custom order must contain every selected debt once")
        if len(set(custom_order)) != len(custom_order) or set(custom_order) != set(debt_ids):
            raise AmortizationError("custom order must contain every selected debt once")
        return custom_order
    if custom_order is not None:
        raise AmortizationError("custom order is only valid for the custom strategy")
    if strategy == PayoffStrategy.SNOWBALL:
        ordered = sorted(
            debts,
            key=lambda debt: (
                _money(debt.balance),
                -debt.annual_rate_basis_points,
                str(debt.debt_id),
            ),
        )
    else:
        ordered = sorted(
            debts,
            key=lambda debt: (
                -debt.annual_rate_basis_points,
                _money(debt.balance),
                str(debt.debt_id),
            ),
        )
    return tuple(debt.debt_id for debt in ordered)


def calculate_payoff_scenario(
    *,
    debts: tuple[ScenarioDebt, ...],
    strategy: PayoffStrategy,
    extra_monthly_payment: Decimal = Decimal("0.00"),
    custom_order: tuple[uuid.UUID, ...] | None = None,
    max_months: int = DEFAULT_MAX_MONTHS,
) -> PayoffScenario:
    """Project a debt-payoff strategy using one fixed monthly payment budget.

    Minimum payments continue on every active debt. The initial combined minimums plus
    the explicit extra payment form a fixed budget; payments freed by a payoff roll to
    the next debt in the stable strategy order, including within the payoff month.
    """
    if not debts:
        raise AmortizationError("at least one debt is required")
    if extra_monthly_payment < 0:
        raise AmortizationError("extra monthly payment must not be negative")
    if max_months <= 0:
        raise AmortizationError("max_months must be positive")

    for debt in debts:
        if debt.balance < 0:
            raise AmortizationError("debt balance must not be negative")
        if debt.annual_rate_basis_points < 0:
            raise AmortizationError("annual rate must not be negative")
        if debt.minimum_payment < 0:
            raise AmortizationError("minimum payment must not be negative")

    order = _payoff_order(debts, strategy, custom_order)
    balances = {debt.debt_id: _money(debt.balance) for debt in debts}
    minimums = {debt.debt_id: _money(debt.minimum_payment) for debt in debts}
    rates = {
        debt.debt_id: Decimal(debt.annual_rate_basis_points)
        / BASIS_POINTS_PER_ONE
        / MONTHS_PER_YEAR
        for debt in debts
    }
    extra = _money(extra_monthly_payment)
    monthly_budget = _money(sum(minimums.values(), start=Decimal("0.00")) + extra)

    for debt_id in order:
        if balances[debt_id] == 0:
            continue
        first_interest = _money(balances[debt_id] * rates[debt_id])
        if minimums[debt_id] <= first_interest:
            raise InsufficientPaymentError(
                f"minimum payment for debt {debt_id} must exceed accrued monthly interest"
            )

    months: list[ScenarioMonth] = []
    total_interest = Decimal("0.00")
    total_paid = Decimal("0.00")

    for month_number in range(1, max_months + 1):
        if all(balance == 0 for balance in balances.values()):
            break

        starting = balances.copy()
        interest = {
            debt_id: _money(starting[debt_id] * rates[debt_id])
            if starting[debt_id] > 0
            else Decimal("0.00")
            for debt_id in order
        }
        due = {debt_id: starting[debt_id] + interest[debt_id] for debt_id in order}
        minimum_paid = {
            debt_id: min(minimums[debt_id], due[debt_id])
            if starting[debt_id] > 0
            else Decimal("0.00")
            for debt_id in order
        }
        remaining_budget = monthly_budget - sum(
            minimum_paid.values(), start=Decimal("0.00")
        )
        strategy_paid = {debt_id: Decimal("0.00") for debt_id in order}
        targets: list[uuid.UUID] = []

        for debt_id in order:
            still_due = due[debt_id] - minimum_paid[debt_id]
            if still_due <= 0 or remaining_budget <= 0:
                continue
            allocated = min(remaining_budget, still_due)
            strategy_paid[debt_id] = allocated
            remaining_budget -= allocated
            targets.append(debt_id)

        payment_rows: list[ScenarioDebtPayment] = []
        month_paid = Decimal("0.00")
        for debt_id in order:
            payment = minimum_paid[debt_id] + strategy_paid[debt_id]
            principal_paid = payment - interest[debt_id]
            ending = _money(due[debt_id] - payment)
            balances[debt_id] = ending
            month_paid += payment
            total_interest += interest[debt_id]
            payment_rows.append(
                ScenarioDebtPayment(
                    debt_id=debt_id,
                    starting_balance=starting[debt_id],
                    interest=interest[debt_id],
                    minimum_payment=minimum_paid[debt_id],
                    strategy_payment=strategy_paid[debt_id],
                    total_payment=payment,
                    principal=principal_paid,
                    ending_balance=ending,
                )
            )

        total_paid += month_paid
        months.append(
            ScenarioMonth(
                month=month_number,
                extra_payment_targets=tuple(targets),
                payments=tuple(payment_rows),
                total_payment=_money(month_paid),
                remaining_balance=_money(
                    sum(balances.values(), start=Decimal("0.00"))
                ),
            )
        )
        if all(balance == 0 for balance in balances.values()):
            break
    else:
        raise NonConvergingScheduleError(
            f"debts did not pay off within the {max_months}-month projection limit"
        )

    return PayoffScenario(
        strategy=strategy,
        payoff_order=order,
        extra_monthly_payment=extra,
        monthly_payment_budget=monthly_budget,
        schedule=tuple(months),
        total_interest=_money(total_interest),
        total_paid=_money(total_paid),
        months=len(months),
    )
