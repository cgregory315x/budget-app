from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Protocol

from app.db.models import AccountType


@dataclass(frozen=True, slots=True)
class CandidateTransaction:
    posted_date: date
    description: str
    amount: Decimal
    source_text: str
    confidence: Decimal
    warnings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ParsedStatement:
    institution: str
    account_hint: str | None
    period_start: date | None
    period_end: date | None
    transactions: tuple[CandidateTransaction, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)


class StatementAdapter(Protocol):
    name: str
    account_type: AccountType

    def can_parse(self, statement_text: str) -> bool: ...

    def parse(self, statement_text: str) -> ParsedStatement: ...


class UnsupportedStatementError(ValueError):
    """Raised when no registered adapter recognizes a statement."""


class StatementParseError(ValueError):
    """Raised when a recognized statement cannot be parsed safely."""
