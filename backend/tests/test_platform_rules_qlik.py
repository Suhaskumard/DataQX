import pandas as pd

from app.services.issue_detection import detect_issues
from app.services.platform_rules.qlik import evaluate
from app.services.profiling import DatasetProfile, profile_dataset
from app.services.semantic_roles import classify_columns


def _assess(df: pd.DataFrame):
    profile = profile_dataset(df)
    issues = detect_issues(df, profile)
    roles = classify_columns(profile)
    return evaluate(df, profile, issues, roles)


def _status_of(report, check_name):
    return next(c.status for c in report.checks if c.check_name == check_name)


def test_duplicate_key_fails_key_consistency():
    df = pd.DataFrame({"customer_id": list(range(1, 20)) + [19], "amount": range(20)})
    report = _assess(df)
    assert _status_of(report, "key_consistency") == "fail"


def test_unique_key_passes():
    df = pd.DataFrame({"customer_id": range(1, 21), "amount": range(20)})
    report = _assess(df)
    assert _status_of(report, "key_consistency") == "pass"


def test_duplicate_field_names_fail():
    # Real ingestion (pandas read_csv/read_excel) auto-mangles truly-duplicate
    # headers before this ever runs, so `profile_dataset()` is never exercised
    # against a genuinely duplicate-named DataFrame in production -- this check
    # exists as a defensive backstop, exercised directly against a minimal profile
    # rather than crashing pandas' own per-column profiling loop on duplicate names.
    df = pd.DataFrame([[1, 2], [3, 4]], columns=["id", "id"])
    empty_profile = DatasetProfile(
        row_count=2, column_count=2, file_size_bytes=None, memory_usage_bytes=0,
        duplicate_row_count=0, empty_row_count=0, empty_column_count=0,
        constant_columns=[], near_constant_columns=[], dataset_hash="test", columns=[],
    )
    report = evaluate(df, empty_profile, [], [])
    assert _status_of(report, "duplicate_fields") == "fail"


def test_circular_relationship_check_is_honest_not_applicable():
    df = pd.DataFrame({"customer_id": range(1, 21)})
    report = _assess(df)
    assert _status_of(report, "circular_relationship_risk") == "not_applicable"
