from app.services.currency_normalizer import detect_column_currency_inconsistency, parse_currency_cell


def test_rupee_symbol_no_space():
    result = parse_currency_cell("₹4500")
    assert result.normalized_value == 4500.0
    assert result.confidence == "HIGH"
    assert result.currency == "INR"


def test_rupee_symbol_with_comma():
    result = parse_currency_cell("₹ 4,500")
    assert result.normalized_value == 4500.0


def test_plain_comma_thousands():
    result = parse_currency_cell("4,500")
    assert result.normalized_value == 4500.0


def test_currency_code_suffix():
    result = parse_currency_cell("2499 INR")
    assert result.normalized_value == 2499.0
    assert result.currency == "INR"


def test_currency_code_prefix():
    result = parse_currency_cell("INR 2499")
    assert result.normalized_value == 2499.0


def test_decimal_with_comma():
    result = parse_currency_cell("1,200.50")
    assert result.normalized_value == 1200.50


def test_dollar_sign():
    result = parse_currency_cell("$1,200.50")
    assert result.normalized_value == 1200.50
    assert result.currency == "USD"


def test_parentheses_negative():
    result = parse_currency_cell("(500)")
    assert result.normalized_value == -500.0


def test_rs_prefix():
    result = parse_currency_cell("Rs. 4500")
    assert result.normalized_value == 4500.0
    assert result.currency == "INR"


def test_not_available_is_missing_not_zero():
    result = parse_currency_cell("not available")
    assert result.normalized_value is None
    assert result.confidence == "MISSING"


def test_free_text_is_invalid_not_zero():
    result = parse_currency_cell("free")
    assert result.normalized_value is None
    assert result.confidence == "INVALID"


def test_spelled_out_number_is_invalid():
    result = parse_currency_cell("ten thousand")
    assert result.normalized_value is None
    assert result.confidence == "INVALID"


def test_mixed_currency_column_detected():
    currencies = detect_column_currency_inconsistency(["$500", "₹500", "100"])
    assert set(currencies) == {"USD", "INR"}


def test_single_currency_column_not_flagged():
    currencies = detect_column_currency_inconsistency(["₹500", "₹1,000", "100"])
    assert currencies == []
