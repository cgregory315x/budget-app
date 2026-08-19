import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import (
    Account,
    AccountType,
    Category,
    CategoryKind,
    MonthlyBudget,
    MonthlyIncome,
    Transaction,
)
from app.main import create_app
from app.services.monthly_summary import build_monthly_summary, build_monthly_trends

AUGUST = date(2026, 8, 1)


def add_transaction(
    session: Session,
    account: Account,
    *,
    amount: str,
    category: Category | None = None,
    posted_date: date = date(2026, 8, 14),
    excluded: bool = False,
) -> Transaction:
    transaction = Transaction(
        account_id=account.id,
        category_id=category.id if category else None,
        posted_date=posted_date,
        description="Synthetic transaction",
        amount=Decimal(amount),
        fingerprint=uuid.uuid4().hex,
        occurrence_index=1,
        excluded_from_budget=excluded,
    )
    session.add(transaction)
    return transaction


def test_monthly_summary_api_contract_is_registered() -> None:
    schema = create_app().openapi()

    assert set(schema["paths"]["/api/v1/summary"]) == {"get"}
    parameters = schema["paths"]["/api/v1/summary"]["get"]["parameters"]
    assert parameters[0]["name"] == "month"
    assert parameters[0]["required"] is True

    trend_operation = schema["paths"]["/api/v1/summary/trends"]["get"]
    trend_parameters = {parameter["name"]: parameter for parameter in trend_operation["parameters"]}
    assert trend_parameters["end_month"]["required"] is True
    assert trend_parameters["months"]["schema"]["default"] == 6
    assert trend_parameters["months"]["schema"]["minimum"] == 2
    assert trend_parameters["months"]["schema"]["maximum"] == 24


def test_builds_monthly_totals_composition_and_budget_progress(
    db_session: Session,
) -> None:
    account = Account(
        name="Synthetic Checking",
        institution="Example Credit Union",
        account_type=AccountType.CHECKING,
        currency="USD",
    )
    expense = Category(name="Synthetic Groceries", kind=CategoryKind.EXPENSE, color="#112233")
    income_category = Category(name="Synthetic Income", kind=CategoryKind.INCOME)
    transfer = Category(name="Synthetic Transfer", kind=CategoryKind.TRANSFER)
    db_session.add_all((account, expense, income_category, transfer))
    db_session.flush()

    add_transaction(db_session, account, amount="-100.00", category=expense)
    add_transaction(db_session, account, amount="20.00", category=expense)
    add_transaction(db_session, account, amount="-30.00")
    add_transaction(db_session, account, amount="500.00")
    add_transaction(db_session, account, amount="1000.00", category=income_category)
    add_transaction(db_session, account, amount="200.00", category=transfer)
    add_transaction(db_session, account, amount="-200.00", category=transfer)
    add_transaction(db_session, account, amount="-50.00", excluded=True)
    add_transaction(
        db_session,
        account,
        amount="-999.00",
        category=expense,
        posted_date=date(2026, 9, 1),
    )
    budget = MonthlyBudget(
        month=AUGUST, category_id=expense.id, limit_amount=Decimal("75.00")
    )
    db_session.add_all(
        (
            budget,
            MonthlyIncome(
                month=AUGUST,
                description="Synthetic Paycheck",
                amount=Decimal("2000.00"),
            ),
        )
    )
    db_session.commit()

    summary = build_monthly_summary(db_session, AUGUST)

    assert summary.planned_income == Decimal("2000.00")
    assert summary.actual_inflows == Decimal("1500.00")
    assert summary.total_spending == Decimal("110.00")
    assert summary.available_after_spending == Decimal("1890.00")
    assert summary.spending_percent == Decimal("5.5")
    assert summary.remaining_percent == Decimal("94.5")
    assert summary.uncategorized_count == 2
    assert [(item.name, item.spent) for item in summary.category_spending] == [
        ("Synthetic Groceries", Decimal("80.00")),
        ("Uncategorized", Decimal("30.00")),
    ]
    progress = summary.budget_progress[0]
    assert progress.budget_id == budget.id
    assert progress.spent == Decimal("80.00")
    assert progress.remaining == Decimal("-5.00")
    assert progress.percent_used == Decimal("106.7")
    assert progress.overspent is True


def test_zero_income_has_no_percentage(db_session: Session) -> None:
    summary = build_monthly_summary(db_session, AUGUST)

    assert summary.planned_income == Decimal("0.00")
    assert summary.total_spending == Decimal("0.00")
    assert summary.spending_percent is None
    assert summary.remaining_percent is None
    assert summary.category_spending == []
    assert summary.budget_progress == []


def test_builds_ordered_monthly_trends_with_empty_months(db_session: Session) -> None:
    account = Account(
        name="Synthetic Checking",
        institution="Example Credit Union",
        account_type=AccountType.CHECKING,
        currency="USD",
    )
    expense = Category(name="Synthetic Groceries", kind=CategoryKind.EXPENSE)
    income_category = Category(name="Synthetic Income", kind=CategoryKind.INCOME)
    transfer = Category(name="Synthetic Transfer", kind=CategoryKind.TRANSFER)
    db_session.add_all((account, expense, income_category, transfer))
    db_session.flush()

    add_transaction(
        db_session,
        account,
        amount="-125.50",
        category=expense,
        posted_date=date(2026, 7, 20),
    )
    add_transaction(
        db_session,
        account,
        amount="900.00",
        category=income_category,
        posted_date=date(2026, 7, 15),
    )
    add_transaction(db_session, account, amount="-40.25", posted_date=date(2026, 8, 5))
    add_transaction(
        db_session,
        account,
        amount="-500.00",
        category=transfer,
        posted_date=date(2026, 8, 6),
    )
    add_transaction(
        db_session,
        account,
        amount="-99.00",
        category=expense,
        posted_date=date(2026, 8, 7),
        excluded=True,
    )
    db_session.add_all(
        (
            MonthlyIncome(
                month=date(2026, 7, 1),
                description="Synthetic July income",
                amount=Decimal("1000.00"),
            ),
            MonthlyIncome(
                month=AUGUST,
                description="Synthetic August income",
                amount=Decimal("1100.00"),
            ),
        )
    )
    db_session.commit()

    trends = build_monthly_trends(db_session, AUGUST, 3)

    assert trends.start_month == date(2026, 6, 1)
    assert trends.end_month == AUGUST
    assert [point.month for point in trends.months] == [
        date(2026, 6, 1),
        date(2026, 7, 1),
        AUGUST,
    ]
    assert [point.planned_income for point in trends.months] == [
        Decimal("0.00"),
        Decimal("1000.00"),
        Decimal("1100.00"),
    ]
    assert [point.actual_inflows for point in trends.months] == [
        Decimal("0.00"),
        Decimal("900.00"),
        Decimal("0.00"),
    ]
    assert [point.total_spending for point in trends.months] == [
        Decimal("0.00"),
        Decimal("125.50"),
        Decimal("40.25"),
    ]
