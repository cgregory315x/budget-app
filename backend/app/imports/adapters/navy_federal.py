import re

from app.imports.types import ParsedStatement, StatementParseError


class NavyFederalCheckingAdapter:
    """Adapter boundary for selectable-text Navy Federal checking statements.

    Transaction extraction will be implemented against synthetic or redacted fixtures so the
    parser can be validated without committing real financial data.
    """

    name = "navy_federal_checking_v1"
    _institution_pattern = re.compile(r"NAVY\s+FEDERAL\s+CREDIT\s+UNION", re.IGNORECASE)

    def can_parse(self, statement_text: str) -> bool:
        return bool(self._institution_pattern.search(statement_text))

    def parse(self, statement_text: str) -> ParsedStatement:
        if not self.can_parse(statement_text):
            raise StatementParseError("The document is not a recognized Navy Federal statement")

        raise StatementParseError(
            "The Navy Federal adapter recognizes this statement, but transaction extraction "
            "requires a synthetic or redacted statement fixture"
        )

