import pandas as pd

from app.services.cleaning import apply_cleaning
from app.services.issue_detection import detect_issues
from app.services.profiling import profile_dataset
from app.services.rollback import evaluate_gate


def _clean(df: pd.DataFrame):
    profile = profile_dataset(df)
    issues = detect_issues(df, profile)
    return apply_cleaning(df, issues)


def test_unresolved_duplicate_id_blocks_publish():
    rows = [f"{i},active" for i in range(1, 19)] + ["18,inactive"]
    import io

    df = pd.read_csv(io.StringIO("customer_id,status\n" + "\n".join(rows)))
    cleaning_result = _clean(df)

    gate = evaluate_gate(cleaning_result.cleaned_df)

    assert gate.published is False
    assert gate.validation_report.overall_status == "fail"
    assert "id_uniqueness" in gate.reason


def test_majority_business_rule_violation_blocks_publish():
    df = pd.DataFrame(
        {
            "id": range(1, 5),
            "quantity": [2, 2, 2, 2],
            "unit_price": [10, 10, 10, 10],
            "revenue": [999, 999, 999, 20],  # 3 of 4 wrong
        }
    )
    cleaning_result = _clean(df)

    gate = evaluate_gate(cleaning_result.cleaned_df)

    assert gate.published is False
    assert "business_rules" in gate.reason


def test_clean_dataset_is_published():
    df = pd.DataFrame(
        {
            "id": range(1, 21),
            "amount": [10, 20, 30, 40, 50] * 4,
            "category": ["A", "B", "C"] * 6 + ["A", "B"],
        }
    )
    cleaning_result = _clean(df)

    gate = evaluate_gate(cleaning_result.cleaned_df)

    assert gate.published is True
    assert gate.reason is None
    assert gate.validation_report.overall_status == "pass"


def test_warning_only_dataset_is_still_published():
    df = pd.DataFrame({"id": range(1, 6), "amount": [10, 20, 30, 40, 1000]})
    cleaning_result = _clean(df)

    gate = evaluate_gate(cleaning_result.cleaned_df)

    assert gate.validation_report.overall_status == "warning"
    assert gate.published is True  # warnings never block publishing
    assert gate.reason is None
