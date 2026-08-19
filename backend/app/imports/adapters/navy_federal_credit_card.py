import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.db.models import AccountType
from app.imports.types import CandidateTransaction, ParsedStatement, StatementParseError


class NavyFederalCreditCardAdapter:
    """Parser for selectable-text Navy Federal credit-card statements."""

    name = "navy_federal_credit_card_v1"
    account_type = AccountType.CREDIT_CARD
    _institution_pattern = re.compile(r"NAVY\s+FEDERAL\s+CREDIT\s+UNION", re.IGNORECASE)
    _layout_pattern = re.compile(
        r"Trans\s+Date\s+Post\s+Date\s+Reference\s+No\.\s+Description\s+Amount",
        re.IGNORECASE,
    )
    _row_pattern = re.compile(
        r"^(\d{2}/\d{2}/\d{2})\s+(\d{2}/\d{2}/\d{2})\s+"
        r"([A-Za-z0-9]{6,})\s+(.+?)\s+\$([\d,]+\.\d{2})$"
    )
    _account_pattern = re.compile(
        r"(?:X{4}|\*{4})(?:\s+(?:X{4}|\*{4})){2}\s+(\d{4})", re.IGNORECASE
    )
    _positive_pattern = re.compile(r"\b(?:PAYMENT|REFUND|CREDIT|REVERSAL)\b", re.IGNORECASE)
    _end_pattern = re.compile(
        r"^(?:TOTAL(?:\s|FEES)|\d{4}\s+TOTALS|INTEREST\s+CHARGE)", re.IGNORECASE
    )

    def can_parse(self, statement_text: str) -> bool:
        return bool(
            self._institution_pattern.search(statement_text)
            and self._layout_pattern.search(statement_text)
        )

    def parse(self, statement_text: str) -> ParsedStatement:
        if not self.can_parse(statement_text):
            raise StatementParseError(
                "The document is not a recognized Navy Federal credit card statement"
            )

        account_match = self._account_pattern.search(statement_text)
        transactions: list[CandidateTransaction] = []
        statement_warnings: list[str] = []
        in_table = False

        for raw_line in statement_text.splitlines():
            line = raw_line.strip()
            if self._layout_pattern.fullmatch(line):
                in_table = True
                continue
            if in_table and self._end_pattern.match(line):
                in_table = False
                continue
            if not in_table or not line:
                continue
            match = self._row_pattern.fullmatch(line)
            if match is None:
                if re.match(r"^\d{2}/\d{2}/\d{2}\b", line):
                    statement_warnings.append("Skipped a malformed credit card transaction row")
                continue
            try:
                posted_date = self._parse_date(match.group(2))
                unsigned_amount = Decimal(match.group(5).replace(",", ""))
            except (ValueError, InvalidOperation):
                statement_warnings.append("Skipped a row with an invalid date or amount")
                continue

            description = match.group(4).strip()
            is_credit = bool(self._positive_pattern.search(description))
            amount = unsigned_amount if is_credit else -unsigned_amount
            transactions.append(
                CandidateTransaction(
                    posted_date=posted_date,
                    description=description,
                    amount=amount,
                    source_text=line,
                    confidence=Decimal("0.850"),
                    warnings=(
                        "Amount sign inferred from credit card transaction description",
                    ),
                )
            )

        if not transactions:
            raise StatementParseError("No supported credit card transaction rows were found")

        dates = [transaction.posted_date for transaction in transactions]
        return ParsedStatement(
            institution="Navy Federal Credit Union",
            account_hint=f"…{account_match.group(1)}" if account_match else None,
            period_start=min(dates),
            period_end=max(dates),
            transactions=tuple(transactions),
            warnings=tuple(statement_warnings),
        )

    @staticmethod
    def _parse_date(value: str) -> date:
        return datetime.strptime(value, "%m/%d/%y").date()
