import csv

import pandas as pd

from app.services.audit_logging import (
    AUDIT_COLUMNS,
    ROW_DETAIL_LIMIT,
    append_rows_to_csv,
    build_log_rows,
)
from app.services.cleaning import apply_cleaning
from app.services.issue_detection import detect_issues
from app.services.profiling import profile_dataset


def test_small_number_of_changes_produces_one_row_each():
    df = pd.DataFrame(
        {
            "id": range(1, 6),
            "status": ["active", "active", "N/A", "active", "inactive"],
        }
    )
    profile = profile_dataset(df)
    issues = detect_issues(df, profile)
    cleaning_result = apply_cleaning(df, issues)

    audit_rows, cleaning_rows = build_log_rows("run_1", "data.csv", issues, cleaning_result.log)

    placeholder_rows = [r for r in cleaning_rows if r["issue_type"] == "missing_value_placeholder"]
    assert len(placeholder_rows) == 1  # only one placeholder value in this dataset
    assert placeholder_rows[0]["row_reference"] == 2
    assert placeholder_rows[0]["original_value"] == "N/A"
    assert placeholder_rows[0]["status"] == "applied"


def test_large_number_of_changes_is_aggregated():
    values = ["N/A"] * (ROW_DETAIL_LIMIT + 10) + ["active"] * 5
    df = pd.DataFrame({"id": range(len(values)), "status": values})
    profile = profile_dataset(df)
    issues = detect_issues(df, profile)
    cleaning_result = apply_cleaning(df, issues)

    audit_rows, cleaning_rows = build_log_rows("run_2", "data.csv", issues, cleaning_result.log)

    placeholder_rows = [r for r in cleaning_rows if r["issue_type"] == "missing_value_placeholder"]
    assert len(placeholder_rows) == 1  # aggregated into a single row
    assert "aggregated" in placeholder_rows[0]["row_reference"]
    assert str(ROW_DETAIL_LIMIT + 10) in placeholder_rows[0]["row_reference"]


def test_low_confidence_issue_only_appears_in_audit_not_cleaning():
    df = pd.DataFrame({"amount": [10, 20, 30, 40, 1000]})
    profile = profile_dataset(df)
    issues = detect_issues(df, profile)
    cleaning_result = apply_cleaning(df, issues)

    audit_rows, cleaning_rows = build_log_rows("run_3", "data.csv", issues, cleaning_result.log)

    outlier_audit_rows = [r for r in audit_rows if r["issue_type"] == "outlier"]
    outlier_cleaning_rows = [r for r in cleaning_rows if r["issue_type"] == "outlier"]

    assert len(outlier_audit_rows) == 1
    assert outlier_audit_rows[0]["status"] == "flagged_for_review"
    assert outlier_audit_rows[0]["confidence"] == "LOW"
    assert outlier_cleaning_rows == []


def test_every_issue_produces_at_least_one_audit_row():
    df = pd.DataFrame(
        {
            "id": range(1, 6),
            "status": ["active", "active", "N/A", "active", "inactive"],
            "amount": [10, 20, 30, 40, 1000],
        }
    )
    profile = profile_dataset(df)
    issues = detect_issues(df, profile)
    cleaning_result = apply_cleaning(df, issues)

    audit_rows, _ = build_log_rows("run_4", "data.csv", issues, cleaning_result.log)

    audit_issue_types = {r["issue_type"] for r in audit_rows}
    detected_issue_types = {i.issue_type for i in issues}
    assert audit_issue_types == detected_issue_types


def test_append_rows_to_csv_creates_then_appends(tmp_path):
    path = tmp_path / "audit_log.csv"
    rows_1 = [{col: f"r1_{col}" for col in AUDIT_COLUMNS}]
    rows_2 = [{col: f"r2_{col}" for col in AUDIT_COLUMNS}]

    append_rows_to_csv(path, rows_1)
    append_rows_to_csv(path, rows_2)

    with open(path, newline="", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    assert len(reader) == 2
    assert reader[0]["run_id"] == "r1_run_id"
    assert reader[1]["run_id"] == "r2_run_id"

    with open(path, encoding="utf-8") as f:
        header_count = sum(1 for line in f if line.startswith("timestamp,"))
    assert header_count == 1  # header written exactly once


def test_append_rows_to_csv_noop_for_empty_rows(tmp_path):
    path = tmp_path / "audit_log.csv"
    append_rows_to_csv(path, [])
    assert not path.exists()
