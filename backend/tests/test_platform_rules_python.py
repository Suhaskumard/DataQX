import pandas as pd

from app.services.issue_detection import detect_issues
from app.services.platform_rules.python_ import evaluate
from app.services.profiling import profile_dataset
from app.services.semantic_roles import classify_columns


def _assess(df: pd.DataFrame):
    profile = profile_dataset(df)
    issues = detect_issues(df, profile)
    roles = classify_columns(profile)
    return evaluate(df, profile, issues, roles)


def _status_of(report, check_name):
    return next(c.status for c in report.checks if c.check_name == check_name)


def test_identifier_excluded_from_features():
    df = pd.DataFrame({"customer_id": range(1, 21), "amount": range(20)})
    report = _assess(df)
    assert report.field_roles["customer_id"] == "Identifier"
    feature_check = next(c for c in report.checks if c.check_name == "possible_feature_variables")
    assert "customer_id" not in feature_check.details["columns"]


def test_target_variable_guessed_by_name():
    df = pd.DataFrame({"amount": range(20), "churn": [0, 1] * 10})
    report = _assess(df)
    target_check = next(c for c in report.checks if c.check_name == "possible_target_variable")
    assert "churn" in target_check.details["columns"]


def test_outlier_detected_and_flagged():
    df = pd.DataFrame({"amount": [10, 20, 30, 40, 1000]})
    report = _assess(df)
    assert _status_of(report, "outliers") == "warning"


def test_constant_column_flagged():
    df = pd.DataFrame({"id": range(1, 21), "flag": ["same"] * 20})
    report = _assess(df)
    assert _status_of(report, "constant_columns") == "warning"
