from app.services.email_validator import validate_email_cell


def test_valid_email():
    result = validate_email_cell("john@gmail.com")
    assert result.is_valid
    assert result.normalized_value == "john@gmail.com"


def test_valid_email_subdomain():
    result = validate_email_cell("john.smith@company.co.in")
    assert result.is_valid


def test_missing_domain_tld():
    result = validate_email_cell("arjun.kumar@gmail")
    assert not result.is_valid


def test_missing_domain_entirely():
    result = validate_email_cell("kiran@")
    assert not result.is_valid


def test_missing_at_symbol():
    result = validate_email_cell("gautham.gmail.com")
    assert not result.is_valid


def test_no_at_at_all():
    result = validate_email_cell("invalid-email")
    assert not result.is_valid


def test_multiple_at_symbols():
    result = validate_email_cell("a@b@c.com")
    assert not result.is_valid


def test_whitespace_in_email():
    result = validate_email_cell("john smith@gmail.com")
    assert not result.is_valid


def test_uppercase_normalized_to_lowercase():
    result = validate_email_cell("JOHN@GMAIL.COM")
    assert result.is_valid
    assert result.normalized_value == "john@gmail.com"


def test_trims_whitespace():
    result = validate_email_cell("  john@gmail.com  ")
    assert result.is_valid
    assert result.normalized_value == "john@gmail.com"


def test_invalid_email_never_fabricates_domain():
    result = validate_email_cell("kiran@")
    assert result.normalized_value is None
