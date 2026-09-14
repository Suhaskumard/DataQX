import pandas as pd

from app.services.issue_detection import detect_issues
from app.services.platform_rules.r_ import evaluate
from app.services.profiling import profile_dataset
from app.services.semantic_roles import classify_columns


def _assess(df: pd.DataFrame):
    profile = profile_dataset(df)
    issues = detect_issues(df, profile)
    roles = classify_columns(profile)
    return evaluate(df, profile, issues, roles)


def _status_of(report, check_name):
    return next(c.status for c in report.checks if c.check_name == check_name)


def test_categorical_columns_recommended_as_factors():
    df = pd.DataFrame({"category": ["A", "B", "C"] * 6 + ["A", "B"], "amount": range(20)})
    report = _assess(df)
    assert report.field_roles["category"] == "Factor Candidate"
    assert any("factor" in r.lower() for r in report.recommendations)


def test_date_column_recommends_as_date_parsing():
    dates = [f"2024-01-{i:02d}" for i in range(1, 21)]
    df = pd.DataFrame({"order_date": dates, "amount": range(20)})
    report = _assess(df)
    assert _status_of(report, "datetime_columns") == "pass"
    assert any("as.Date" in r for r in report.recommendations)


def test_duplicate_rows_flagged():
    df = pd.DataFrame({"id": [1, 1, 2, 3], "amount": [10, 10, 20, 30]})
    report = _assess(df)
    assert _status_of(report, "duplicates") == "warning"
