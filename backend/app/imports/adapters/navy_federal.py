import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.db.models import AccountType
from app.imports.types import CandidateTransaction, ParsedStatement, StatementParseError


class NavyFederalCheckingAdapter:
    """Parser for the supported selectable-text checking statement layout."""

    name = "navy_federal_checking_v1"
    account_type = AccountType.CHECKING
    _institution_pattern = re.compile(
        r"NAVY\s+FEDERAL(?:\s+CREDIT\s+UNION)?", re.IGNORECASE
    )
    _credit_card_pattern = re.compile(
        r"Trans\s+Date\s+Post\s+Date\s+Reference\s+No\.",
        re.IGNORECASE,
    )
    _period_pattern = re.compile(
    r"Statement\s+Period\s*:?\s*(\d{2}/\d{2}/(?:\d{4}|\d{2}))\s*"
    r"(?:-|through|to)\s*(\d{2}/\d{2}/(?:\d{4}|\d{2}))",
        re.IGNORECASE | re.MULTILINE,
    )
    _account_pattern = re.compile(
        r"(?:Checking\s+Account|Account\s+Number)\s*:?\s*(?:X{2,}|\*{2,})?\s*(\d{4})\b",
        re.IGNORECASE,
    )
    _checking_section_pattern = re.compile(
        r"^EveryDay\s+Checking\s+-\s+(\d{6,})", re.IGNORECASE
    )
    _real_table_header_pattern = re.compile(
        r"^Date\s+(?:Transaction|Transact\s+ion)\s+"
        r"(?:Details?|Detai\s+l).*Amount\(\$\)\s+Balance\(\$\)$",
        re.IGNORECASE | re.MULTILINE,
    )
    _real_transaction_pattern = re.compile(
        r"^(\d{2}-\d{2})\s+(.+?)\s+\$?([\d,]+\.\d{2})\s*(-?)\s+"
        r"\$?([\d,]+\.\d{2})-?$"
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
        multiple_accounts = False
        if period_start is None or period_end is None:
            warnings.append("Statement period could not be identified")
        if self._real_table_header_pattern.search(statement_text):
            transactions, row_warnings, transaction_accounts = self._parse_real_transactions(
                statement_text, period_start, period_end
            )
            if len(transaction_accounts) == 1:
                account_hint = f"…{next(iter(transaction_accounts))}"
            elif len(transaction_accounts) > 1:
                account_hint = None
                multiple_accounts = True
                warnings.append(
                    "Transactions from multiple checking account sections require review"
                )
        else:
            transactions, row_warnings = self._parse_transactions(
                statement_text, period_start, period_end
            )
        if account_hint is None and not multiple_accounts:
            warnings.append("Account hint could not be identified")
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
        date_format = "%m/%d/%Y" if len(value.rsplit("/", 1)[-1]) == 4 else "%m/%d/%y"
        return datetime.strptime(value, date_format).date()

    @staticmethod
    def _parse_amount(value: str) -> Decimal:
        normalized = value.replace("$", "").replace(",", "")
        if normalized.startswith("(") and normalized.endswith(")"):
            normalized = f"-{normalized[1:-1]}"
        return Decimal(normalized)

    def _parse_real_transactions(
        self, text: str, period_start: date | None, period_end: date | None
    ) -> tuple[list[CandidateTransaction], list[str], set[str]]:
        active_account: str | None = None
        in_table = False
        transactions: list[CandidateTransaction] = []
        warnings: list[str] = []
        transaction_accounts: set[str] = set()

        for raw_line in text.splitlines():
            line = raw_line.strip()
            section_match = self._checking_section_pattern.match(line)
            if section_match:
                active_account = section_match.group(1)[-4:]
                in_table = False
                continue
            if re.match(r"^(?:Savings|Certificates?|Loans?)\b", line, re.IGNORECASE):
                active_account = None
                in_table = False
                continue
            if active_account and self._real_table_header_pattern.match(line):
                in_table = True
                continue
            if in_table and re.match(r"^\d{2}-\d{2}\s+Ending\s+Balance", line, re.IGNORECASE):
                in_table = False
                continue
            if not in_table or active_account is None or not line:
                continue
            if re.match(r"^\d{2}-\d{2}\s+Beginning\s+Balance", line, re.IGNORECASE):
                continue
            match = self._real_transaction_pattern.fullmatch(line)
            if match is None:
                if re.match(r"^\d{2}-\d{2}\b", line):
                    warnings.append("Skipped an unrecognized checking transaction row")
                continue
            posted_date = self._date_in_period(match.group(1), period_start, period_end)
            amount = Decimal(match.group(3).replace(",", ""))
            if match.group(4) == "-":
                amount = -amount
            transactions.append(
                CandidateTransaction(
                    posted_date=posted_date,
                    description=match.group(2).strip(),
                    amount=amount,
                    source_text=line,
                    confidence=Decimal("1.000"),
                )
            )
            transaction_accounts.add(active_account)
        return transactions, warnings, transaction_accounts

    @staticmethod
    def _date_in_period(
        month_day: str, period_start: date | None, period_end: date | None
    ) -> date:
        month, day = (int(part) for part in month_day.split("-"))
        years = (
            range(period_start.year, period_end.year + 1)
            if period_start is not None and period_end is not None
            else (date.today().year,)
        )
        candidates = [date(year, month, day) for year in years]
        if period_start is not None and period_end is not None:
            for candidate in candidates:
                if period_start <= candidate <= period_end:
                    return candidate
        return candidates[-1]
