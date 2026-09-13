from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from app.services.issue_detection import detect_issues
from app.services.profiling import profile_dataset


def _issues_of_type(issues, issue_type):
    return [i for i in issues if i.issue_type == issue_type]


def test_missing_placeholder_detected_when_mixed_with_real_values():
    df = pd.DataFrame({"status": ["active", "active", "N/A", "active", "inactive"]})
    profile = profile_dataset(df)
    issues = detect_issues(df, profile)

    matches = _issues_of_type(issues, "missing_value_placeholder")
    assert len(matches) == 1
    assert matches[0].column == "status"
    assert matches[0].affected_count == 1


def test_missing_placeholder_not_flagged_when_column_is_entirely_placeholders():
    df = pd.DataFrame({"status": ["N/A", "N/A", "N/A", "N/A"]})
    profile = profile_dataset(df)
    issues = detect_issues(df, profile)

    assert _issues_of_type(issues, "missing_value_placeholder") == []


def test_exact_duplicate_rows_detected():
    df = pd.DataFrame({"a": [1, 1, 2], "b": [10, 10, 20]})
    profile = profile_dataset(df)
    issues = detect_issues(df, profile)

    matches = _issues_of_type(issues, "duplicate_rows")
    assert len(matches) == 1
    assert matches[0].affected_count == 1


def test_duplicate_id_detected():
    values = list(range(1, 20)) + [19]  # 20 values, "19" repeated -> 95% unique
    df = pd.DataFrame({"customer_id": values})
    profile = profile_dataset(df)
    id_col = next(c for c in profile.columns if c.original_name == "customer_id")
    assert id_col.inferred_type == "id"

    issues = detect_issues(df, profile)
    matches = _issues_of_type(issues, "duplicate_id")
    assert len(matches) == 1
    assert matches[0].column == "customer_id"
    assert matches[0].severity == "critical"
    assert matches[0].affected_count == 1


def test_mixed_types_detected():
    df = pd.DataFrame({"amount_text": ["100", "200", "300", "abc", "150"]})
    profile = profile_dataset(df)
    col = next(c for c in profile.columns if c.original_name == "amount_text")
    assert col.inferred_type == "string"

    issues = detect_issues(df, profile)
    matches = _issues_of_type(issues, "mixed_data_types")
    assert len(matches) == 1
    assert matches[0].affected_count == 1
    assert "abc" in matches[0].details["examples"]


def test_category_inconsistency_detected():
    values = ["USA", "usa", " USA ", "Canada", "Canada", "Canada", "Mexico", "Mexico", "Mexico", "Mexico"]
    df = pd.DataFrame({"country": values})
    profile = profile_dataset(df)
    col = next(c for c in profile.columns if c.original_name == "country")
    assert col.inferred_type == "categorical"

    issues = detect_issues(df, profile)
    matches = _issues_of_type(issues, "category_inconsistency")
    assert len(matches) == 1
    assert matches[0].column == "country"


def test_invalid_and_future_date_detected():
    future = (datetime.now(timezone.utc) + timedelta(days=100)).strftime("%Y-%m-%d")
    df = pd.DataFrame({"event_date": ["2023-01-01", "2023-06-15", "garbage", future]})
    profile = profile_dataset(df)
    col = next(c for c in profile.columns if c.original_name == "event_date")
    assert col.inferred_type == "date"

    issues = detect_issues(df, profile)
    invalid = _issues_of_type(issues, "invalid_date")
    future_issues = _issues_of_type(issues, "future_date")
    assert len(invalid) == 1 and invalid[0].affected_count == 1
    assert len(future_issues) == 1 and future_issues[0].affected_count == 1


def test_ambiguous_date_format_detected():
    df = pd.DataFrame({"order_date": ["15/03/2024", "03/04/2024", "20/01/2024", "05/06/2024"]})
    profile = profile_dataset(df)

    issues = detect_issues(df, profile)
    matches = _issues_of_type(issues, "ambiguous_date_format")
    assert len(matches) == 1
    assert matches[0].column == "order_date"


