from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Account, Category, MonthlyBudget, MonthlyIncome, Transaction
from app.services.demo_data import DemoDataNotEmptyError, seed_demo_data
from app.services.monthly_summary import build_monthly_trends


def test_seeds_six_months_of_safe_reporting_data(db_session: Session) -> None:
    end_month = date(2026, 8, 1)

    seed_demo_data(db_session, end_month)
    db_session.commit()

    assert db_session.scalar(select(func.count()).select_from(Account)) == 2
    assert db_session.scalar(select(func.count()).select_from(Category)) == 7
    assert db_session.scalar(select(func.count()).select_from(MonthlyIncome)) == 6
    assert db_session.scalar(select(func.count()).select_from(MonthlyBudget)) == 30
    assert db_session.scalar(select(func.count()).select_from(Transaction)) == 54
    trends = build_monthly_trends(db_session, end_month, 6)
    assert trends.start_month == date(2026, 3, 1)
    assert [point.planned_income for point in trends.months] == [Decimal("4800.00")] * 6
    assert trends.months[-1].actual_inflows == Decimal("4600.00")
    assert trends.months[-1].total_spending == Decimal("2875.40")


def test_refuses_to_seed_when_any_user_data_exists(db_session: Session) -> None:
    existing = MonthlyIncome(
        month=date(2026, 8, 1),
        description="Existing user data",
        amount=Decimal("1.00"),
    )
    db_session.add(existing)
    db_session.commit()

    with pytest.raises(DemoDataNotEmptyError, match="completely empty"):
        seed_demo_data(db_session, date(2026, 8, 1))

    assert db_session.scalar(select(func.count()).select_from(Account)) == 0
    assert db_session.scalar(select(func.count()).select_from(MonthlyIncome)) == 1


def test_requires_first_day_for_service_calls(db_session: Session) -> None:
    with pytest.raises(ValueError, match="first day"):
        seed_demo_data(db_session, date(2026, 8, 19))
