import pandas as pd

from app.services.issue_detection import detect_issues
from app.services.powerbi import PowerBICheck, assess_single_file_readiness, compute_score
from app.services.profiling import profile_dataset


def _assess(df: pd.DataFrame):
    profile = profile_dataset(df)
    issues = detect_issues(df, profile)
    return assess_single_file_readiness(df, profile, issues), profile, issues


def _status_of(report, check_name):
    return next(c.status for c in report.checks if c.check_name == check_name)


def test_duplicate_key_fails():
    df = pd.DataFrame({"customer_id": list(range(1, 20)) + [19], "amount": range(20)})
    report, _, _ = _assess(df)

    assert _status_of(report, "duplicate_keys") == "fail"


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

    measures_check = next(c for c in report.checks if c.check_name == "measures_identified")
    assert "amount" in measures_check.details["columns"]

    attrs_check = next(c for c in report.checks if c.check_name == "dimension_attributes_identified")
    assert "category" in attrs_check.details["columns"]


def test_currency_like_column_flagged():
    df = pd.DataFrame({"id": range(1, 6), "unit_price": [10, 20, 30, 40, 50]})
    report, _, _ = _assess(df)

    check = next(c for c in report.checks if c.check_name == "currency_percentage_representation")
    assert "unit_price" in check.details["currency_like"]


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
    assert report.table_role == "fact"


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
    assert report.table_role == "dimension"


def test_compute_score_hand_verified():
    checks = [
        PowerBICheck("a", "pass", "ok"),
        PowerBICheck("b", "warning", "minor issue"),
        PowerBICheck("c", "fail", "major issue"),
        PowerBICheck("d", "not_applicable", "n/a"),
    ]
    # 100 - 5 (warning) - 15 (fail) - 0 (pass) - 0 (n/a) = 80
    assert compute_score(checks) == 80


def test_compute_score_clamped_at_zero():
    checks = [PowerBICheck(f"c{i}", "fail", "bad") for i in range(10)]
    assert compute_score(checks) == 0


def test_compute_score_perfect_dataset():
    checks = [PowerBICheck("a", "pass", "ok"), PowerBICheck("b", "pass", "ok")]
    assert compute_score(checks) == 100
