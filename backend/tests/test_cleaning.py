import math

import pandas as pd
import pytest

from app.services.cleaning import apply_cleaning
from app.services.issue_detection import detect_issues
from app.services.profiling import profile_dataset


def _clean(df: pd.DataFrame):
    profile = profile_dataset(df)
    issues = detect_issues(df, profile)
    result = apply_cleaning(df, issues)
    return result, issues


def test_whitespace_is_trimmed():
    values = [f"free text value {i}" for i in range(19)] + ["  extra   spaces  "]
    df = pd.DataFrame({"notes": values})

    result, _ = _clean(df)

    assert result.cleaned_df.loc[19, "notes"] == "extra spaces"
    assert any(entry.issue_type == "whitespace_formatting" for entry in result.log)


def test_empty_column_is_dropped():
    df = pd.DataFrame({"id": range(1, 11), "notes": [None] * 10})

    result, _ = _clean(df)

    assert "notes" not in result.cleaned_df.columns
    assert "id" in result.cleaned_df.columns
    assert any(entry.issue_type == "empty_column" for entry in result.log)


def test_exact_duplicate_row_is_removed():
    df = pd.DataFrame({"a": [1, 1, 2], "b": [10, 10, 20]})

    result, _ = _clean(df)

    assert len(result.cleaned_df) == 2
    assert any(entry.issue_type == "duplicate_rows" for entry in result.log)


def test_missing_placeholder_becomes_nan_and_real_values_untouched():
    # An "id" column ensures rows with the same status text are NOT also exact
    # full-row duplicates, so the (correct, higher-priority) duplicate_rows cleanup
    # doesn't collapse them and confuse this test's row-position assertions.
    df = pd.DataFrame(
        {
            "id": [1, 2, 3, 4, 5],
            "status": ["active", "active", "N/A", "active", "inactive"],
        }
    )

    result, _ = _clean(df)

    cleaned = result.cleaned_df["status"]
    assert pd.isna(cleaned.iloc[2])
    assert cleaned.iloc[0] == "active"
    assert cleaned.iloc[1] == "active"
    assert cleaned.iloc[3] == "active"
    assert cleaned.iloc[4] == "inactive"
    assert any(entry.issue_type == "missing_value_placeholder" for entry in result.log)


def test_category_inconsistency_collapses_to_majority_spelling():
    values = ["USA", "usa", " USA "] + ["Canada"] * 8 + ["Mexico"] * 9
    df = pd.DataFrame({"id": range(1, len(values) + 1), "country": values})

    result, _ = _clean(df)

    # "USA"/"usa"/" USA " should all collapse to whichever variant is most frequent
    # among themselves. Each appears once, so max() picks deterministically (first
    # encountered with the max count) -- we just assert they all became the SAME value.
    usa_rows = result.cleaned_df["country"].iloc[0:3]
    assert usa_rows.nunique() == 1
    # Untouched categories remain untouched.
    assert (result.cleaned_df["country"].iloc[3:11] == "Canada").all()
    assert (result.cleaned_df["country"].iloc[11:20] == "Mexico").all()
    assert any(entry.issue_type == "category_inconsistency" for entry in result.log)


def test_invalid_date_becomes_nan_valid_date_untouched():
    df = pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "event_date": ["2023-01-01", "2023-06-15", "garbage", "2023-06-15"],
        }
    )

    result, _ = _clean(df)

    cleaned = result.cleaned_df["event_date"]
    assert pd.isna(cleaned.iloc[2])
    assert cleaned.iloc[0] == "2023-01-01"
    assert cleaned.iloc[1] == "2023-06-15"
    assert cleaned.iloc[3] == "2023-06-15"
    assert any(entry.issue_type == "invalid_date" for entry in result.log)


def test_low_confidence_outlier_never_modified():
    df = pd.DataFrame({"amount": [10, 20, 30, 40, 1000]})

    result, issues = _clean(df)

    assert any(i.issue_type == "outlier" for i in issues)
    assert result.cleaned_df["amount"].tolist() == [10, 20, 30, 40, 1000]
    assert not any(entry.issue_type == "outlier" for entry in result.log)
    assert result.skipped_low_confidence >= 1


def test_low_confidence_impossible_value_never_modified():
    df = pd.DataFrame({"age": [25, 30, -5, 200, 40]})

    result, issues = _clean(df)

    assert any(i.issue_type == "impossible_value" for i in issues)
    assert result.cleaned_df["age"].tolist() == [25, 30, -5, 200, 40]
    assert not any(entry.issue_type == "impossible_value" for entry in result.log)


def test_unrelated_columns_untouched():
    df = pd.DataFrame(
        {
            "status": ["active", "active", "N/A", "active", "inactive"],
            "amount": [10, 20, 30, 40, 50],
        }
    )

    result, _ = _clean(df)

    assert result.cleaned_df["amount"].tolist() == [10, 20, 30, 40, 50]


def test_cleaning_log_entry_has_full_row_detail_not_capped():
    # 20 placeholder rows -- more than EXAMPLE_LIMIT (5) -- to prove `changes`
    # captures every affected row, not just the capped preview examples.
    values = ["N/A"] * 20 + ["active"] * 5
    df = pd.DataFrame({"id": range(len(values)), "status": values})

    result, _ = _clean(df)

    entry = next(e for e in result.log if e.issue_type == "missing_value_placeholder")
    assert len(entry.changes) == 20
    assert len(entry.before_examples) == 5  # preview stays capped
    assert all(c["new_value"] is None for c in entry.changes)
    assert {c["row_index"] for c in entry.changes} == set(range(20))


def test_protected_column_is_never_modified_even_when_actionable():
    df = pd.DataFrame(
        {
            "id": range(1, 6),
            "status": ["active", "active", "N/A", "active", "inactive"],  # protected
            "notes": ["  padded  "] + [f"clean text {i}" for i in range(19)][:4],  # not protected
        }
    )
    profile = profile_dataset(df)
    issues = detect_issues(df, profile)

    result = apply_cleaning(df, issues, protected_columns={"status"})

    # Protected column: placeholder left exactly as-is, not converted to NaN.
    assert result.cleaned_df.loc[2, "status"] == "N/A"
    assert not any(entry.column == "status" for entry in result.log)
    assert result.skipped_protected_columns >= 1

    # Unprotected column with the same kind of issue is still cleaned.
    assert result.cleaned_df.loc[0, "notes"] == "padded"
    assert any(entry.column == "notes" for entry in result.log)


def test_clean_dataset_produces_no_log_entries():
    df = pd.DataFrame(
        {
            "id": range(1, 21),
            "amount": [10, 20, 30, 40, 50] * 4,
            "category": ["A", "B", "C"] * 6 + ["A", "B"],
        }
    )

    result, issues = _clean(df)

    assert issues == []
    assert result.log == []
    assert result.skipped_low_confidence == 0
    pd.testing.assert_frame_equal(result.cleaned_df, df)
