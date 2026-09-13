import pandas as pd

from app.services.cleaning import apply_cleaning
from app.services.data_dictionary import DATA_DICTIONARY_COLUMNS, build_data_dictionary
from app.services.issue_detection import detect_issues
from app.services.lineage import build_lineage
from app.services.profiling import profile_dataset


def test_data_dictionary_fixed_column_has_cleaning_actions_and_lineage_id():
    df = pd.DataFrame(
        {
            "id": range(1, 6),
            "status": ["active", "active", "N/A", "active", "inactive"],
        }
    )
    raw_profile = profile_dataset(df)
    issues = detect_issues(df, raw_profile)
    cleaning_result = apply_cleaning(df, issues)
    cleaned_profile = profile_dataset(cleaning_result.cleaned_df)

    lineage_entries = build_lineage(
        "data.csv", list(df.columns), list(cleaning_result.cleaned_df.columns), cleaning_result.log
    )

    dictionary = build_data_dictionary(cleaned_profile, lineage_entries, cleaning_result.log)

    status_row = next(r for r in dictionary if r["original_name"] == "status")
    assert status_row["cleaning_actions"] == "Convert placeholder text to a proper missing value (NaN)."
    assert status_row["lineage_id"] is not None
    assert status_row["nullable"] is True  # now has a real missing value

    id_row = next(r for r in dictionary if r["original_name"] == "id")
    assert id_row["cleaning_actions"] is None
    assert id_row["nullable"] is False


def test_data_dictionary_has_expected_columns_and_types():
    df = pd.DataFrame({"amount": [10, 20, 30, 40, 50]})
    profile = profile_dataset(df)
    dictionary = build_data_dictionary(profile, [], [])

    row = dictionary[0]
    assert set(row.keys()) == set(DATA_DICTIONARY_COLUMNS)
    assert row["column_name"] == "amount"
    assert row["min"] == 10.0
    assert row["max"] == 50.0
    assert "column" in row["description"].lower()
