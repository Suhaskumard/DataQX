"""Phase 25 -- Explicit scalar-value edge-case matrix, exercised directly against
profile_dataset()/detect_issues() (not through the API) since these are unit-level
value edge cases, not integration scenarios. Each test's only contract is "does not
raise" unless a specific behavior is called out (e.g. placeholder-vs-missing
distinction)."""

from __future__ import annotations

import pandas as pd

from app.services.issue_detection import detect_issues
from app.services.profiling import profile_dataset


def _profile_and_detect(df: pd.DataFrame):
    profile = profile_dataset(df)
    issues = detect_issues(df, profile)
    return profile, issues


def test_zero_row_dataframe():
    df = pd.DataFrame({"a": pd.Series([], dtype="object"), "b": pd.Series([], dtype="float64")})
    profile, issues = _profile_and_detect(df)
    assert profile.row_count == 0


def test_one_row_dataframe():
    df = pd.DataFrame({"a": [1], "b": ["x"]})
    profile, issues = _profile_and_detect(df)
    assert profile.row_count == 1


def test_all_null_column():
    df = pd.DataFrame({"id": range(10), "empty": [None] * 10})
    profile, issues = _profile_and_detect(df)
    assert any(i.issue_type == "empty_column" for i in issues)


def test_all_unique_column():
    df = pd.DataFrame({"id": range(100), "token": [f"t{i}" for i in range(100)]})
    profile, issues = _profile_and_detect(df)
    token_col = next(c for c in profile.columns if c.original_name == "token")
    assert token_col.unique_percentage == 100.0


def test_all_duplicate_rows():
    df = pd.DataFrame({"a": [1] * 20, "b": ["x"] * 20})
    profile, issues = _profile_and_detect(df)
    assert profile.duplicate_row_count == 19
    assert any(i.issue_type == "duplicate_rows" for i in issues)


def test_constant_column():
    df = pd.DataFrame({"id": range(20), "flag": [True] * 20})
    profile, issues = _profile_and_detect(df)
    assert "flag" in profile.constant_columns


def test_extremely_long_string_value():
    long_value = "x" * 200_000
    df = pd.DataFrame({"id": range(5), "blob": [long_value] * 5})
    _profile_and_detect(df)  # must not raise or hang


def test_unicode_and_emoji_values():
    df = pd.DataFrame({"id": range(3), "name": ["café", "中文", "\U0001f600\U0001f4ca"]})
    _profile_and_detect(df)


def test_leading_zeros_treated_as_text_not_stripped_numerically():
    df = pd.DataFrame({"zip_code": ["00501", "00544", "12345", "00601"]})
    profile, _ = _profile_and_detect(df)
    zip_col = next(c for c in profile.columns if c.original_name == "zip_code")
    # Leading-zero codes must survive as their original string representation
    # somewhere in the example values -- a numeric reinterpretation would lose them.
    assert "00501" in zip_col.example_values


def test_negative_zero_and_scientific_notation_numbers():
    df = pd.DataFrame({"id": range(5), "value": [-5, 0, 1.5e10, -2.3e-8, 100]})
    profile, _ = _profile_and_detect(df)
    value_col = next(c for c in profile.columns if c.original_name == "value")
    assert value_col.inferred_type == "float"
    assert value_col.negative_count == 2


def test_very_large_and_very_small_numbers():
    df = pd.DataFrame({"id": range(3), "value": [1e300, 1e-300, 42]})
    _profile_and_detect(df)  # must not overflow/crash


def test_infinity_and_negative_infinity_values():
    df = pd.DataFrame({"id": range(4), "value": [1.0, float("inf"), float("-inf"), 2.0]})
    _profile_and_detect(df)  # must not raise (Batch 6 sanitization covers JSON output)


def test_nan_values_mixed_with_real_numbers():
    df = pd.DataFrame({"id": range(4), "value": [1.0, float("nan"), 3.0, float("nan")]})
    profile, _ = _profile_and_detect(df)
    value_col = next(c for c in profile.columns if c.original_name == "value")
    assert value_col.missing_count == 2


def test_placeholder_strings_distinguished_from_true_missingness():
    """NULL/None/N/A/NA/null/Unknown/Not Available are all semantically "missing"
    placeholders but must not raise. The detector only flags them when mixed with
    genuine real values (by design -- a column that's entirely "Unknown" could be
    legitimate data, not a data-quality defect), so this fixture mixes placeholders
    with real values rather than using an all-placeholder column."""
    placeholders = ["NULL", "None", "N/A", "NA", "null", "Unknown", "Not Available"]
    real_values = ["active", "inactive", "active"]
    df = pd.DataFrame({"id": range(len(placeholders) + len(real_values)), "status": placeholders + real_values})
    profile, issues = _profile_and_detect(df)
    placeholder_issue = next((i for i in issues if i.issue_type == "missing_value_placeholder"), None)
    assert placeholder_issue is not None
    assert placeholder_issue.affected_count == len(placeholders)


def test_all_placeholder_column_is_left_alone_not_misflagged():
    """An entirely-placeholder column (e.g. genuinely always "Unknown") is left
    alone by design -- it's contextual evidence, not a blind blocklist match."""
    df = pd.DataFrame({"id": range(3), "status": ["Unknown", "Unknown", "N/A"]})
    _, issues = _profile_and_detect(df)
    assert not any(i.issue_type == "missing_value_placeholder" for i in issues)
