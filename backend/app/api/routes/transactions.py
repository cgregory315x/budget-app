import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.transactions import (
    TransactionCreate,
    TransactionResponse,
    TransactionUpdate,
)
from app.services import transactions

router = APIRouter()
SessionDependency = Annotated[Session, Depends(get_db_session)]


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")


def _reference_error(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


@router.get("", response_model=list[TransactionResponse])
def list_all(
    session: SessionDependency,
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    posted_from: date | None = None,
    posted_to: date | None = None,
    uncategorized: bool | None = None,
    excluded: bool | None = None,
    search: Annotated[str | None, Query(max_length=120)] = None,
) -> list[TransactionResponse]:
    if category_id is not None and uncategorized is True:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="category_id cannot be combined with uncategorized=true",
        )
    if posted_from is not None and posted_to is not None and posted_from > posted_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="posted_from must not be after posted_to",
        )
    filters = transactions.TransactionFilters(
        account_id=account_id,
        category_id=category_id,
        posted_from=posted_from,
        posted_to=posted_to,
        uncategorized=uncategorized,
        excluded=excluded,
        search=search,
    )
    return [
        TransactionResponse.model_validate(transaction)
        for transaction in transactions.list_transactions(session, filters)
    ]


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create(data: TransactionCreate, session: SessionDependency) -> TransactionResponse:
    try:
        transaction = transactions.create_transaction(session, data)
    except transactions.TransactionReferenceError as error:
        raise _reference_error(str(error)) from error
    except transactions.TransactionConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The transaction conflicts with an existing record",
        ) from error
    return TransactionResponse.model_validate(transaction)


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get(transaction_id: uuid.UUID, session: SessionDependency) -> TransactionResponse:
    try:
        transaction = transactions.get_transaction(session, transaction_id)
    except transactions.TransactionNotFoundError as error:
        raise _not_found() from error
    return TransactionResponse.model_validate(transaction)


@router.patch("/{transaction_id}", response_model=TransactionResponse)
def update(
    transaction_id: uuid.UUID,
    data: TransactionUpdate,
    session: SessionDependency,
) -> TransactionResponse:
    try:
        transaction = transactions.update_transaction(session, transaction_id, data)
    except transactions.TransactionNotFoundError as error:
        raise _not_found() from error
    except transactions.TransactionReferenceError as error:
        raise _reference_error(str(error)) from error
    except transactions.TransactionConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The transaction conflicts with an existing record",
        ) from error
    return TransactionResponse.model_validate(transaction)


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(transaction_id: uuid.UUID, session: SessionDependency) -> Response:
    try:
        transactions.delete_transaction(session, transaction_id)
    except transactions.TransactionNotFoundError as error:
        raise _not_found() from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
