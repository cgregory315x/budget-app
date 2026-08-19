import uuid
from decimal import Decimal

import pytest

from app.services.debt import (
    AmortizationError,
    InsufficientPaymentError,
    NonConvergingScheduleError,
    PayoffStrategy,
    ScenarioDebt,
    calculate_amortization,
    calculate_payoff_scenario,
)

SMALL_DEBT_ID = uuid.UUID(int=1)
LARGE_DEBT_ID = uuid.UUID(int=2)


def scenario_debts() -> tuple[ScenarioDebt, ...]:
    return (
        ScenarioDebt(
            debt_id=LARGE_DEBT_ID,
            balance=Decimal("200.00"),
            annual_rate_basis_points=0,
            minimum_payment=Decimal("20.00"),
        ),
        ScenarioDebt(
            debt_id=SMALL_DEBT_ID,
            balance=Decimal("100.00"),
            annual_rate_basis_points=0,
            minimum_payment=Decimal("30.00"),
        ),
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


def test_snowball_uses_stable_balance_order_and_rolls_freed_payments() -> None:
    scenario = calculate_payoff_scenario(
        debts=scenario_debts(),
        strategy=PayoffStrategy.SNOWBALL,
        extra_monthly_payment=Decimal("50.00"),
    )

    assert scenario.payoff_order == (SMALL_DEBT_ID, LARGE_DEBT_ID)
    assert scenario.monthly_payment_budget == Decimal("100.00")
    assert scenario.months == 3
    assert scenario.total_interest == Decimal("0.00")
    assert scenario.total_paid == Decimal("300.00")
    assert scenario.schedule[0].extra_payment_targets == (SMALL_DEBT_ID,)
    assert scenario.schedule[1].extra_payment_targets == (LARGE_DEBT_ID,)
    assert scenario.schedule[-1].total_payment == Decimal("100.00")
    assert scenario.schedule[-1].remaining_balance == Decimal("0.00")


def test_avalanche_orders_highest_apr_first_with_deterministic_ties() -> None:
    lowest_id = uuid.UUID(int=3)
    debts = (
        ScenarioDebt(lowest_id, Decimal("300.00"), 1800, Decimal("40.00")),
        ScenarioDebt(LARGE_DEBT_ID, Decimal("200.00"), 1800, Decimal("40.00")),
        ScenarioDebt(SMALL_DEBT_ID, Decimal("100.00"), 1200, Decimal("40.00")),
    )

    scenario = calculate_payoff_scenario(
        debts=debts,
        strategy=PayoffStrategy.AVALANCHE,
        extra_monthly_payment=Decimal("10.00"),
    )

    assert scenario.payoff_order == (LARGE_DEBT_ID, lowest_id, SMALL_DEBT_ID)
    assert scenario.schedule[0].extra_payment_targets == (LARGE_DEBT_ID,)


def test_custom_strategy_requires_every_debt_exactly_once() -> None:
    expected_order = (LARGE_DEBT_ID, SMALL_DEBT_ID)
    scenario = calculate_payoff_scenario(
        debts=scenario_debts(),
        strategy=PayoffStrategy.CUSTOM,
        custom_order=expected_order,
    )

    assert scenario.payoff_order == expected_order

    with pytest.raises(AmortizationError, match="every selected debt once"):
        calculate_payoff_scenario(
            debts=scenario_debts(),
            strategy=PayoffStrategy.CUSTOM,
            custom_order=(SMALL_DEBT_ID, SMALL_DEBT_ID),
        )


def test_rejects_custom_order_for_an_automatic_strategy() -> None:
    with pytest.raises(AmortizationError, match="only valid"):
        calculate_payoff_scenario(
            debts=scenario_debts(),
            strategy=PayoffStrategy.SNOWBALL,
            custom_order=(SMALL_DEBT_ID, LARGE_DEBT_ID),
        )


def test_rejects_duplicate_debts_and_invalid_scenario_inputs() -> None:
    duplicate = (scenario_debts()[0], scenario_debts()[0])
    with pytest.raises(AmortizationError, match="exactly once"):
        calculate_payoff_scenario(debts=duplicate, strategy=PayoffStrategy.SNOWBALL)
    with pytest.raises(AmortizationError, match="at least one debt"):
        calculate_payoff_scenario(debts=(), strategy=PayoffStrategy.SNOWBALL)
    with pytest.raises(AmortizationError, match="extra monthly"):
        calculate_payoff_scenario(
            debts=scenario_debts(),
            strategy=PayoffStrategy.SNOWBALL,
            extra_monthly_payment=Decimal("-0.01"),
        )


def test_rejects_a_minimum_that_does_not_cover_interest() -> None:
    debt = ScenarioDebt(
        debt_id=SMALL_DEBT_ID,
        balance=Decimal("1000.00"),
        annual_rate_basis_points=1200,
        minimum_payment=Decimal("10.00"),
    )

    with pytest.raises(InsufficientPaymentError, match=str(SMALL_DEBT_ID)):
        calculate_payoff_scenario(
            debts=(debt,),
            strategy=PayoffStrategy.SNOWBALL,
            extra_monthly_payment=Decimal("100.00"),
        )


def test_scenario_clamps_final_payment_and_honors_exact_iteration_limit() -> None:
    debt = ScenarioDebt(
        debt_id=SMALL_DEBT_ID,
        balance=Decimal("100.00"),
        annual_rate_basis_points=0,
        minimum_payment=Decimal("60.00"),
    )
    scenario = calculate_payoff_scenario(
        debts=(debt,), strategy=PayoffStrategy.SNOWBALL, max_months=2
    )

    assert scenario.months == 2
    assert scenario.schedule[-1].total_payment == Decimal("40.00")

    with pytest.raises(NonConvergingScheduleError, match="1-month"):
        calculate_payoff_scenario(
            debts=(debt,), strategy=PayoffStrategy.SNOWBALL, max_months=1
        )
