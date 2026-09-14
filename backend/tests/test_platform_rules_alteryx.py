import pandas as pd

from app.services.issue_detection import detect_issues
from app.services.platform_rules.alteryx import evaluate
from app.services.profiling import profile_dataset
from app.services.semantic_roles import classify_columns


def _assess(df: pd.DataFrame):
    profile = profile_dataset(df)
    issues = detect_issues(df, profile)
    roles = classify_columns(profile)
    return evaluate(df, profile, issues, roles)


def _status_of(report, check_name):
    return next(c.status for c in report.checks if c.check_name == check_name)


def test_bad_field_names_warn():
    df = pd.DataFrame({"Customer Name!": range(20), "id": range(20)})
    report = _assess(df)
    assert _status_of(report, "field_naming") == "warning"


def test_clean_field_names_pass():
    df = pd.DataFrame({"customer_name": range(20), "id": range(20)})
    report = _assess(df)
    assert _status_of(report, "field_naming") == "pass"


def test_duplicate_join_key_fails():
    df = pd.DataFrame({"id": list(range(1, 20)) + [19], "value": range(20)})
    report = _assess(df)
    assert _status_of(report, "join_keys") == "fail"


def test_unique_join_key_passes():
    df = pd.DataFrame({"id": range(1, 21), "value": range(20)})
    report = _assess(df)
    assert _status_of(report, "join_keys") == "pass"


def test_constant_column_flags_schema_stability():
    df = pd.DataFrame({"id": range(1, 21), "flag": ["same"] * 20})
    report = _assess(df)
    assert _status_of(report, "schema_stability") == "warning"
