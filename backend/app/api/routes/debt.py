import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.debt import (
    LoanBalanceCreate,
    LoanBalanceResponse,
    LoanBalanceUpdate,
    LoanTermsCreate,
    LoanTermsResponse,
    LoanTermsUpdate,
)
from app.services import loans

router = APIRouter()
SessionDependency = Annotated[Session, Depends(get_db_session)]


def _loan_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Loan not found")


def _balance_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Balance snapshot not found")


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=409, detail=detail)


@router.get("", response_model=list[LoanTermsResponse])
def list_all(session: SessionDependency) -> list[LoanTermsResponse]:
    return [LoanTermsResponse.model_validate(item) for item in loans.list_loans(session)]


@router.post("", response_model=LoanTermsResponse, status_code=status.HTTP_201_CREATED)
def create(data: LoanTermsCreate, session: SessionDependency) -> LoanTermsResponse:
    try:
        loan = loans.create_loan(session, data)
    except loans.LoanAccountError as error:
        raise _conflict("Loan terms require an existing loan account") from error
    except loans.LoanConflictError as error:
        raise _conflict("The account already has loan terms") from error
    return LoanTermsResponse.model_validate(loan)


@router.get("/{loan_id}", response_model=LoanTermsResponse)
def get(loan_id: uuid.UUID, session: SessionDependency) -> LoanTermsResponse:
    try:
        loan = loans.get_loan(session, loan_id)
    except loans.LoanNotFoundError as error:
        raise _loan_not_found() from error
    return LoanTermsResponse.model_validate(loan)


@router.patch("/{loan_id}", response_model=LoanTermsResponse)
def update(
    loan_id: uuid.UUID, data: LoanTermsUpdate, session: SessionDependency
) -> LoanTermsResponse:
    try:
        loan = loans.update_loan(session, loan_id, data)
    except loans.LoanNotFoundError as error:
        raise _loan_not_found() from error
    return LoanTermsResponse.model_validate(loan)


@router.delete("/{loan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(loan_id: uuid.UUID, session: SessionDependency) -> Response:
    try:
        loans.delete_loan(session, loan_id)
    except loans.LoanNotFoundError as error:
        raise _loan_not_found() from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{loan_id}/balances", response_model=list[LoanBalanceResponse])
def list_balance_history(
    loan_id: uuid.UUID, session: SessionDependency
) -> list[LoanBalanceResponse]:
    try:
        snapshots = loans.list_balances(session, loan_id)
    except loans.LoanNotFoundError as error:
        raise _loan_not_found() from error
    return [LoanBalanceResponse.model_validate(item) for item in snapshots]


@router.post(
    "/{loan_id}/balances",
    response_model=LoanBalanceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_balance(
    loan_id: uuid.UUID, data: LoanBalanceCreate, session: SessionDependency
) -> LoanBalanceResponse:
    try:
        snapshot = loans.create_balance(session, loan_id, data)
    except loans.LoanNotFoundError as error:
        raise _loan_not_found() from error
    except loans.BalanceConflictError as error:
        raise _conflict("A balance already exists for this loan and date") from error
    return LoanBalanceResponse.model_validate(snapshot)


@router.patch(
    "/{loan_id}/balances/{balance_id}", response_model=LoanBalanceResponse
)
def update_balance(
    loan_id: uuid.UUID,
    balance_id: uuid.UUID,
    data: LoanBalanceUpdate,
    session: SessionDependency,
) -> LoanBalanceResponse:
    try:
        snapshot = loans.update_balance(session, loan_id, balance_id, data)
    except loans.BalanceNotFoundError as error:
        raise _balance_not_found() from error
    except loans.BalanceConflictError as error:
        raise _conflict("A balance already exists for this loan and date") from error
    return LoanBalanceResponse.model_validate(snapshot)


@router.delete(
    "/{loan_id}/balances/{balance_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_balance(
    loan_id: uuid.UUID, balance_id: uuid.UUID, session: SessionDependency
) -> Response:
    try:
        loans.delete_balance(session, loan_id, balance_id)
    except loans.BalanceNotFoundError as error:
        raise _balance_not_found() from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
