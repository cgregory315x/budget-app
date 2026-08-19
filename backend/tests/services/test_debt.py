from decimal import Decimal

import pytest

from app.services.debt import (
    AmortizationError,
    InsufficientPaymentError,
    NonConvergingScheduleError,
    calculate_amortization,
)


def test_calculates_monthly_schedule_with_explicit_cent_rounding() -> None:
    schedule = calculate_amortization(
        principal=Decimal("1000.00"),
        annual_rate_basis_points=1200,
        monthly_payment=Decimal("100.00"),
    )

    assert schedule.months == 11
    assert schedule.total_interest == Decimal("58.98")
    assert schedule.total_paid == Decimal("1058.98")
    assert schedule.monthly_rate == Decimal("0.01")
    assert schedule.rounding_mode == "ROUND_HALF_UP"
    assert schedule.compounding == "monthly"
    assert schedule.payments[0].interest == Decimal("10.00")
    assert schedule.payments[0].principal == Decimal("90.00")
    assert schedule.payments[-1].payment == Decimal("58.98")
    assert schedule.payments[-1].ending_balance == Decimal("0.00")


def test_rounds_half_cents_up_at_the_monthly_interest_boundary() -> None:
    schedule = calculate_amortization(
        principal=Decimal("1.00"),
        annual_rate_basis_points=600,
        monthly_payment=Decimal("2.00"),
    )

    assert schedule.payments[0].interest == Decimal("0.01")
    assert schedule.payments[0].payment == Decimal("1.01")


def test_zero_balance_has_an_empty_schedule() -> None:
    schedule = calculate_amortization(
        principal=Decimal("0.00"),
        annual_rate_basis_points=2500,
        monthly_payment=Decimal("0.00"),
    )

    assert schedule.months == 0
    assert schedule.payments == ()
    assert schedule.total_interest == Decimal("0.00")
    assert schedule.total_paid == Decimal("0.00")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("principal", Decimal("-0.01"), "principal"),
        ("annual_rate_basis_points", -1, "annual rate"),
        ("monthly_payment", Decimal("-0.01"), "monthly payment"),
        ("max_months", 0, "max_months"),
    ],
)
def test_rejects_negative_or_invalid_inputs(
    field: str, value: Decimal | int, message: str
) -> None:
    arguments: dict[str, Decimal | int] = {
        "principal": Decimal("100.00"),
        "annual_rate_basis_points": 1200,
        "monthly_payment": Decimal("10.00"),
        "max_months": 1200,
    }
    arguments[field] = value

    with pytest.raises(AmortizationError, match=message):
        calculate_amortization(**arguments)  # type: ignore[arg-type]


@pytest.mark.parametrize("payment", [Decimal("0.00"), Decimal("10.00")])
def test_rejects_payments_that_do_not_reduce_the_balance(payment: Decimal) -> None:
    with pytest.raises(InsufficientPaymentError):
        calculate_amortization(
            principal=Decimal("1000.00"),
            annual_rate_basis_points=1200,
            monthly_payment=payment,
        )


def test_fails_explicitly_at_the_iteration_bound() -> None:
    with pytest.raises(NonConvergingScheduleError, match="12-month"):
        calculate_amortization(
            principal=Decimal("1000.00"),
            annual_rate_basis_points=0,
            monthly_payment=Decimal("1.00"),
            max_months=12,
        )
