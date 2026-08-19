"""Pure, deterministic debt projection calculations.

The calculator treats an APR in basis points as a fixed nominal annual rate. Interest
compounds monthly at ``APR / 12`` and is rounded to cents using ``ROUND_HALF_UP`` before
each payment is applied. Payments are also rounded to cents, and the final payment is
clamped to the amount due so a projection never overpays the loan.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

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
