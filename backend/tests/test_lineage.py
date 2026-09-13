import pandas as pd

from app.services.cleaning import apply_cleaning
from app.services.issue_detection import detect_issues
from app.services.lineage import build_lineage
from app.services.profiling import profile_dataset


def _run_pipeline(df: pd.DataFrame):
    profile = profile_dataset(df)
    issues = detect_issues(df, profile)
    cleaning_result = apply_cleaning(df, issues)
    lineage = build_lineage(
        "data.csv",
        list(df.columns),
        list(cleaning_result.cleaned_df.columns),
        cleaning_result.log,
    )
    return lineage, cleaning_result


def test_column_with_single_transformation_gets_one_lineage_entry():
    df = pd.DataFrame(
        {
            "id": range(1, 6),
            "status": ["active", "active", "N/A", "active", "inactive"],
        }
    )
    lineage, _ = _run_pipeline(df)

    status_entries = [e for e in lineage if e.source_column == "status"]
    assert len(status_entries) == 1
    entry = status_entries[0]
    assert entry.output_column == "status"
    assert entry.transformation == "Convert placeholder text to a proper missing value (NaN)."
    assert entry.rule == "missing_value_placeholder"
    assert entry.confidence == "MEDIUM"
    assert entry.reason  # non-empty


def test_column_with_two_transformations_gets_two_lineage_entries():
    # "notes" gets both a placeholder-adjacent whitespace fix; use a column that
    # triggers two distinct cleaning actions: whitespace + missing placeholder both
    # target the same "mixed" column.
    df = pd.DataFrame(
        {
            "id": range(1, 21),
            "mixed": ["N/A"] + ["  padded  "] + [f"value {i}" for i in range(18)],
        }
    )
    lineage, cleaning_result = _run_pipeline(df)

    mixed_entries = [e for e in lineage if e.source_column == "mixed"]
    applied_types = {e.rule for e in mixed_entries}
    # Both whitespace_formatting and missing_value_placeholder should have fired on "mixed".
    assert "whitespace_formatting" in applied_types
    assert "missing_value_placeholder" in applied_types
    assert len(mixed_entries) == 2


def test_untouched_column_gets_unchanged_entry():
    df = pd.DataFrame({"id": range(1, 21), "amount": [10, 20, 30, 40, 50] * 4})
    lineage, _ = _run_pipeline(df)

    amount_entries = [e for e in lineage if e.source_column == "amount"]
    assert len(amount_entries) == 1
    assert amount_entries[0].transformation == "unchanged"
    assert amount_entries[0].rule is None
    assert amount_entries[0].confidence is None
    assert amount_entries[0].output_column == "amount"


def test_dropped_empty_column_gets_null_output_entry():
    df = pd.DataFrame({"id": range(1, 11), "notes": [None] * 10})
    lineage, cleaning_result = _run_pipeline(df)

    assert "notes" not in cleaning_result.cleaned_df.columns
    notes_entries = [e for e in lineage if e.source_column == "notes"]
    assert len(notes_entries) == 1
    assert notes_entries[0].output_column is None
    assert notes_entries[0].transformation == "dropped_empty_column"
    assert notes_entries[0].rule == "empty_column"
    assert notes_entries[0].confidence == "HIGH"


def test_duplicate_rows_never_produces_column_lineage_entry():
    df = pd.DataFrame({"a": [1, 1, 2], "b": [10, 10, 20]})
    lineage, cleaning_result = _run_pipeline(df)

    assert any(e.issue_type == "duplicate_rows" for e in cleaning_result.log)
    assert all(e.transformation != cleaning_result.log[0].action_taken or e.rule != "duplicate_rows" for e in lineage)
    assert not any(e.rule == "duplicate_rows" for e in lineage)


def test_all_lineage_ids_unique_within_one_dataset():
    df = pd.DataFrame(
        {
            "id": range(1, 21),
            "status": ["N/A"] + ["active"] * 19,
            "notes": [None] * 20,
            "amount": [10, 20, 30, 40, 50] * 4,
        }
    )
    lineage, _ = _run_pipeline(df)

    ids = [e.lineage_id for e in lineage]
    assert len(ids) == len(set(ids))
    assert len(lineage) == 4  # one entry per column in this dataset
