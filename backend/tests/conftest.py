from collections.abc import Generator
from typing import cast

import pytest
from sqlalchemy import Table, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import (
    Account,
    Category,
    LoanBalanceSnapshot,
    LoanTerms,
    MerchantRule,
    MonthlyBudget,
    MonthlyIncome,
    StatementImport,
    Transaction,
)


@pytest.fixture
def db_session() -> Generator[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            cast(Table, Account.__table__),
            cast(Table, Category.__table__),
            cast(Table, LoanTerms.__table__),
            cast(Table, LoanBalanceSnapshot.__table__),
            cast(Table, StatementImport.__table__),
            cast(Table, Transaction.__table__),
            cast(Table, MerchantRule.__table__),
            cast(Table, MonthlyBudget.__table__),
            cast(Table, MonthlyIncome.__table__),
        ],
    )
    test_session = sessionmaker[Session](
        bind=engine, autoflush=False, expire_on_commit=False
    )

    with test_session() as session:
        yield session
    engine.dispose()
