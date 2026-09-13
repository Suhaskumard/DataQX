import pandas as pd

from app.services.issue_detection import detect_issues
from app.services.profiling import profile_dataset
from app.services.quality_score import compute_quality_score
from app.services.validation import validate_dataset


def _compute(df: pd.DataFrame, powerbi_score: float = 100.0):
    profile = profile_dataset(df)
    issues = detect_issues(df, profile)
    validation_report = validate_dataset(df)
    return compute_quality_score(df, profile, issues, validation_report, powerbi_score), profile, issues


def test_clean_dataset_scores_near_100_on_every_dimension():
    df = pd.DataFrame(
        {
            "id": range(1, 21),
            "amount": [10, 20, 30, 40, 50] * 4,
            "category": ["A", "B", "C"] * 6 + ["A", "B"],
        }
    )
    result, _, issues = _compute(df)

    assert issues == []
    assert result.dimensions["completeness"] == 100.0
    assert result.dimensions["validity"] == 100.0
    assert result.dimensions["consistency"] == 100.0
    assert result.dimensions["uniqueness"] == 100.0
    assert result.dimensions["integrity"] == 100.0
    assert result.dimensions["schema_quality"] == 100.0
    assert result.overall_score == 100


def test_duplicate_rows_reduce_uniqueness_dimension():
    df = pd.DataFrame({"a": [1, 1, 2, 3], "b": [10, 10, 20, 30]})
    result, profile, _ = _compute(df)

    # 1 duplicate row out of 4 = 25% -> uniqueness = 100 - 25 = 75
    assert profile.duplicate_row_count == 1
    assert result.dimensions["uniqueness"] == 75.0


def test_high_missingness_reduces_completeness_dimension():
    df = pd.DataFrame({"id": range(1, 11), "optional": [1, 2, 3, 4, 5] + [None] * 5})
    result, profile, _ = _compute(df)

    # id: 0% missing, optional: 50% missing -> average = 25% -> completeness = 75
    assert result.dimensions["completeness"] == 75.0


def test_constant_column_reduces_schema_quality_dimension():
    df = pd.DataFrame({"id": range(1, 11), "flag": ["X"] * 10})
    result, _, _ = _compute(df)

    # 1 constant column -> 100 - 10 = 90
    assert result.dimensions["schema_quality"] == 90.0


def test_powerbi_score_passed_through_directly():
    df = pd.DataFrame({"id": range(1, 11)})
    result, _, _ = _compute(df, powerbi_score=42.0)

    assert result.dimensions["powerbi_readiness"] == 42.0


def test_methodology_contains_real_formula_strings_for_every_dimension():
    df = pd.DataFrame({"id": range(1, 11)})
    result, _, _ = _compute(df)

    for dimension in result.dimensions:
        assert dimension in result.methodology
        assert len(result.methodology[dimension]) > 10  # a real sentence, not a placeholder
