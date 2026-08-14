import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.monthly_planning import (
    MonthlyBudgetCreate,
    MonthlyBudgetResponse,
    MonthlyBudgetUpdate,
    MonthlyIncomeCreate,
    MonthlyIncomeResponse,
    MonthlyIncomeUpdate,
    validate_month,
)
from app.services import monthly_planning

budget_router = APIRouter()
income_router = APIRouter()
SessionDependency = Annotated[Session, Depends(get_db_session)]


def _month_filter(month: date | None) -> date | None:
    if month is None:
        return None
    try:
        return validate_month(month)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error


@budget_router.get("", response_model=list[MonthlyBudgetResponse])
def list_budgets(
    session: SessionDependency,
    month: Annotated[date | None, Query()] = None,
) -> list[MonthlyBudgetResponse]:
    return [
        MonthlyBudgetResponse.model_validate(budget)
        for budget in monthly_planning.list_budgets(
            session, month=_month_filter(month)
        )
    ]


@budget_router.post(
    "", response_model=MonthlyBudgetResponse, status_code=status.HTTP_201_CREATED
)
def create_budget(
    data: MonthlyBudgetCreate, session: SessionDependency
) -> MonthlyBudgetResponse:
    try:
        budget = monthly_planning.create_budget(session, data)
    except monthly_planning.BudgetCategoryError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Budget category must be an active expense category",
        ) from error
    except monthly_planning.BudgetConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A budget already exists for that category and month",
        ) from error
    return MonthlyBudgetResponse.model_validate(budget)


@budget_router.get("/{budget_id}", response_model=MonthlyBudgetResponse)
def get_budget(budget_id: uuid.UUID, session: SessionDependency) -> MonthlyBudgetResponse:
    try:
        budget = monthly_planning.get_budget(session, budget_id)
    except monthly_planning.BudgetNotFoundError as error:
        raise HTTPException(status_code=404, detail="Monthly budget not found") from error
    return MonthlyBudgetResponse.model_validate(budget)


@budget_router.patch("/{budget_id}", response_model=MonthlyBudgetResponse)
def update_budget(
    budget_id: uuid.UUID,
    data: MonthlyBudgetUpdate,
    session: SessionDependency,
) -> MonthlyBudgetResponse:
    try:
        budget = monthly_planning.update_budget(session, budget_id, data)
    except monthly_planning.BudgetNotFoundError as error:
        raise HTTPException(status_code=404, detail="Monthly budget not found") from error
    except monthly_planning.BudgetCategoryError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Budget category must be an active expense category",
        ) from error
    except monthly_planning.BudgetConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A budget already exists for that category and month",
        ) from error
    return MonthlyBudgetResponse.model_validate(budget)


@budget_router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(budget_id: uuid.UUID, session: SessionDependency) -> Response:
    try:
        monthly_planning.delete_budget(session, budget_id)
    except monthly_planning.BudgetNotFoundError as error:
        raise HTTPException(status_code=404, detail="Monthly budget not found") from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@income_router.get("", response_model=list[MonthlyIncomeResponse])
def list_income(
    session: SessionDependency,
    month: Annotated[date | None, Query()] = None,
) -> list[MonthlyIncomeResponse]:
    return [
        MonthlyIncomeResponse.model_validate(income)
        for income in monthly_planning.list_income(
            session, month=_month_filter(month)
        )
    ]


@income_router.post(
    "", response_model=MonthlyIncomeResponse, status_code=status.HTTP_201_CREATED
)
def create_income(
    data: MonthlyIncomeCreate, session: SessionDependency
) -> MonthlyIncomeResponse:
    return MonthlyIncomeResponse.model_validate(
        monthly_planning.create_income(session, data)
    )


@income_router.get("/{income_id}", response_model=MonthlyIncomeResponse)
def get_income(income_id: uuid.UUID, session: SessionDependency) -> MonthlyIncomeResponse:
    try:
        income = monthly_planning.get_income(session, income_id)
    except monthly_planning.IncomeNotFoundError as error:
        raise HTTPException(status_code=404, detail="Monthly income not found") from error
    return MonthlyIncomeResponse.model_validate(income)


@income_router.patch("/{income_id}", response_model=MonthlyIncomeResponse)
def update_income(
    income_id: uuid.UUID,
    data: MonthlyIncomeUpdate,
    session: SessionDependency,
) -> MonthlyIncomeResponse:
    try:
        income = monthly_planning.update_income(session, income_id, data)
    except monthly_planning.IncomeNotFoundError as error:
        raise HTTPException(status_code=404, detail="Monthly income not found") from error
    return MonthlyIncomeResponse.model_validate(income)


@income_router.delete("/{income_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_income(income_id: uuid.UUID, session: SessionDependency) -> Response:
    try:
        monthly_planning.delete_income(session, income_id)
    except monthly_planning.IncomeNotFoundError as error:
        raise HTTPException(status_code=404, detail="Monthly income not found") from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
