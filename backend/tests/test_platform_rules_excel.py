import pandas as pd

from app.services.issue_detection import detect_issues
from app.services.platform_rules.excel import evaluate
from app.services.profiling import profile_dataset
from app.services.semantic_roles import classify_columns


def _assess(df: pd.DataFrame):
    profile = profile_dataset(df)
    issues = detect_issues(df, profile)
    roles = classify_columns(profile)
    return evaluate(df, profile, issues, roles)


def _status_of(report, check_name):
    return next(c.status for c in report.checks if c.check_name == check_name)


def test_unnamed_column_fails():
    # A real, reachable case: pandas mangles truly-duplicate CSV headers on read
    # (e.g. "id" -> "id.1"), but a stray blank header from an exported spreadsheet
    # survives as a literal "Unnamed: N" column -- that's what this check must catch.
    df = pd.DataFrame({"id": range(1, 21), "Unnamed: 2": range(20)})
    report = _assess(df)
    assert _status_of(report, "single_header_row") == "fail"


def test_clean_headers_pass():
    df = pd.DataFrame({"id": range(1, 21), "amount": range(20)})
    report = _assess(df)
    assert _status_of(report, "single_header_row") == "pass"


def test_duplicate_rows_warn():
    df = pd.DataFrame({"id": [1, 1, 2, 3], "amount": [10, 10, 20, 30]})
    report = _assess(df)
    assert _status_of(report, "duplicate_rows") == "warning"


def test_clean_dataset_is_ready():
    df = pd.DataFrame({"id": range(1, 21), "amount": range(20), "category": ["A", "B"] * 10})
    report = _assess(df)
    assert report.status == "READY"