def test_impossible_age_value_detected():
    df = pd.DataFrame({"age": [25, 30, -5, 200, 40]})
    profile = profile_dataset(df)

    issues = detect_issues(df, profile)
    matches = _issues_of_type(issues, "impossible_value")
    assert len(matches) == 1
    assert matches[0].column == "age"
    assert matches[0].affected_count == 2


def test_negative_quantity_detected():
    df = pd.DataFrame({"quantity": [5, 10, -3, 8]})
    profile = profile_dataset(df)

    issues = detect_issues(df, profile)
    matches = _issues_of_type(issues, "negative_value")
    assert len(matches) == 1
    assert matches[0].affected_count == 1


def test_outlier_classified_potential_error_for_extreme_value():
    df = pd.DataFrame({"amount": [10, 20, 30, 40, 1000]})
    profile = profile_dataset(df)

    issues = detect_issues(df, profile)
    matches = _issues_of_type(issues, "outlier")
    assert len(matches) == 1
    assert matches[0].details["classification"] == "potential_error"
    assert matches[0].severity == "high"


def test_outlier_classified_suspicious_for_mild_value():
    df = pd.DataFrame({"amount": [10, 20, 30, 40, 72]})
    profile = profile_dataset(df)

    issues = detect_issues(df, profile)
    matches = _issues_of_type(issues, "outlier")
    assert len(matches) == 1
    assert matches[0].details["classification"] == "suspicious"
    assert matches[0].severity == "medium"


def test_constant_column_detected():
    df = pd.DataFrame({"region": ["East"] * 10, "id": range(1, 11)})
    profile = profile_dataset(df)

    issues = detect_issues(df, profile)
    matches = _issues_of_type(issues, "constant_column")
    assert len(matches) == 1
    assert matches[0].column == "region"


def test_empty_column_detected():
    df = pd.DataFrame({"notes": [None] * 10, "id": range(1, 11)})
    profile = profile_dataset(df)

    issues = detect_issues(df, profile)
    matches = _issues_of_type(issues, "empty_column")
    assert len(matches) == 1
    assert matches[0].column == "notes"


def test_high_cardinality_column_detected():
    df = pd.DataFrame({"comments": [f"free text unique {i}" for i in range(20)]})
    profile = profile_dataset(df)
    col = next(c for c in profile.columns if c.original_name == "comments")
    assert col.inferred_type == "string"

    issues = detect_issues(df, profile)
    matches = _issues_of_type(issues, "high_cardinality")
    assert len(matches) == 1
    assert matches[0].column == "comments"


def test_whitespace_formatting_detected():
    values = [f"free text value {i}" for i in range(19)] + ["  extra spaces  "]
    df = pd.DataFrame({"notes": values})
    profile = profile_dataset(df)
    col = next(c for c in profile.columns if c.original_name == "notes")
    assert col.inferred_type == "string"

    issues = detect_issues(df, profile)
    matches = _issues_of_type(issues, "whitespace_formatting")
    assert len(matches) == 1
    assert matches[0].column == "notes"
    assert matches[0].affected_count == 1


def test_whitespace_formatting_absent_when_clean():
    values = [f"free text value {i}" for i in range(20)]
    df = pd.DataFrame({"notes": values})
    profile = profile_dataset(df)

    issues = detect_issues(df, profile)
    assert _issues_of_type(issues, "whitespace_formatting") == []


def test_clean_dataset_produces_no_issues():
    df = pd.DataFrame(
        {
            "id": range(1, 21),
            "amount": [10, 20, 30, 40, 50] * 4,
            "category": ["A", "B", "C"] * 6 + ["A", "B"],
        }
    )
    profile = profile_dataset(df)

    issues = detect_issues(df, profile)
    assert issues == []
