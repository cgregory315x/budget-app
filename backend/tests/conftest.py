from collections.abc import Generator
from typing import cast

import pytest
from sqlalchemy import Table, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Account, Category


@pytest.fixture
def db_session() -> Generator[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[cast(Table, Account.__table__), cast(Table, Category.__table__)],
    )
    test_session = sessionmaker[Session](
        bind=engine, autoflush=False, expire_on_commit=False
    )

    with test_session() as session:
        yield session
    engine.dispose()
