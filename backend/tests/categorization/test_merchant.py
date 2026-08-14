from app.categorization.merchant import normalize_merchant


def test_normalizes_case_spacing_and_punctuation() -> None:
    assert normalize_merchant("  Café  Example #104  ") == "CAFE EXAMPLE 104"


def test_retains_digits_that_may_distinguish_merchants() -> None:
    assert normalize_merchant("Example Store 123") == "EXAMPLE STORE 123"

