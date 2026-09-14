import pandas as pd

from app.services.issue_detection import detect_issues
from app.services.platform_rules.looker import evaluate
from app.services.profiling import profile_dataset
from app.services.semantic_roles import classify_columns


def _assess(df: pd.DataFrame):
    profile = profile_dataset(df)
    issues = detect_issues(df, profile)
    roles = classify_columns(profile)
    return evaluate(df, profile, issues, roles)


def _status_of(report, check_name):
    return next(c.status for c in report.checks if c.check_name == check_name)


def test_duplicate_rows_flag_grain_concern():
    df = pd.DataFrame({"id": [1, 1, 2, 3], "amount": [10, 10, 20, 30]})
    report = _assess(df)
    assert _status_of(report, "grain_concern") == "warning"


def test_no_duplicates_grain_passes():
    df = pd.DataFrame({"id": range(1, 21), "amount": range(20)})
    report = _assess(df)
    assert _status_of(report, "grain_concern") == "pass"


def test_inconsistent_naming_warns():
    df = pd.DataFrame({"Customer Name": range(20), "id": range(20)})
    report = _assess(df)
    assert _status_of(report, "naming_consistency") == "warning"


def test_snake_case_naming_passes():
    df = pd.DataFrame({"customer_name": range(20), "id": range(20)})
    report = _assess(df)
    assert _status_of(report, "naming_consistency") == "pass"
