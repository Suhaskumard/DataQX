import pandas as pd

from app.services.issue_detection import detect_issues
from app.services.platform_rules.lookerstudio import evaluate
from app.services.profiling import profile_dataset
from app.services.semantic_roles import classify_columns


def _assess(df: pd.DataFrame):
    profile = profile_dataset(df)
    issues = detect_issues(df, profile)
    roles = classify_columns(profile)
    return evaluate(df, profile, issues, roles)


def _status_of(report, check_name):
    return next(c.status for c in report.checks if c.check_name == check_name)


def test_unsafe_header_characters_warn():
    df = pd.DataFrame({"amount$": range(20), "id": range(20)})
    report = _assess(df)
    assert _status_of(report, "connector_friendly_headers") == "warning"


def test_no_numeric_field_warns_aggregation():
    df = pd.DataFrame({"name": [f"item{i}" for i in range(20)]})
    report = _assess(df)
    assert _status_of(report, "numeric_fields") == "warning"
    assert _status_of(report, "aggregation_usability") == "warning"


def test_numeric_field_present_passes_aggregation():
    df = pd.DataFrame({"amount": range(20), "category": ["A", "B"] * 10})
    report = _assess(df)
    assert _status_of(report, "aggregation_usability") == "pass"
