import pandas as pd
import pytest

from app.services.confidence import _CONFIDENCE_TABLE, classify_issue
from app.services.issue_detection import Issue, detect_issues
from app.services.profiling import profile_dataset


@pytest.mark.parametrize(
    "issue_type,expected_confidence",
    [
        ("whitespace_formatting", "HIGH"),
        ("empty_column", "HIGH"),
        ("duplicate_rows", "HIGH"),
        ("missing_value_placeholder", "MEDIUM"),
        ("category_inconsistency", "MEDIUM"),
        ("invalid_date", "MEDIUM"),
        ("duplicate_id", "LOW"),
        ("mixed_data_types", "LOW"),
        ("future_date", "LOW"),
        ("ambiguous_date_format", "LOW"),
        ("impossible_value", "LOW"),
        ("negative_value", "LOW"),
        ("outlier", "LOW"),
        ("constant_column", "LOW"),
        ("high_cardinality", "LOW"),
        ("missing_required_column", "LOW"),
    ],
)
def test_confidence_level_per_issue_type(issue_type, expected_confidence):
    issue = Issue(
        issue_type=issue_type,
        column="some_column",
        severity="medium",
        affected_count=3,
        description="test issue",
        details={"example_detail": "value"},
    )

    decision = classify_issue(issue)

    assert decision.confidence == expected_confidence
    assert decision.rule == issue_type
    assert decision.action  # non-empty recommended action
    assert decision.reason  # non-empty justification
    assert decision.evidence["column"] == "some_column"
    assert decision.evidence["affected_count"] == 3
    assert decision.evidence["example_detail"] == "value"


def test_unknown_issue_type_defaults_to_low():
    issue = Issue(
        issue_type="some_future_issue_type_not_yet_mapped",
        column=None,
        severity="low",
        affected_count=1,
        description="test issue",
    )

    decision = classify_issue(issue)

    assert decision.confidence == "LOW"
    assert "Unrecognized issue type" in decision.reason


def test_every_detectable_issue_type_has_an_explicit_mapping():
    """Build a dataset that triggers every Phase 6 detector and confirm none of the
    resulting issues silently fall back to the default LOW entry."""
    future = pd.Timestamp.now() + pd.Timedelta(days=100)
    df = pd.DataFrame(
        {
            "customer_id": list(range(1, 20)) + [19],  # duplicate id
            "status": ["active"] * 18 + ["N/A", "  extra space  "],  # placeholder + whitespace
            "country": ["USA", "usa", " USA "] + ["Canada"] * 8 + ["Mexico"] * 9,  # inconsistency
            "age": [25] * 18 + [-5, 200],  # impossible value
            "quantity": [5] * 19 + [-3],  # negative value
            "amount": [10, 20, 30, 40] + [50] * 15 + [1000],  # outlier
            "event_date": (["2023-01-01"] * 18 + ["garbage", str(future.date())]),  # invalid + future
            "constant_col": ["X"] * 20,
            "empty_col": [None] * 20,
        }
    )
    df.loc[0, "customer_id"] = df.loc[0, "customer_id"]  # no-op, keep column int dtype

    profile = profile_dataset(df)
    issues = detect_issues(df, profile)

    assert len(issues) > 0
    for issue in issues:
        assert issue.issue_type in _CONFIDENCE_TABLE, f"No confidence mapping for {issue.issue_type}"
