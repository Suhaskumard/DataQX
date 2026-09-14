import pandas as pd

from app.services.issue_detection import detect_issues
from app.services.platform_rules.tableau import evaluate
from app.services.profiling import profile_dataset
from app.services.semantic_roles import classify_columns


def _assess(df: pd.DataFrame):
    profile = profile_dataset(df)
    issues = detect_issues(df, profile)
    roles = classify_columns(profile)
    return evaluate(df, profile, issues, roles)


def _status_of(report, check_name):
    return next(c.status for c in report.checks if c.check_name == check_name)


def test_geographic_field_detected_by_name():
    df = pd.DataFrame({"country": ["US", "UK", "IN"] * 7, "amount": range(21)})
    report = _assess(df)
    assert _status_of(report, "potential_geographic_field") == "pass"


def test_no_geographic_field_is_not_applicable():
    df = pd.DataFrame({"id": range(1, 21), "amount": range(20)})
    report = _assess(df)
    assert _status_of(report, "potential_geographic_field") == "not_applicable"


def test_near_unique_numeric_column_warns_on_aggregation_safety():
    df = pd.DataFrame({"transaction_amount": [i * 1.5 for i in range(1, 21)]})
    report = _assess(df)
    assert _status_of(report, "aggregation_safety") == "warning"


def test_clean_dataset_is_ready_with_no_warnings():
    df = pd.DataFrame(
        {
            "order_date": [f"2024-01-{i:02d}" for i in range(1, 11)],
            "region": ["East", "West"] * 5,
            "revenue": [100, 200, 150, 300, 250, 100, 200, 150, 300, 250],
        }
    )
    report = _assess(df)
    assert report.status == "READY"
