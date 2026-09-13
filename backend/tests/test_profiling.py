import math
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from app.services.profiling import (
    ColumnProfile,
    _profile_categorical,
    _profile_date,
    _profile_numeric,
    _profile_text,
    clean_column_name,
    infer_column_type,
    profile_dataset,
)


# --- clean_column_name ----------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Customer Name", "customer_name"),
        ("customer-name", "customer_name"),
        ("CUSTOMER NAME", "customer_name"),
        ("customer.name", "customer_name"),
        ("  weird__col!!", "weird_col"),
        ("", "column"),
    ],
)
def test_clean_column_name(raw, expected):
    assert clean_column_name(raw) == expected


# --- infer_column_type -----------------------------------------------------------


def test_infer_type_id_column():
    series = pd.Series(range(1, 21), name="id")
    assert infer_column_type(series, "id") == "id"


def test_infer_type_integer_column():
    series = pd.Series([1, 2, 3, 4, 5])
    assert infer_column_type(series, "quantity") == "integer"


def test_infer_type_float_column():
    series = pd.Series([1.5, 2.25, 3.75])
    assert infer_column_type(series, "amount") == "float"


def test_infer_type_boolean_column():
    series = pd.Series([True, False, True])
    assert infer_column_type(series, "is_active") == "boolean"


def test_infer_type_categorical_low_cardinality():
    series = pd.Series(["M", "F", "M", "F", "M", "F", "M", "F"])
    assert infer_column_type(series, "gender") == "categorical"


def test_infer_type_string_high_cardinality():
    series = pd.Series([f"free text value number {i}" for i in range(20)])
    assert infer_column_type(series, "notes") == "string"


def test_infer_type_date_like_strings():
    series = pd.Series(["2024-01-01", "2024-02-15", "2024-03-30"])
    assert infer_column_type(series, "order_date") == "date"


# --- _profile_numeric --------------------------------------------------------------


def test_profile_numeric_quantiles_and_outlier():
    series = pd.Series([10, 20, 30, 40, 1000])
    result = _profile_numeric(series)

    assert result["q25"] == pytest.approx(20.0)
    assert result["q50"] == pytest.approx(30.0)
    assert result["q75"] == pytest.approx(40.0)
    assert result["outlier_count"] == 1  # 1000 is far outside the IQR fence


def test_profile_numeric_no_outliers():
    series = pd.Series([10, 20, 30, 40, 50])
    result = _profile_numeric(series)
    assert result["outlier_count"] == 0


# --- _profile_categorical -----------------------------------------------------------


def test_profile_categorical_top_rare_and_inconsistencies():
    series = pd.Series(["USA", "usa", " USA ", "Canada", "Canada", "Mexico"])
    result = _profile_categorical(series)

    top_values = {c["value"] for c in result["top_categories"]}
    assert "Canada" in top_values

    rare_values = {c["value"] for c in result["rare_categories"]}
    assert "Mexico" in rare_values  # count == 1

    inconsistency_groups = result["potential_inconsistencies"]
    usa_group = next((g for g in inconsistency_groups if "USA" in g), None)
    assert usa_group is not None
    assert set(usa_group) == {"USA", "usa", " USA "}


# --- _profile_date --------------------------------------------------------------


def test_profile_date_invalid_and_future_counts():
    future_date = (datetime.now(timezone.utc) + timedelta(days=365)).strftime("%Y-%m-%d")
    series = pd.Series(["2023-01-01", "2023-06-15", "not-a-date", future_date])
    result = _profile_date(series)

    assert result["invalid_count"] == 1
    assert result["future_count"] == 1
    assert result["min"] is not None
    assert result["max"] is not None


# --- _profile_text --------------------------------------------------------------


def test_profile_text_whitespace_empty_case_and_unicode():
    series = pd.Series(["  leading", "trailing  ", "double  space", "", "café", "normal", "NORMAL"])
    result = _profile_text(series)

    assert result["whitespace_issue_count"] == 3  # leading, trailing, double-space
    assert result["empty_string_count"] == 1
    assert result["case_variation_count"] == 1  # "normal" vs "NORMAL"
    assert result["unicode_issue_count"] == 1  # "café"


# --- profile_dataset (integration) -----------------------------------------------


def test_profile_dataset_level_stats_duplicates_and_empty_rows():
    df = pd.DataFrame(
        {
            "a": [1, 1, 2, None],
            "b": [10, 10, 20, None],
        }
    )

    profile = profile_dataset(df)

    assert profile.row_count == 4
    assert profile.column_count == 2
    assert profile.duplicate_row_count == 1  # row 1 duplicates row 0
    assert profile.empty_row_count == 1  # row 3 is all-null
    assert profile.empty_column_count == 0


def test_profile_dataset_constant_near_constant_and_empty_columns():
    df = pd.DataFrame(
        {
            "constant_col": ["X"] * 20,
            "near_col": ["A"] * 19 + ["B"],
            "empty_col": [None] * 20,
        }
    )

    profile = profile_dataset(df)

    assert profile.constant_columns == ["constant_col"]
    assert profile.near_constant_columns == ["near_col"]
    assert profile.empty_column_count == 1
    # Empty columns must not also appear in constant/near-constant lists.
    assert "empty_col" not in profile.constant_columns
    assert "empty_col" not in profile.near_constant_columns


def test_profile_dataset_numeric_column_end_to_end():
    df = pd.DataFrame({"id": range(1, 6), "amount": [10, 20, 30, 40, 50]})

    profile = profile_dataset(df)
    amount_col = next(c for c in profile.columns if c.original_name == "amount")

    assert amount_col.inferred_type in ("integer",)
    assert amount_col.min == 10.0
    assert amount_col.max == 50.0
    assert amount_col.mean == pytest.approx(30.0)
    assert amount_col.median == pytest.approx(30.0)
    assert amount_col.std == pytest.approx(math.sqrt(250), rel=1e-6)
    assert amount_col.zero_count == 0
    assert amount_col.negative_count == 0

    id_col = next(c for c in profile.columns if c.original_name == "id")
    assert id_col.inferred_type == "id"


def test_profile_dataset_hash_consistent_for_same_content(tmp_path):
    path_a = tmp_path / "a.csv"
    path_b = tmp_path / "b.csv"
    path_a.write_text("x,y\n1,2\n3,4\n", encoding="utf-8")
    path_b.write_text("x,y\n1,2\n3,4\n", encoding="utf-8")  # identical content

    df = pd.read_csv(path_a)
    profile_a = profile_dataset(df, source_path=path_a)
    profile_b = profile_dataset(df, source_path=path_b)

    assert profile_a.dataset_hash == profile_b.dataset_hash

    path_c = tmp_path / "c.csv"
    path_c.write_text("x,y\n1,2\n3,5\n", encoding="utf-8")  # different content
    df_c = pd.read_csv(path_c)
    profile_c = profile_dataset(df_c, source_path=path_c)
    assert profile_c.dataset_hash != profile_a.dataset_hash


def test_profile_dataset_missing_and_unique_percentages():
    df = pd.DataFrame({"col": [1, 2, 2, None]})
    profile = profile_dataset(df)
    col = profile.columns[0]

    assert col.missing_count == 1
    assert col.missing_percentage == pytest.approx(25.0)
    assert col.unique_count == 2  # {1, 2}
    assert col.unique_percentage == pytest.approx(2 / 3 * 100)
