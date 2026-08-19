import uuid
from calendar import monthrange
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Category, CategoryKind, MonthlyBudget, MonthlyIncome, Transaction
from app.schemas.monthly_summary import (
    BudgetProgressSummary,
    CategorySpendingSummary,
    MonthlySummaryResponse,
    MonthlyTrendPoint,
    MonthlyTrendsResponse,
)

ZERO = Decimal("0.00")
PERCENT_QUANTUM = Decimal("0.1")
UNCATEGORIZED_COLOR = "#A3AAA7"


def _next_month(month: date) -> date:
    return month + timedelta(days=monthrange(month.year, month.month)[1])


def _shift_month(month: date, offset: int) -> date:
    month_index = month.year * 12 + month.month - 1 + offset
    year, zero_based_month = divmod(month_index, 12)
    return date(year, zero_based_month + 1, 1)


def _percent(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator == 0:
        return None
    return ((numerator / denominator) * 100).quantize(
        PERCENT_QUANTUM, rounding=ROUND_HALF_UP
    )


def build_monthly_summary(session: Session, month: date) -> MonthlySummaryResponse:
    end = _next_month(month)
    categories = {category.id: category for category in session.scalars(select(Category))}
    transaction_rows = list(
        session.scalars(
            select(Transaction).where(
                Transaction.posted_date >= month,
                Transaction.posted_date < end,
                Transaction.excluded_from_budget.is_(False),
            )
        )
    )

    category_net: dict[uuid.UUID, Decimal] = {}
    uncategorized_spending = ZERO
    actual_inflows = ZERO
    uncategorized_count = 0

    for transaction in transaction_rows:
        if transaction.category_id is None:
            uncategorized_count += 1
            if transaction.amount < 0:
                uncategorized_spending += -transaction.amount
            elif transaction.amount > 0:
                actual_inflows += transaction.amount
            continue
        category = categories.get(transaction.category_id)
        if category is None or category.kind == CategoryKind.TRANSFER:
            continue
        if category.kind == CategoryKind.INCOME:
            if transaction.amount > 0:
                actual_inflows += transaction.amount
            continue
        category_net[category.id] = category_net.get(category.id, ZERO) + transaction.amount

    spending_by_category = {
        category_id: max(ZERO, -amount) for category_id, amount in category_net.items()
    }
    total_spending = sum(spending_by_category.values(), start=uncategorized_spending)
    planned_income = sum(
        session.scalars(
            select(MonthlyIncome.amount).where(MonthlyIncome.month == month)
        ),
        start=ZERO,
    )
    available = planned_income - total_spending

    category_spending = [
        CategorySpendingSummary(
            category_id=category_id,
            name=categories[category_id].name,
            color=categories[category_id].color,
            spent=spent,
        )
        for category_id, spent in spending_by_category.items()
        if spent > 0
    ]
    if uncategorized_spending > 0:
        category_spending.append(
            CategorySpendingSummary(
                category_id=None,
                name="Uncategorized",
                color=UNCATEGORIZED_COLOR,
                spent=uncategorized_spending,
            )
        )
    category_spending.sort(key=lambda item: (-item.spent, item.name.casefold()))

    budgets = list(
        session.scalars(
            select(MonthlyBudget)
            .where(MonthlyBudget.month == month)
            .order_by(MonthlyBudget.category_id)
        )
    )
    budget_progress: list[BudgetProgressSummary] = []
    for budget in budgets:
        category = categories.get(budget.category_id)
        if category is None:
            continue
        spent = spending_by_category.get(category.id, ZERO)
        remaining = budget.limit_amount - spent
        budget_progress.append(
            BudgetProgressSummary(
                budget_id=budget.id,
                category_id=category.id,
                name=category.name,
                color=category.color,
                limit_amount=budget.limit_amount,
                spent=spent,
                remaining=remaining,
                percent_used=_percent(spent, budget.limit_amount),
                overspent=spent > budget.limit_amount,
            )
        )
    budget_progress.sort(key=lambda item: item.name.casefold())

    return MonthlySummaryResponse(
        month=month,
        planned_income=planned_income,
        actual_inflows=actual_inflows,
        total_spending=total_spending,
        available_after_spending=available,
        spending_percent=_percent(total_spending, planned_income),
        remaining_percent=_percent(available, planned_income),
        uncategorized_count=uncategorized_count,
        category_spending=category_spending,
        budget_progress=budget_progress,
    )


def build_monthly_trends(
    session: Session, end_month: date, month_count: int
) -> MonthlyTrendsResponse:
    start_month = _shift_month(end_month, -(month_count - 1))
    points: list[MonthlyTrendPoint] = []
    for offset in range(month_count):
        summary = build_monthly_summary(session, _shift_month(start_month, offset))
        points.append(
            MonthlyTrendPoint(
                month=summary.month,
                planned_income=summary.planned_income,
                actual_inflows=summary.actual_inflows,
                total_spending=summary.total_spending,
            )
        )
    return MonthlyTrendsResponse(
        start_month=start_month,
        end_month=end_month,
        months=points,
    )
