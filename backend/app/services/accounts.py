import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Account
from app.schemas.accounts import AccountCreate, AccountUpdate


class AccountNotFoundError(Exception):
    pass


def list_accounts(session: Session, *, include_archived: bool = False) -> list[Account]:
    statement = select(Account)
    if not include_archived:
        statement = statement.where(Account.archived.is_(False))
    statement = statement.order_by(func.lower(Account.name), Account.id)
    return list(session.scalars(statement))


def get_account(session: Session, account_id: uuid.UUID) -> Account:
    account = session.get(Account, account_id)
    if account is None:
        raise AccountNotFoundError
    return account


def create_account(session: Session, data: AccountCreate) -> Account:
    account = Account(**data.model_dump())
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def update_account(session: Session, account_id: uuid.UUID, data: AccountUpdate) -> Account:
    account = get_account(session, account_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    session.commit()
    session.refresh(account)
    return account


def archive_account(session: Session, account_id: uuid.UUID) -> None:
    account = get_account(session, account_id)
    if not account.archived:
        account.archived = True
        session.commit()
