import uuid
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.models import Category, CategoryKind
from app.main import create_app
from app.schemas.monthly_planning import (
    MonthlyBudgetCreate,
    MonthlyBudgetUpdate,
    MonthlyIncomeCreate,
    MonthlyIncomeUpdate,
)
from app.services import monthly_planning

AUGUST = date(2026, 8, 1)
SEPTEMBER = date(2026, 9, 1)


def expense_category(session: Session, name: str = "Synthetic Groceries") -> Category:
    category = Category(name=name, kind=CategoryKind.EXPENSE)
    session.add(category)
    session.commit()
    return category


def test_monthly_planning_api_contract_is_registered() -> None:
    paths = create_app().openapi()["paths"]

    assert set(paths["/api/v1/budgets"]) == {"get", "post"}
    assert set(paths["/api/v1/budgets/{budget_id}"]) == {"get", "patch", "delete"}
    assert set(paths["/api/v1/income"]) == {"get", "post"}
    assert set(paths["/api/v1/income/{income_id}"]) == {"get", "patch", "delete"}


def test_create_filter_update_and_delete_budget(db_session: Session) -> None:
    category = expense_category(db_session)
    budget = monthly_planning.create_budget(
        db_session,
        MonthlyBudgetCreate(
            month=AUGUST, category_id=category.id, limit_amount=Decimal("450.00")
        ),
    )
    monthly_planning.create_budget(
        db_session,
        MonthlyBudgetCreate(
            month=SEPTEMBER, category_id=category.id, limit_amount=Decimal("475.00")
        ),
    )

    assert monthly_planning.list_budgets(db_session, month=AUGUST) == [budget]
    updated = monthly_planning.update_budget(
        db_session,
        budget.id,
        MonthlyBudgetUpdate(limit_amount=Decimal("500.00")),
    )
    assert updated.limit_amount == Decimal("500.00")

    monthly_planning.delete_budget(db_session, budget.id)
    with pytest.raises(monthly_planning.BudgetNotFoundError):
        monthly_planning.get_budget(db_session, budget.id)


def test_duplicate_budget_is_rejected(db_session: Session) -> None:
    category = expense_category(db_session)
    data = MonthlyBudgetCreate(
        month=AUGUST, category_id=category.id, limit_amount=Decimal("450.00")
    )
    monthly_planning.create_budget(db_session, data)

    with pytest.raises(monthly_planning.BudgetConflictError):
        monthly_planning.create_budget(db_session, data)


@pytest.mark.parametrize("kind", [CategoryKind.INCOME, CategoryKind.TRANSFER])
def test_budget_requires_active_expense_category(
    db_session: Session, kind: CategoryKind
) -> None:
    category = Category(name=f"Synthetic {kind.value}", kind=kind)
    db_session.add(category)
    db_session.commit()
    data = MonthlyBudgetCreate(
        month=AUGUST, category_id=category.id, limit_amount=Decimal("100.00")
    )

    with pytest.raises(monthly_planning.BudgetCategoryError):
        monthly_planning.create_budget(db_session, data)

    category.kind = CategoryKind.EXPENSE
    category.archived = True
    db_session.commit()
    with pytest.raises(monthly_planning.BudgetCategoryError):
        monthly_planning.create_budget(db_session, data)


def test_create_filter_update_and_delete_income(db_session: Session) -> None:
    income = monthly_planning.create_income(
        db_session,
        MonthlyIncomeCreate(
            month=AUGUST,
            description="Synthetic Paycheck",
            amount=Decimal("3200.00"),
        ),
    )
    monthly_planning.create_income(
        db_session,
        MonthlyIncomeCreate(
            month=SEPTEMBER,
            description="Synthetic Paycheck",
            amount=Decimal("3250.00"),
        ),
    )

    assert monthly_planning.list_income(db_session, month=AUGUST) == [income]
    updated = monthly_planning.update_income(
        db_session,
        income.id,
        MonthlyIncomeUpdate(
            description="Updated Synthetic Paycheck", amount=Decimal("3300.00")
        ),
    )
    assert updated.description == "Updated Synthetic Paycheck"
    assert updated.amount == Decimal("3300.00")

    monthly_planning.delete_income(db_session, income.id)
    with pytest.raises(monthly_planning.IncomeNotFoundError):
        monthly_planning.get_income(db_session, income.id)


@pytest.mark.parametrize(
    ("schema", "payload"),
    [
        (
            MonthlyBudgetCreate,
            {"month": "2026-08-02", "category_id": str(uuid.uuid4()), "limit_amount": "1"},
        ),
        (
            MonthlyBudgetCreate,
            {"month": "2026-08-01", "category_id": str(uuid.uuid4()), "limit_amount": "-1"},
        ),
        (
            MonthlyIncomeCreate,
            {"month": "2026-08-02", "description": "Example", "amount": "1"},
        ),
        (
            MonthlyIncomeCreate,
            {"month": "2026-08-01", "description": " ", "amount": "0"},
        ),
    ],
)
def test_invalid_monthly_entry_is_rejected(
    schema: type[MonthlyBudgetCreate] | type[MonthlyIncomeCreate],
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        schema.model_validate(payload)


def test_empty_updates_are_rejected() -> None:
    with pytest.raises(ValidationError):
        MonthlyBudgetUpdate.model_validate({})
    with pytest.raises(ValidationError):
        MonthlyIncomeUpdate.model_validate({})
