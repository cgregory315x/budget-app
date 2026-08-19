from datetime import date
from decimal import Decimal

import pytest

from app.imports.adapters.navy_federal import NavyFederalCheckingAdapter
from app.imports.types import StatementParseError

SYNTHETIC_STATEMENT = """NAVY FEDERAL CREDIT UNION
Checking Account XXXX 1234
Statement Period: 08/01/2026 - 08/31/2026
Transactions
08/02/2026 SYNTHETIC MARKET PURCHASE -$45.67
08/05/2026 SYNTHETIC PAYROLL $1,250.00
08/08/2026 SYNTHETIC ONLINE ORDER ($19.95)
ORDER REFERENCE ABC
Ending Balance $2,000.00
"""


def test_parses_statement_metadata_and_transactions() -> None:
    parsed = NavyFederalCheckingAdapter().parse(SYNTHETIC_STATEMENT)

    assert parsed.institution == "Navy Federal Credit Union"
    assert parsed.account_hint == "…1234"
    assert parsed.period_start == date(2026, 8, 1)
    assert parsed.period_end == date(2026, 8, 31)
    assert [(row.posted_date, row.amount) for row in parsed.transactions] == [
        (date(2026, 8, 2), Decimal("-45.67")),
        (date(2026, 8, 5), Decimal("1250.00")),
        (date(2026, 8, 8), Decimal("-19.95")),
    ]
    continued = parsed.transactions[2]
    assert continued.description == "SYNTHETIC ONLINE ORDER ORDER REFERENCE ABC"
    assert continued.confidence == Decimal("0.900")
    assert continued.warnings == ("Description continued across multiple lines",)


def test_warns_for_missing_metadata_malformed_rows_and_out_of_period_dates() -> None:
    parsed = NavyFederalCheckingAdapter().parse(
        """NAVY FEDERAL CREDIT UNION
Checking
Transactions
08/02/2026 MISSING AMOUNT
09/01/2026 SYNTHETIC PURCHASE -1.00
Ending Balance 0.00
"""
    )

    assert parsed.warnings == (
        "Statement period could not be identified",
        "Account hint could not be identified",
        "Skipped a malformed transaction row",
    )
    assert parsed.transactions[0].warnings == ()


def test_warns_when_transaction_date_is_outside_known_period() -> None:
    parsed = NavyFederalCheckingAdapter().parse(
        """NAVY FEDERAL CREDIT UNION
Checking
Statement Period: 08/01/2026 - 08/31/2026
Transactions
09/01/2026 SYNTHETIC PURCHASE -1.00
Ending Balance 0.00
"""
    )

    assert parsed.transactions[0].confidence == Decimal("0.700")
    assert parsed.transactions[0].warnings == (
        "Posted date falls outside the statement period",
    )


def test_requires_at_least_one_supported_transaction() -> None:
    with pytest.raises(StatementParseError, match="No supported transaction rows"):
        NavyFederalCheckingAdapter().parse(
            "NAVY FEDERAL CREDIT UNION\nChecking\nTransactions\nDate Description Amount"
        )


def test_does_not_claim_credit_card_layout() -> None:
    text = """NAVY FEDERAL CREDIT UNION
CREDIT CARD
TRANSACTIONS
Trans Date Post Date Reference No. Description Amount
01/02/26 01/03/26 123456789012 SYNTHETIC PURCHASE $10.00"""

    assert NavyFederalCheckingAdapter().can_parse(text) is False
