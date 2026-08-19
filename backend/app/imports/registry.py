from collections.abc import Iterable

from app.imports.adapters.navy_federal import NavyFederalCheckingAdapter
from app.imports.adapters.navy_federal_credit_card import NavyFederalCreditCardAdapter
from app.imports.types import StatementAdapter, UnsupportedStatementError

DEFAULT_ADAPTERS: tuple[StatementAdapter, ...] = (
    NavyFederalCreditCardAdapter(),
    NavyFederalCheckingAdapter(),
)


def identify_adapter(
    statement_text: str,
    adapters: Iterable[StatementAdapter] = DEFAULT_ADAPTERS,
) -> StatementAdapter:
    for adapter in adapters:
        if adapter.can_parse(statement_text):
            return adapter

    raise UnsupportedStatementError("No supported statement format was recognized")
