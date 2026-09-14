"""Regression tests for the date_normalizer module, named after the exact failure
mode this module exists to prevent: valid/recoverable dates silently becoming NaN
because pandas' default format inference couldn't guess them."""

from app.services.date_normalizer import infer_column_convention, parse_date_cell


def test_05_01_2026_not_destroyed_with_ddmm_column_evidence():
    # "13/01/2026" elsewhere in the column proves DD/MM/YYYY -- day can't be 13 in MM/DD.
    convention = infer_column_convention(["13/01/2026", "05/01/2026"])
    result = parse_date_cell("05/01/2026", column_convention=convention)
    assert result.status == "parsed"
    assert result.normalized_value == "2026-01-05"
    assert result.confidence == "MEDIUM"


def test_jan_7_2026_not_destroyed():
    result = parse_date_cell("Jan 7 2026")
    assert result.status == "parsed"
    assert result.normalized_value == "2026-01-07"
    assert result.confidence == "HIGH"


def test_january_7_2026_comma_form_not_destroyed():
    result = parse_date_cell("January 7, 2026")
    assert result.status == "parsed"
    assert result.normalized_value == "2026-01-07"


def test_7_jan_2026_not_destroyed():
    result = parse_date_cell("7 Jan 2026")
    assert result.status == "parsed"
    assert result.normalized_value == "2026-01-07"


def test_2026_01_08_not_destroyed():
    result = parse_date_cell("2026/01/08")
    assert result.status == "parsed"
    assert result.normalized_value == "2026-01-08"
    assert result.confidence == "HIGH"


def test_08_01_2026_not_destroyed():
    # No column evidence provided -- but both components are 08 (<=12) and 01 (<=12),
    # genuinely ambiguous without more context, so this alone should be preserved+flagged,
    # not guessed. This documents that expectation explicitly.
    result = parse_date_cell("08-01-2026")
    assert result.status == "ambiguous"
    assert result.normalized_value is None
    assert result.original_value == "08-01-2026"  # preserved, not destroyed


def test_08_01_2026_resolved_with_column_evidence():
    convention = infer_column_convention(["08-01-2026", "25-01-2026"])  # 25 > 12 -> DD/MM
    result = parse_date_cell("08-01-2026", column_convention=convention)
    assert result.status == "parsed"
    assert result.normalized_value == "2026-01-08"


def test_13_01_2026_interpreted_as_ddmm():
    result = parse_date_cell("13-01-2026")
    assert result.status == "parsed"
    assert result.normalized_value == "2026-01-13"
    assert result.confidence == "HIGH"
    assert result.convention == "DD/MM"


def test_invalid_date_31_02_2026_flagged_not_guessed():
    result = parse_date_cell("31/02/2026")
    assert result.status == "invalid"
    assert result.normalized_value is None


def test_invalid_date_99_99_2026():
    result = parse_date_cell("99/99/2026")
    assert result.status == "invalid"


def test_leap_year_29_02_2024_valid():
    result = parse_date_cell("2024-02-29")
    assert result.status == "parsed"
    assert result.normalized_value == "2024-02-29"


def test_leap_year_29_02_2025_invalid():
    result = parse_date_cell("2025-02-29")
    assert result.status == "invalid"


def test_missing_markers_are_missing_not_invalid():
    for marker in ["", "N/A", "NA", "null", "unknown", "not available"]:
        result = parse_date_cell(marker)
        assert result.status == "missing", f"{marker!r} should be MISSING, got {result.status}"


def test_contradictory_column_evidence_yields_no_convention():
    # "13/01/2026" -> DD/MM signal; "01/13/2026" -> MM/DD signal. Contradictory.
    convention = infer_column_convention(["13/01/2026", "01/13/2026"])
    assert convention is None


def test_random_text_is_invalid_not_missing():
    result = parse_date_cell("banana")
    assert result.status == "invalid"


def test_whitespace_and_mixed_separators_tolerated():
    result = parse_date_cell("  2026-01-08  ")
    assert result.status == "parsed"
    assert result.normalized_value == "2026-01-08"
