import pandas as pd

from app.services.issue_detection import detect_issues
from app.services.platform_rules.common import PlatformCheck, compute_score
from app.services.platform_rules.powerbi import evaluate
from app.services.profiling import profile_dataset
from app.services.semantic_roles import classify_columns


def _assess(df: pd.DataFrame):
    profile = profile_dataset(df)
    issues = detect_issues(df, profile)
    roles = classify_columns(profile)
    return evaluate(df, profile, issues, roles), profile, issues


def _status_of(report, check_name):
    return next(c.status for c in report.checks if c.check_name == check_name)


def _details_of(report, check_name):
    return next(c.details for c in report.checks if c.check_name == check_name)


def test_duplicate_key_fails():
    df = pd.DataFrame({"customer_id": list(range(1, 20)) + [19], "amount": range(20)})
    report, _, _ = _assess(df)

    assert _status_of(report, "duplicate_keys") == "fail"
    assert report.status in ("NEEDS_CLEANING", "NOT_READY")


def test_unique_key_passes():
    df = pd.DataFrame({"customer_id": range(1, 21), "amount": range(20)})
    report, _, _ = _assess(df)

    assert _status_of(report, "duplicate_keys") == "pass"


def test_no_date_column_warns():
    df = pd.DataFrame({"id": range(1, 21), "amount": range(20)})
    report, _, _ = _assess(df)

    assert _status_of(report, "date_dimension_present") == "warning"


def test_date_column_present_passes():
    dates = [f"2024-01-{i:02d}" for i in range(1, 21)]
    df = pd.DataFrame({"id": range(1, 21), "order_date": dates})
    report, _, _ = _assess(df)

    assert _status_of(report, "date_dimension_present") == "pass"


def test_high_cardinality_field_reused_from_issue_detection():
    df = pd.DataFrame({"comments": [f"unique free text {i}" for i in range(20)]})
    report, _, issues = _assess(df)

    assert any(i.issue_type == "high_cardinality" for i in issues)
    assert _status_of(report, "high_cardinality_fields") == "warning"


def test_measures_and_dimension_attributes_identified():
    df = pd.DataFrame(
        {
            "id": range(1, 21),
            "amount": [10, 20, 30, 40, 50] * 4,
            "category": ["A", "B", "C"] * 6 + ["A", "B"],
        }
    )
    report, _, _ = _assess(df)

    assert "amount" in _details_of(report, "measures_identified")["columns"]
    assert "category" in _details_of(report, "dimension_attributes_identified")["columns"]


def test_currency_like_column_flagged():
    df = pd.DataFrame({"id": range(1, 6), "unit_price": [10, 20, 30, 40, 50]})
    report, _, _ = _assess(df)

    assert "unit_price" in _details_of(report, "currency_percentage_representation")["currency_like"]


def test_table_role_classified_as_fact_when_more_measures():
    df = pd.DataFrame(
        {
            "id": range(1, 21),
            "quantity": range(20),
            "unit_price": range(20),
            "revenue": range(20),
        }
    )
    report, _, _ = _assess(df)
    assert _details_of(report, "table_role")["table_role"] == "fact"


def test_table_role_classified_as_dimension_when_mostly_categorical():
    df = pd.DataFrame(
        {
            "id": range(1, 21),
            "category": ["A", "B", "C"] * 6 + ["A", "B"],
            "region": ["East", "West"] * 10,
            "segment": ["Retail", "Wholesale", "Online"] * 6 + ["Retail", "Wholesale"],
        }
    )
    report, _, _ = _assess(df)
    assert _details_of(report, "table_role")["table_role"] == "dimension"


def test_compute_score_hand_verified():
    checks = [
        PlatformCheck("a", "pass", "ok"),
        PlatformCheck("b", "warning", "minor issue"),
        PlatformCheck("c", "fail", "major issue"),
        PlatformCheck("d", "not_applicable", "n/a"),
    ]
    # 100 - 5 (warning) - 15 (fail) - 0 (pass) - 0 (n/a) = 80
    assert compute_score(checks) == 80


def test_compute_score_clamped_at_zero():
    checks = [PlatformCheck(f"c{i}", "fail", "bad") for i in range(10)]
    assert compute_score(checks) == 0


def test_compute_score_perfect_dataset():
    checks = [PlatformCheck("a", "pass", "ok"), PlatformCheck("b", "pass", "ok")]
    assert compute_score(checks) == 100
