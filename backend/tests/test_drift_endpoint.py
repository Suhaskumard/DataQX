import uuid

import pandas as pd
from fastapi.testclient import TestClient

from app.core.config import get_settings
from main import app

client = TestClient(app)


def _upload(content: bytes, filename: str) -> str:
    response = client.post("/api/upload", files={"files": (filename, content, "text/csv")})
    assert response.status_code == 200
    return response.json()["run_id"]


def test_same_filename_second_upload_detects_drift():
    settings = get_settings()
    csv_before = pd.read_csv(settings.reports_dir / "drift_report.csv").shape[0] if (
        settings.reports_dir / "drift_report.csv"
    ).exists() else 0

    # Unique filename per test invocation: analyze.py persists profile history to the
    # real reports/history/ directory (not a test-isolated tmp path, matching this
    # project's established pattern of testing against real execution), so reusing a
    # fixed filename across separate test runs would find leftover history from a
    # previous run and break the "first upload = no history" assumption.
    dataset_name = f"customers_{uuid.uuid4().hex[:8]}.csv"

    # First version: 20 rows, "status" column with 2% missing, no "region" column.
    v1_rows = ["1"] * 49 + [""]
    content_v1 = ("id,status\n" + "\n".join(f"{i},{v}" for i, v in enumerate(v1_rows))).encode()
    run_id_1 = _upload(content_v1, dataset_name)

    analyze_1 = client.post("/api/analyze", json={"run_id": run_id_1})
    assert analyze_1.status_code == 200

    drift_1 = client.get(f"/api/drift/{run_id_1}").json()
    file_drift_1 = drift_1["files"][dataset_name]
    assert file_drift_1["overall_status"] == "no_history"
    assert file_drift_1["compared_against"] is None

    # Second version: same filename, but a new "region" column and much higher missingness.
    v2_rows = ["1"] * 41 + [""] * 9  # 18% missing, vs 2% before
    content_v2 = (
        "id,status,region\n" + "\n".join(f"{i},{v},East" for i, v in enumerate(v2_rows))
    ).encode()
    run_id_2 = _upload(content_v2, dataset_name)

    analyze_2 = client.post("/api/analyze", json={"run_id": run_id_2})
    assert analyze_2.status_code == 200

    drift_2 = client.get(f"/api/drift/{run_id_2}").json()
    file_drift_2 = drift_2["files"][dataset_name]
    assert file_drift_2["overall_status"] == "drift_detected"
    assert file_drift_2["compared_against"] == run_id_1

    finding_types = {f["drift_type"] for f in file_drift_2["findings"]}
    assert "schema_drift_new_columns" in finding_types
    assert "missingness_drift" in finding_types

    new_col_finding = next(f for f in file_drift_2["findings"] if f["drift_type"] == "schema_drift_new_columns")
    assert new_col_finding["details"]["new_columns"] == ["region"]

    # Cumulative reports/drift_report.csv gains rows from both analyses.
    drift_csv_path = settings.reports_dir / "drift_report.csv"
    assert drift_csv_path.exists()
    drift_csv = pd.read_csv(drift_csv_path)
    assert len(drift_csv) >= csv_before + 2
    assert (drift_csv["run_id"] == run_id_1).any()
    assert (drift_csv["run_id"] == run_id_2).any()


def test_drift_endpoint_404_for_nonexistent_run():
    response = client.get("/api/drift/run_does_not_exist")
    assert response.status_code == 404
