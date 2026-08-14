from collections.abc import Iterable

from app.imports.adapters.navy_federal import NavyFederalCheckingAdapter
from app.imports.types import StatementAdapter, UnsupportedStatementError

DEFAULT_ADAPTERS: tuple[StatementAdapter, ...] = (NavyFederalCheckingAdapter(),)


def identify_adapter(
    statement_text: str,
    adapters: Iterable[StatementAdapter] = DEFAULT_ADAPTERS,
) -> StatementAdapter:
    for adapter in adapters:
        if adapter.can_parse(statement_text):
            return adapter

    raise UnsupportedStatementError("No supported statement format was recognized")

