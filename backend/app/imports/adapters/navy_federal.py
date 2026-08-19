import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.db.models import AccountType
from app.imports.types import CandidateTransaction, ParsedStatement, StatementParseError


class NavyFederalCheckingAdapter:
    """Parser for the supported selectable-text checking statement layout."""

    name = "navy_federal_checking_v1"
    account_type = AccountType.CHECKING
    _institution_pattern = re.compile(r"NAVY\s+FEDERAL\s+CREDIT\s+UNION", re.IGNORECASE)
    _credit_card_pattern = re.compile(
        r"\bCREDIT\s+CARD\b|Trans\s+Date\s+Post\s+Date\s+Reference\s+No\.",
        re.IGNORECASE,
    )
    _period_pattern = re.compile(
        r"Statement\s+Period\s*:?\s*(\d{2}/\d{2}/\d{4})\s*(?:-|through|to)\s*"
        r"(\d{2}/\d{2}/\d{4})",
        re.IGNORECASE,
    )
    _account_pattern = re.compile(
        r"(?:Checking\s+Account|Account\s+Number)\s*:?\s*(?:X{2,}|\*{2,})?\s*(\d{4})\b",
        re.IGNORECASE,
    )
    _transaction_pattern = re.compile(
        r"^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+"
        r"(\(?[-+]?\$?[\d,]+\.\d{2}\)?)$"
    )
    _section_start_pattern = re.compile(r"^(?:Transaction\s+Detail|Transactions)$", re.IGNORECASE)
    _section_end_pattern = re.compile(
        r"^(?:Ending\s+Balance|Daily\s+Balance|Account\s+Summary)", re.IGNORECASE
    )
    _column_header_pattern = re.compile(
        r"^Date\s+(?:Description|Transaction).*(?:Amount|Deposits?|Withdrawals?)$",
        re.IGNORECASE,
    )

    def can_parse(self, statement_text: str) -> bool:
        return bool(
            self._institution_pattern.search(statement_text)
            and re.search(r"\bCHECKING\b", statement_text, re.IGNORECASE)
            and not self._credit_card_pattern.search(statement_text)
        )

    def parse(self, statement_text: str) -> ParsedStatement:
        if not self.can_parse(statement_text):
            raise StatementParseError("The document is not a recognized Navy Federal statement")

        period_start, period_end = self._parse_period(statement_text)
        account_match = self._account_pattern.search(statement_text)
        account_hint = f"…{account_match.group(1)}" if account_match else None
        warnings: list[str] = []
        if period_start is None or period_end is None:
            warnings.append("Statement period could not be identified")
        if account_hint is None:
            warnings.append("Account hint could not be identified")

        transactions, row_warnings = self._parse_transactions(
            statement_text, period_start, period_end
        )
        warnings.extend(row_warnings)
        if not transactions:
            raise StatementParseError("No supported transaction rows were found")

        return ParsedStatement(
            institution="Navy Federal Credit Union",
            account_hint=account_hint,
            period_start=period_start,
            period_end=period_end,
            transactions=tuple(transactions),
            warnings=tuple(warnings),
        )

    def _parse_period(self, text: str) -> tuple[date | None, date | None]:
        match = self._period_pattern.search(text)
        if match is None:
            return None, None
        try:
            return self._parse_date(match.group(1)), self._parse_date(match.group(2))
        except ValueError:
            return None, None

    def _parse_transactions(
        self, text: str, period_start: date | None, period_end: date | None
    ) -> tuple[list[CandidateTransaction], list[str]]:
        lines = [line.strip() for line in text.splitlines()]
        in_section = False
        rows: list[tuple[str, str]] = []
        warnings: list[str] = []

        for line in lines:
            if self._section_start_pattern.fullmatch(line):
                in_section = True
                continue
            if in_section and self._section_end_pattern.match(line):
                break
            if not in_section or not line:
                continue
            if self._column_header_pattern.match(line):
                continue
            match = self._transaction_pattern.fullmatch(line)
            if match:
                rows.append((match.group(1), line))
            elif re.match(r"^\d{2}/\d{2}/\d{4}\b", line):
                warnings.append("Skipped a malformed transaction row")
            elif rows:
                transaction_date, source = rows[-1]
                rows[-1] = (transaction_date, f"{source}\n{line}")
            else:
                warnings.append("Skipped an unrecognized line before the first transaction")

        transactions: list[CandidateTransaction] = []
        for date_text, source_text in rows:
            # Continuation lines are stored after the original complete row. Re-match the first
            # source line to keep the amount separate from the accumulated description.
            first_line = source_text.splitlines()[0]
            match = self._transaction_pattern.fullmatch(first_line)
            if match is None:
                continue
            description = match.group(2)
            continuation = source_text.splitlines()[1:]
            if continuation:
                description = " ".join((description, *continuation))
            try:
                posted_date = self._parse_date(date_text)
                amount = self._parse_amount(match.group(3))
            except (ValueError, InvalidOperation):
                warnings.append("Skipped a transaction row with an invalid date or amount")
                continue

            row_warnings: list[str] = []
            confidence = Decimal("1.000")
            if continuation:
                row_warnings.append("Description continued across multiple lines")
                confidence = Decimal("0.900")
            if (
                period_start is not None
                and period_end is not None
                and not period_start <= posted_date <= period_end
            ):
                row_warnings.append("Posted date falls outside the statement period")
                confidence = min(confidence, Decimal("0.700"))

            transactions.append(
                CandidateTransaction(
                    posted_date=posted_date,
                    description=description,
                    amount=amount,
                    source_text=source_text,
                    confidence=confidence,
                    warnings=tuple(row_warnings),
                )
            )
        return transactions, warnings

    @staticmethod
    def _parse_date(value: str) -> date:
        return datetime.strptime(value, "%m/%d/%Y").date()

    @staticmethod
    def _parse_amount(value: str) -> Decimal:
        normalized = value.replace("$", "").replace(",", "")
        if normalized.startswith("(") and normalized.endswith(")"):
            normalized = f"-{normalized[1:-1]}"
        return Decimal(normalized)
