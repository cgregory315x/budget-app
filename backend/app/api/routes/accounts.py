import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.accounts import AccountCreate, AccountResponse, AccountUpdate
from app.services import accounts

router = APIRouter()
SessionDependency = Annotated[Session, Depends(get_db_session)]


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")


@router.get("", response_model=list[AccountResponse])
def list_all(
    session: SessionDependency,
    include_archived: Annotated[bool, Query()] = False,
) -> list[AccountResponse]:
    return [
        AccountResponse.model_validate(account)
        for account in accounts.list_accounts(session, include_archived=include_archived)
    ]


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def create(data: AccountCreate, session: SessionDependency) -> AccountResponse:
    return AccountResponse.model_validate(accounts.create_account(session, data))


@router.get("/{account_id}", response_model=AccountResponse)
def get(account_id: uuid.UUID, session: SessionDependency) -> AccountResponse:
    try:
        account = accounts.get_account(session, account_id)
    except accounts.AccountNotFoundError as error:
        raise _not_found() from error
    return AccountResponse.model_validate(account)


@router.patch("/{account_id}", response_model=AccountResponse)
def update(
    account_id: uuid.UUID, data: AccountUpdate, session: SessionDependency
) -> AccountResponse:
    try:
        account = accounts.update_account(session, account_id, data)
    except accounts.AccountNotFoundError as error:
        raise _not_found() from error
    return AccountResponse.model_validate(account)


@router.delete(
    "/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive an account",
)
def archive(account_id: uuid.UUID, session: SessionDependency) -> Response:
    try:
        accounts.archive_account(session, account_id)
    except accounts.AccountNotFoundError as error:
        raise _not_found() from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
