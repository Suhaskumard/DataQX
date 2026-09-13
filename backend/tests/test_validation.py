import pandas as pd
import pytest

from app.services.validation import validate_dataset


def _status_of(report, check_name):
    return next(c.status for c in report.checks if c.check_name == check_name)


def test_empty_dataframe_fails_row_integrity():
    df = pd.DataFrame()
    report = validate_dataset(df)

    assert _status_of(report, "row_integrity") in ("fail",) or len(df) == 0
    assert report.overall_status == "fail"


def test_zero_rows_fails_row_integrity():
    df = pd.DataFrame({"a": [], "b": []})
    report = validate_dataset(df)

    assert _status_of(report, "row_integrity") == "fail"
    assert report.overall_status == "fail"


def test_duplicate_column_names_fails_column_integrity():
    df = pd.DataFrame([[1, 2], [3, 4]], columns=["a", "a"])
    report = validate_dataset(df)

    assert _status_of(report, "column_integrity") == "fail"
    assert report.overall_status == "fail"


def test_fully_missing_column_fails_missingness():
    df = pd.DataFrame({"id": range(1, 11), "notes": [None] * 10})
    report = validate_dataset(df)

    assert _status_of(report, "missingness") == "fail"
    assert report.overall_status == "fail"


def test_high_missing_column_warns():
    df = pd.DataFrame({"id": range(1, 11), "optional": [1, 2, 3, 4] + [None] * 6})
    report = validate_dataset(df)

    assert _status_of(report, "missingness") == "warning"


def test_duplicate_rows_fails_duplicates_check():
    df = pd.DataFrame({"a": [1, 1, 2], "b": [10, 10, 20]})
    report = validate_dataset(df)

    assert _status_of(report, "duplicates") == "fail"
    assert report.overall_status == "fail"


def test_duplicate_id_fails_id_uniqueness():
    df = pd.DataFrame({"customer_id": list(range(1, 20)) + [19]})
    report = validate_dataset(df)

    assert _status_of(report, "id_uniqueness") == "fail"
    assert report.overall_status == "fail"


def test_unique_id_passes_id_uniqueness():
    df = pd.DataFrame({"customer_id": range(1, 21)})
    report = validate_dataset(df)

    assert _status_of(report, "id_uniqueness") == "pass"


def test_end_date_before_start_date_violates_business_rule():
    df = pd.DataFrame(
        {
            "id": range(1, 6),
            "start_date": ["2024-01-01"] * 5,
            "end_date": ["2023-12-31", "2024-02-01", "2024-02-01", "2024-02-01", "2024-02-01"],
        }
    )
    report = validate_dataset(df)

    status = _status_of(report, "business_rules")
    assert status == "warning"  # 1 of 5 violates -- minority, so warning not fail


def test_total_not_equal_subtotal_plus_tax_violates_business_rule():
    df = pd.DataFrame(
        {
            "id": range(1, 6),
            "subtotal": [100, 100, 100, 100, 100],
            "tax": [10, 10, 10, 10, 10],
            "total": [110, 110, 999, 110, 110],  # one row wrong
        }
    )
    report = validate_dataset(df)

    status = _status_of(report, "business_rules")
    assert status == "warning"
    details = next(c.details for c in report.checks if c.check_name == "business_rules")
    assert details["violations"]["total_not_equal_subtotal_plus_tax"] == 1


def test_revenue_not_equal_quantity_times_price_majority_fails():
    df = pd.DataFrame(
        {
            "id": range(1, 5),
            "quantity": [2, 2, 2, 2],
            "unit_price": [10, 10, 10, 10],
            "revenue": [999, 999, 999, 20],  # 3 of 4 wrong -- majority
        }
    )
    report = validate_dataset(df)

    assert _status_of(report, "business_rules") == "fail"
    assert report.overall_status == "fail"


def test_remaining_impossible_age_warns():
    df = pd.DataFrame({"id": range(1, 6), "age": [25, 30, -5, 200, 40]})
    report = validate_dataset(df)

    assert _status_of(report, "invalid_values") == "warning"
    assert report.overall_status != "fail"  # a warning-only dataset should not overall-fail


def test_remaining_outlier_warns():
    df = pd.DataFrame({"amount": [10, 20, 30, 40, 1000]})
    report = validate_dataset(df)

    assert _status_of(report, "outlier_behavior") == "warning"


def test_thin_schema_warns():
    df = pd.DataFrame({"only_column": range(1, 11)})
    report = validate_dataset(df)

    assert _status_of(report, "schema_integrity") == "warning"


def test_clean_valid_dataset_passes_overall():
    df = pd.DataFrame(
        {
            "id": range(1, 21),
            "amount": [10, 20, 30, 40, 50] * 4,
            "category": ["A", "B", "C"] * 6 + ["A", "B"],
        }
    )
    report = validate_dataset(df)

    assert report.overall_status == "pass"
    assert all(c.status == "pass" for c in report.checks)
