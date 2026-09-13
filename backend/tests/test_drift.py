import pandas as pd

from app.services.drift import detect_drift, find_previous_profile, save_profile_snapshot
from app.services.profiling import profile_dataset


def _finding_types(report):
    return {f.drift_type for f in report.findings}


def test_no_drift_for_identical_profiles():
    df = pd.DataFrame({"id": range(1, 21), "amount": [10, 20, 30, 40, 50] * 4})
    profile_a = profile_dataset(df)
    profile_b = profile_dataset(df)

    report = detect_drift(profile_b, profile_a)

    assert report.overall_status == "no_drift"
    assert report.findings == []


def test_schema_drift_new_column():
    df_prev = pd.DataFrame({"id": range(1, 21)})
    df_curr = pd.DataFrame({"id": range(1, 21), "region": ["East"] * 20})

    report = detect_drift(profile_dataset(df_curr), profile_dataset(df_prev))

    assert "schema_drift_new_columns" in _finding_types(report)
    finding = next(f for f in report.findings if f.drift_type == "schema_drift_new_columns")
    assert finding.details["new_columns"] == ["region"]


def test_schema_drift_removed_column():
    df_prev = pd.DataFrame({"id": range(1, 21), "region": ["East"] * 20})
    df_curr = pd.DataFrame({"id": range(1, 21)})

    report = detect_drift(profile_dataset(df_curr), profile_dataset(df_prev))

    assert "schema_drift_removed_columns" in _finding_types(report)


def test_schema_drift_type_change():
    df_prev = pd.DataFrame({"id": range(1, 21), "value": [1, 2, 3, 4, 5] * 4})
    df_curr = pd.DataFrame({"id": range(1, 21), "value": [f"text {i}" for i in range(20)]})

    report = detect_drift(profile_dataset(df_curr), profile_dataset(df_prev))

    assert "schema_drift_type_change" in _finding_types(report)


def test_volume_drift_detected_on_large_row_count_change():
    df_prev = pd.DataFrame({"id": range(1, 101)})
    df_curr = pd.DataFrame({"id": range(1, 21)})  # 80% drop

    report = detect_drift(profile_dataset(df_curr), profile_dataset(df_prev))

    assert "volume_drift" in _finding_types(report)


def test_volume_drift_not_flagged_for_small_change():
    df_prev = pd.DataFrame({"id": range(1, 101)})
    df_curr = pd.DataFrame({"id": range(1, 106)})  # 5% increase

    report = detect_drift(profile_dataset(df_curr), profile_dataset(df_prev))

    assert "volume_drift" not in _finding_types(report)


def test_missingness_drift_matches_spec_example():
    # Previous: ~2% missing (1/50). Current: ~17% missing... let's use exact percents.
    prev_values = [1] * 49 + [None]  # 2% missing
    curr_values = [1] * 41 + [None] * 9  # 18% missing
    df_prev = pd.DataFrame({"id": range(50), "amount": prev_values})
    df_curr = pd.DataFrame({"id": range(50), "amount": curr_values})

    report = detect_drift(profile_dataset(df_curr), profile_dataset(df_prev))

    assert "missingness_drift" in _finding_types(report)
    finding = next(f for f in report.findings if f.drift_type == "missingness_drift")
    assert finding.column == "amount"


def test_category_drift_new_category():
    prev_values = ["A"] * 10 + ["B"] * 10
    curr_values = ["A"] * 10 + ["B"] * 8 + ["C"] * 2
    df_prev = pd.DataFrame({"category": prev_values})
    df_curr = pd.DataFrame({"category": curr_values})

    report = detect_drift(profile_dataset(df_curr), profile_dataset(df_prev))

    assert "category_drift" in _finding_types(report)


def test_distribution_drift_mean_shift():
    df_prev = pd.DataFrame({"id": range(1, 21), "amount": [10, 20, 30, 40, 50] * 4})
    df_curr = pd.DataFrame({"id": range(1, 21), "amount": [100, 200, 300, 400, 500] * 4})

    report = detect_drift(profile_dataset(df_curr), profile_dataset(df_prev))

    assert "distribution_drift_mean" in _finding_types(report)


# --- snapshot save/find round trip -----------------------------------------------


def test_save_and_find_previous_profile_round_trip(tmp_path):
    df = pd.DataFrame({"id": range(1, 21), "amount": [10, 20, 30, 40, 50] * 4})
    profile = profile_dataset(df)

    save_profile_snapshot(tmp_path, "sales.csv", "run_001", profile)

    found = find_previous_profile(tmp_path, "sales.csv", exclude_run_id="run_002")
    assert found is not None
    run_id, found_profile = found
    assert run_id == "run_001"
    assert found_profile.row_count == profile.row_count


def test_find_previous_profile_excludes_current_run(tmp_path):
    df = pd.DataFrame({"id": range(1, 21)})
    profile = profile_dataset(df)
    save_profile_snapshot(tmp_path, "sales.csv", "run_001", profile)

    found = find_previous_profile(tmp_path, "sales.csv", exclude_run_id="run_001")
    assert found is None


def test_find_previous_profile_returns_latest_when_multiple_exist(tmp_path):
    df = pd.DataFrame({"id": range(1, 21)})
    profile = profile_dataset(df)
    save_profile_snapshot(tmp_path, "sales.csv", "run_001", profile)
    save_profile_snapshot(tmp_path, "sales.csv", "run_002", profile)
    save_profile_snapshot(tmp_path, "sales.csv", "run_003", profile)

    found = find_previous_profile(tmp_path, "sales.csv", exclude_run_id="run_004")
    assert found is not None
    run_id, _ = found
    assert run_id == "run_003"


def test_find_previous_profile_none_for_different_dataset_name(tmp_path):
    df = pd.DataFrame({"id": range(1, 21)})
    profile = profile_dataset(df)
    save_profile_snapshot(tmp_path, "sales.csv", "run_001", profile)

    found = find_previous_profile(tmp_path, "other.csv", exclude_run_id="run_999")
    assert found is None
