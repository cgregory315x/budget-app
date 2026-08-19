import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Account, AccountType, LoanBalanceSnapshot, LoanTerms
from app.schemas.debt import (
    LoanBalanceCreate,
    LoanBalanceUpdate,
    LoanTermsCreate,
    LoanTermsUpdate,
)


class LoanNotFoundError(Exception):
    pass


class LoanAccountError(Exception):
    pass


class LoanConflictError(Exception):
    pass


class BalanceNotFoundError(Exception):
    pass


class BalanceConflictError(Exception):
    pass


def list_loans(session: Session) -> list[LoanTerms]:
    statement = select(LoanTerms).order_by(LoanTerms.created_at, LoanTerms.id)
    return list(session.scalars(statement))


def get_loan(session: Session, loan_id: uuid.UUID) -> LoanTerms:
    loan = session.get(LoanTerms, loan_id)
    if loan is None:
        raise LoanNotFoundError
    return loan


def _commit_loan(session: Session, loan: LoanTerms) -> LoanTerms:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise LoanConflictError from error
    session.refresh(loan)
    return loan


def create_loan(session: Session, data: LoanTermsCreate) -> LoanTerms:
    account = session.get(Account, data.account_id)
    if account is None or account.account_type != AccountType.LOAN:
        raise LoanAccountError
    loan = LoanTerms(**data.model_dump())
    session.add(loan)
    return _commit_loan(session, loan)


def update_loan(
    session: Session, loan_id: uuid.UUID, data: LoanTermsUpdate
) -> LoanTerms:
    loan = get_loan(session, loan_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(loan, field, value)
    return _commit_loan(session, loan)


def delete_loan(session: Session, loan_id: uuid.UUID) -> None:
    loan = get_loan(session, loan_id)
    for snapshot in list(loan.balance_snapshots):
        session.delete(snapshot)
    session.delete(loan)
    session.commit()


def list_balances(session: Session, loan_id: uuid.UUID) -> list[LoanBalanceSnapshot]:
    get_loan(session, loan_id)
    statement = (
        select(LoanBalanceSnapshot)
        .where(LoanBalanceSnapshot.loan_terms_id == loan_id)
        .order_by(
            LoanBalanceSnapshot.as_of_date.desc(), LoanBalanceSnapshot.id
        )
    )
    return list(session.scalars(statement))


def get_balance(
    session: Session, loan_id: uuid.UUID, balance_id: uuid.UUID
) -> LoanBalanceSnapshot:
    snapshot = session.get(LoanBalanceSnapshot, balance_id)
    if snapshot is None or snapshot.loan_terms_id != loan_id:
        raise BalanceNotFoundError
    return snapshot


def _commit_balance(
    session: Session, snapshot: LoanBalanceSnapshot
) -> LoanBalanceSnapshot:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise BalanceConflictError from error
    session.refresh(snapshot)
    return snapshot


def create_balance(
    session: Session, loan_id: uuid.UUID, data: LoanBalanceCreate
) -> LoanBalanceSnapshot:
    get_loan(session, loan_id)
    snapshot = LoanBalanceSnapshot(loan_terms_id=loan_id, **data.model_dump())
    session.add(snapshot)
    return _commit_balance(session, snapshot)


def update_balance(
    session: Session,
    loan_id: uuid.UUID,
    balance_id: uuid.UUID,
    data: LoanBalanceUpdate,
) -> LoanBalanceSnapshot:
    snapshot = get_balance(session, loan_id, balance_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(snapshot, field, value)
    return _commit_balance(session, snapshot)


def delete_balance(session: Session, loan_id: uuid.UUID, balance_id: uuid.UUID) -> None:
    snapshot = get_balance(session, loan_id, balance_id)
    session.delete(snapshot)
    session.commit()
