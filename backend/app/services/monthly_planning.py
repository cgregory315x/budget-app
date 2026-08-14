import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Category, CategoryKind, MonthlyBudget, MonthlyIncome
from app.schemas.monthly_planning import (
    MonthlyBudgetCreate,
    MonthlyBudgetUpdate,
    MonthlyIncomeCreate,
    MonthlyIncomeUpdate,
)


class BudgetNotFoundError(Exception):
    pass


class BudgetConflictError(Exception):
    pass


class BudgetCategoryError(Exception):
    pass


class IncomeNotFoundError(Exception):
    pass


def list_budgets(session: Session, *, month: date | None = None) -> list[MonthlyBudget]:
    statement = select(MonthlyBudget)
    if month is not None:
        statement = statement.where(MonthlyBudget.month == month)
    statement = statement.order_by(MonthlyBudget.month.desc(), MonthlyBudget.category_id)
    return list(session.scalars(statement))


def get_budget(session: Session, budget_id: uuid.UUID) -> MonthlyBudget:
    budget = session.get(MonthlyBudget, budget_id)
    if budget is None:
        raise BudgetNotFoundError
    return budget


def _validate_budget_category(session: Session, category_id: uuid.UUID) -> None:
    category = session.get(Category, category_id)
    if category is None or category.archived or category.kind != CategoryKind.EXPENSE:
        raise BudgetCategoryError


def _commit_budget(session: Session, budget: MonthlyBudget) -> MonthlyBudget:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise BudgetConflictError from error
    session.refresh(budget)
    return budget


def create_budget(session: Session, data: MonthlyBudgetCreate) -> MonthlyBudget:
    _validate_budget_category(session, data.category_id)
    budget = MonthlyBudget(**data.model_dump())
    session.add(budget)
    return _commit_budget(session, budget)


def update_budget(
    session: Session, budget_id: uuid.UUID, data: MonthlyBudgetUpdate
) -> MonthlyBudget:
    budget = get_budget(session, budget_id)
    changes = data.model_dump(exclude_unset=True)
    if "category_id" in changes:
        _validate_budget_category(session, changes["category_id"])
    for field, value in changes.items():
        setattr(budget, field, value)
    return _commit_budget(session, budget)


def delete_budget(session: Session, budget_id: uuid.UUID) -> None:
    budget = get_budget(session, budget_id)
    session.delete(budget)
    session.commit()


def list_income(session: Session, *, month: date | None = None) -> list[MonthlyIncome]:
    statement = select(MonthlyIncome)
    if month is not None:
        statement = statement.where(MonthlyIncome.month == month)
    statement = statement.order_by(MonthlyIncome.month.desc(), MonthlyIncome.created_at)
    return list(session.scalars(statement))


def get_income(session: Session, income_id: uuid.UUID) -> MonthlyIncome:
    income = session.get(MonthlyIncome, income_id)
    if income is None:
        raise IncomeNotFoundError
    return income


def create_income(session: Session, data: MonthlyIncomeCreate) -> MonthlyIncome:
    income = MonthlyIncome(**data.model_dump())
    session.add(income)
    session.commit()
    session.refresh(income)
    return income


def update_income(
    session: Session, income_id: uuid.UUID, data: MonthlyIncomeUpdate
) -> MonthlyIncome:
    income = get_income(session, income_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(income, field, value)
    session.commit()
    session.refresh(income)
    return income


def delete_income(session: Session, income_id: uuid.UUID) -> None:
    income = get_income(session, income_id)
    session.delete(income)
    session.commit()
