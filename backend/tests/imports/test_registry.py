import pytest

from app.imports.registry import identify_adapter
from app.imports.types import UnsupportedStatementError


def test_identifies_navy_federal_statement() -> None:
    adapter = identify_adapter("Navy Federal Credit Union\nStatement for checking")

    assert adapter.name == "navy_federal_checking_v1"


def test_rejects_unknown_statement() -> None:
    with pytest.raises(UnsupportedStatementError):
        identify_adapter("Example Community Bank\nMonthly account statement")

