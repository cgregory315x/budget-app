import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")
_PUNCTUATION = re.compile(r"[^A-Z0-9 ]+")


def normalize_merchant(description: str) -> str:
    """Create a stable, conservative value for deterministic merchant matching.

    Numbers are intentionally retained because they can distinguish merchants or locations.
    Institution-specific noise removal belongs in the corresponding statement adapter.
    """

    ascii_description = (
        unicodedata.normalize("NFKD", description).encode("ascii", "ignore").decode()
    )
    uppercase = ascii_description.upper()
    without_punctuation = _PUNCTUATION.sub(" ", uppercase)
    return _WHITESPACE.sub(" ", without_punctuation).strip()
