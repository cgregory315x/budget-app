import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class CategorySpendingSummary(BaseModel):
    category_id: uuid.UUID | None
    name: str
    color: str
    spent: Decimal


class BudgetProgressSummary(BaseModel):
    budget_id: uuid.UUID
    category_id: uuid.UUID
    name: str
    color: str
    limit_amount: Decimal
    spent: Decimal
    remaining: Decimal
    percent_used: Decimal | None
    overspent: bool


class MonthlySummaryResponse(BaseModel):
    month: date
    planned_income: Decimal
    actual_inflows: Decimal
    total_spending: Decimal
    available_after_spending: Decimal
    spending_percent: Decimal | None
    remaining_percent: Decimal | None
    uncategorized_count: int
    category_spending: list[CategorySpendingSummary]
    budget_progress: list[BudgetProgressSummary]


class MonthlyTrendPoint(BaseModel):
    month: date
    planned_income: Decimal
    actual_inflows: Decimal
    total_spending: Decimal


class MonthlyTrendsResponse(BaseModel):
    start_month: date
    end_month: date
    months: list[MonthlyTrendPoint]
