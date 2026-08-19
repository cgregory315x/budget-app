from datetime import date
from decimal import Decimal

import pytest

from app.imports.adapters.navy_federal_credit_card import NavyFederalCreditCardAdapter
from app.imports.types import StatementParseError

SYNTHETIC_STATEMENT = """NAVY FEDERAL CREDIT UNION
CREDIT CARD xxxx xxxx xxxx 1234
TRANSACTIONS
Trans Date Post Date Reference No. Description Amount
08/02/26 08/03/26 12345678901234567890123 SYNTHETIC MARKET $45.67
08/04/26 08/05/26 98765432109876543210987 ONLINE PAYMENT $125.00
TOTAL New Activity $79.33
FEES
Trans Date Post Date Reference No. Description Amount
08/06/26 08/06/26 11112222333344445555666 LATE FEE $20.00
TOTALFEES $20.00
"""


def test_parses_credit_card_rows_and_normalizes_amount_signs() -> None:
    parsed = NavyFederalCreditCardAdapter().parse(SYNTHETIC_STATEMENT)

    assert parsed.account_hint == "…1234"
    assert parsed.period_start == date(2026, 8, 3)
    assert parsed.period_end == date(2026, 8, 6)
    assert [(row.description, row.amount) for row in parsed.transactions] == [
        ("SYNTHETIC MARKET", Decimal("-45.67")),
        ("ONLINE PAYMENT", Decimal("125.00")),
        ("LATE FEE", Decimal("-20.00")),
    ]
    assert all(row.confidence == Decimal("0.850") for row in parsed.transactions)
    assert all(row.warnings for row in parsed.transactions)


def test_warns_and_skips_malformed_credit_card_rows() -> None:
    parsed = NavyFederalCreditCardAdapter().parse(
        SYNTHETIC_STATEMENT.replace(
            "08/02/26 08/03/26 12345678901234567890123 SYNTHETIC MARKET $45.67",
            "08/02/26 MALFORMED ROW",
        )
    )

    assert parsed.warnings == ("Skipped a malformed credit card transaction row",)
    assert len(parsed.transactions) == 2


def test_requires_supported_credit_card_rows() -> None:
    with pytest.raises(StatementParseError, match="No supported credit card transaction rows"):
        NavyFederalCreditCardAdapter().parse(
            """NAVY FEDERAL CREDIT UNION
Trans Date Post Date Reference No. Description Amount"""
        )
