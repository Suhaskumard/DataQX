import pandas as pd

from app.services.cleaning import apply_cleaning
from app.services.data_dictionary import DATA_DICTIONARY_COLUMNS, build_data_dictionary
from app.services.issue_detection import detect_issues
from app.services.lineage import build_lineage
from app.services.profiling import profile_dataset
from app.services.semantic_roles import classify_columns, role_labels_by_column


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
    # No platform readiness was computed for this call -- platform columns must be
    # blank, never a fabricated role.
    assert row["power_bi_role"] is None
    assert row["sql_role"] is None


def test_data_dictionary_carries_real_platform_field_roles():
    df = pd.DataFrame({"customer_id": range(1, 11), "revenue": range(10)})
    profile = profile_dataset(df)
    issues = detect_issues(df, profile)
    roles = classify_columns(profile)

    from app.services.platform_rules.powerbi import evaluate as evaluate_powerbi
    from app.services.platform_rules.sql import evaluate as evaluate_sql

    platform_field_roles = {
        "power_bi": evaluate_powerbi(df, profile, issues, roles).field_roles,
        "sql": evaluate_sql(df, profile, issues, roles).field_roles,
    }
    dictionary = build_data_dictionary(profile, [], [], platform_field_roles)

    id_row = next(r for r in dictionary if r["original_name"] == "customer_id")
    assert id_row["power_bi_role"] == "Key"
    assert id_row["sql_role"] == "Primary Key Candidate"


def test_data_dictionary_semantic_role_matches_backend_classifier_exactly():
    # Single source of truth: the dictionary's "semantic_role" must be exactly
    # what app.services.semantic_roles.classify_columns() computed -- no second,
    # independent guess (e.g. a frontend heuristic off data_type) is allowed to
    # silently diverge from this real, already-computed classification.
    df = pd.DataFrame(
        {
            "customer_id": range(1, 11),
            "signup_date": [f"2024-01-{i:02d}" for i in range(1, 11)],
            "revenue": [float(i) for i in range(10)],
            "category": ["A", "B"] * 5,
        }
    )
    profile = profile_dataset(df)
    roles = classify_columns(profile)
    expected_labels = role_labels_by_column(roles)

    dictionary = build_data_dictionary(profile, [], [], semantic_roles=expected_labels)

    for row in dictionary:
        assert row["semantic_role"] == expected_labels.get(row["original_name"])

    assert next(r for r in dictionary if r["original_name"] == "customer_id")["semantic_role"] == "Identifier"
    assert next(r for r in dictionary if r["original_name"] == "signup_date")["semantic_role"] == "Date"
    assert next(r for r in dictionary if r["original_name"] == "revenue")["semantic_role"] == "Measure"
    assert next(r for r in dictionary if r["original_name"] == "category")["semantic_role"] == "Dimension"
