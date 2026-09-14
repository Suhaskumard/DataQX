import pandas as pd

from app.services.issue_detection import detect_issues
from app.services.platform_rules.sql import evaluate
from app.services.profiling import profile_dataset
from app.services.semantic_roles import classify_columns


def _assess(df: pd.DataFrame):
    profile = profile_dataset(df)
    issues = detect_issues(df, profile)
    roles = classify_columns(profile)
    return evaluate(df, profile, issues, roles)


def _status_of(report, check_name):
    return next(c.status for c in report.checks if c.check_name == check_name)


def test_primary_key_candidate_identified():
    df = pd.DataFrame({"customer_id": range(1, 21), "amount": range(20)})
    report = _assess(df)
    assert _status_of(report, "primary_key_candidates") == "pass"
    assert "customer_id" in report.field_roles
    assert report.field_roles["customer_id"] == "Primary Key Candidate"


def test_duplicate_primary_key_fails():
    df = pd.DataFrame({"customer_id": list(range(1, 20)) + [19], "amount": range(20)})
    report = _assess(df)
    assert _status_of(report, "duplicates") == "fail"


def test_foreign_key_candidate_detected_by_naming():
    df = pd.DataFrame({"order_id": range(1, 21), "customer_id": [1] * 20})
    report = _assess(df)
    assert "customer_id" in report.field_roles
    assert report.field_roles["customer_id"] == "Foreign Key Candidate"


def test_multi_value_cell_detected():
    df = pd.DataFrame({"id": range(1, 21), "tags": ["a,b,c"] * 20})
    report = _assess(df)
    assert _status_of(report, "multi_value_cells") == "warning"


def test_no_multi_value_cells_passes():
    df = pd.DataFrame({"id": range(1, 21), "tag": ["a"] * 20})
    report = _assess(df)
    assert _status_of(report, "multi_value_cells") == "pass"
