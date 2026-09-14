import hashlib
import json

import pandas as pd
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.services.audit_logging import AUDIT_COLUMNS
from main import app

client = TestClient(app)


def _upload(content: bytes, filename: str = "data.csv") -> str:
    response = client.post("/api/upload", files={"files": (filename, content, "text/csv")})
    assert response.status_code == 200
    return response.json()["run_id"]


def test_clean_endpoint_produces_correct_output_and_preserves_raw():
    content = b"id,status,notes\n1,active,normal\n2,active,normal\n3,N/A,  spaced  \n4,inactive,normal\n"
    run_id = _upload(content)

    raw_path = get_settings().input_dir / run_id / "data.csv"
    raw_hash_before = hashlib.sha256(raw_path.read_bytes()).hexdigest()

    analyze_response = client.post("/api/analyze", json={"run_id": run_id})
    assert analyze_response.status_code == 200

    clean_response = client.post("/api/clean", json={"run_id": run_id})
    assert clean_response.status_code == 200
    body = clean_response.json()
    file_result = body["files"]["data.csv"]
    assert file_result["status"] == "cleaned"

    settings = get_settings()

    # Raw file must be byte-identical after cleaning.
    raw_hash_after = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    assert raw_hash_after == raw_hash_before

    csv_path = settings.repo_root / file_result["output_csv"]
    assert csv_path.exists()
    cleaned_text = csv_path.read_text(encoding="utf-8")
    assert "N/A" not in cleaned_text  # placeholder converted to real missing value
    assert "spaced" in cleaned_text and "  spaced  " not in cleaned_text  # whitespace trimmed

    xlsx_path = settings.repo_root / file_result["output_xlsx"]
    assert xlsx_path.exists()

    log_path = settings.runs_dir / run_id / "cleaning_log.json"
    assert log_path.exists()
    log_data = json.loads(log_path.read_text(encoding="utf-8"))
    log_issue_types = {entry["issue_type"] for entry in log_data["files"]["data.csv"]["log"]}
    assert "missing_value_placeholder" in log_issue_types
    assert "whitespace_formatting" in log_issue_types

    metadata = json.loads((settings.runs_dir / run_id / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "cleaned"
    # Phase 17 gap found while building Phase 18: quality_score was never actually
    # wired into run_metadata.json (only analytics_readiness was) -- now fixed.
    assert metadata["quality_score"] is not None

    # Phase 14: output_hash recorded for a published file, matching the real cleaned CSV.
    expected_output_hash = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    assert metadata["files"]["data.csv"]["output_hash"] == expected_output_hash
    assert metadata["processing_time_seconds"]["clean"] > 0

    # Per-run CSV cleaning log (S34's run-directory example).
    run_csv_path = settings.runs_dir / run_id / "cleaning_log.csv"
    assert run_csv_path.exists()
    run_csv = pd.read_csv(run_csv_path)
    assert set(run_csv.columns) == set(AUDIT_COLUMNS)
    assert "missing_value_placeholder" in run_csv["issue_type"].values
    assert "whitespace_formatting" in run_csv["issue_type"].values

    # Global, cumulative logs (S9/S33) -- this run's rows must be present.
    global_audit_path = settings.logs_dir / "audit_log.csv"
    global_cleaning_path = settings.logs_dir / "cleaning_log.csv"
    assert global_audit_path.exists()
    assert global_cleaning_path.exists()

    global_audit = pd.read_csv(global_audit_path)
    assert set(global_audit.columns) == set(AUDIT_COLUMNS)
    assert (global_audit["run_id"] == run_id).any()

    # Phase 17: quality score, before/after summary, data dictionary.
    quality = json.loads((settings.runs_dir / run_id / "quality_report.json").read_text(encoding="utf-8"))
    file_quality = quality["files"]["data.csv"]
    assert file_quality["after"]["overall_score"] >= file_quality["before"]["overall_score"]

    before_after = json.loads(
        (settings.runs_dir / run_id / "before_after_summary.json").read_text(encoding="utf-8")
    )
    # "N/A" is literal text pre-clean (missing_count doesn't see it) and becomes a
    # real NaN post-clean -- missing_values correctly INCREASES here, since cleaning
    # is revealing previously-hidden missingness, not losing data (see Phase 12's
    # rationale for why a naive "missingness up = bad" rule would be wrong).
    missing_metric = before_after["files"]["data.csv"]["missing_values"]
    assert missing_metric["after"] > missing_metric["before"]
    assert before_after["files"]["data.csv"]["quality_score"]["after"] >= before_after["files"]["data.csv"]["quality_score"]["before"]

    dictionary_path = settings.runs_dir / run_id / "data_dictionary.csv"
    assert dictionary_path.exists()
    dictionary = pd.read_csv(dictionary_path)
    assert "column_name" in dictionary.columns
    status_row = dictionary[dictionary["original_name"] == "status"].iloc[0]
    assert pd.notna(status_row["cleaning_actions"])


def test_analytics_readiness_endpoint_reflects_cleaned_data_after_clean_not_stale_raw_snapshot():
    # Real bug found via a live E2E run: /api/analytics-readiness (formerly
    # /api/powerbi) served the snapshot written once by /api/analyze on the RAW
    # data and never updated it, so after /api/clean removed a duplicate row
    # (fixing the duplicate-key violation and publishing a valid dataset), the
    # Dashboard/Analytics Readiness page kept showing the old, lower pre-clean
    # score forever -- contradicting the correct "after" figure already shown on
    # the Before/After page for the exact same run.
    content = b"id,value\n1,a\n2,b\n3,c\n4,d\n5,e\n6,f\n7,g\n8,h\n9,i\n9,i\n"
    run_id = _upload(content)

    assert client.post("/api/analyze", json={"run_id": run_id}).status_code == 200
    raw_readiness = client.get(f"/api/analytics-readiness/{run_id}").json()
    raw_powerbi = raw_readiness["files"]["data.csv"]["platforms"]["power_bi"]
    raw_check = {c["check_name"]: c for c in raw_powerbi["checks"]}
    assert raw_check["duplicate_keys"]["status"] == "fail"
    raw_score = raw_powerbi["score"]

    assert client.post("/api/clean", json={"run_id": run_id}).status_code == 200

    settings = get_settings()
    before_after = json.loads((settings.runs_dir / run_id / "before_after_summary.json").read_text(encoding="utf-8"))
    expected_after_score = before_after["files"]["data.csv"]["analytics_readiness"]["after"]

    updated_readiness = client.get(f"/api/analytics-readiness/{run_id}").json()
    updated_file = updated_readiness["files"]["data.csv"]
    updated_powerbi = updated_file["platforms"]["power_bi"]
    updated_check = {c["check_name"]: c for c in updated_powerbi["checks"]}

    assert updated_check["duplicate_keys"]["status"] == "pass"
    assert updated_file["overall_score"] == expected_after_score
    assert updated_powerbi["score"] > raw_score


def test_clean_endpoint_appends_across_multiple_runs_without_overwriting():
    settings = get_settings()
    global_audit_path = settings.logs_dir / "audit_log.csv"
    rows_before = len(pd.read_csv(global_audit_path)) if global_audit_path.exists() else 0

    run_id_a = _upload(b"id,status\n1,active\n2,N/A\n", filename="a.csv")
    run_id_b = _upload(b"id,status\n1,active\n2,N/A\n3,N/A\n", filename="b.csv")

    for run_id in (run_id_a, run_id_b):
        client.post("/api/analyze", json={"run_id": run_id})
        client.post("/api/clean", json={"run_id": run_id})

    global_audit = pd.read_csv(global_audit_path)
    assert len(global_audit) > rows_before
    assert (global_audit["run_id"] == run_id_a).any()
    assert (global_audit["run_id"] == run_id_b).any()


def test_clean_endpoint_rolls_back_for_unresolved_duplicate_id():
    rows = [f"{i},active" for i in range(1, 19)] + ["18,inactive"]
    content = ("customer_id,status\n" + "\n".join(rows) + "\n").encode()
    run_id = _upload(content, filename="dupid.csv")

    raw_path = get_settings().input_dir / run_id / "dupid.csv"
    raw_hash_before = hashlib.sha256(raw_path.read_bytes()).hexdigest()

    client.post("/api/analyze", json={"run_id": run_id})
    clean_response = client.post("/api/clean", json={"run_id": run_id})
    assert clean_response.status_code == 200
    body = clean_response.json()
    file_result = body["files"]["dupid.csv"]
    assert file_result["status"] == "rolled_back"
    assert "id_uniqueness" in file_result["reason"]
    assert file_result["validation_report"]["overall_status"] == "fail"

    settings = get_settings()

    # No cleaned output files should have been published.
    output_dir = settings.output_dir / run_id
    assert not output_dir.exists() or not any(output_dir.iterdir())

    # Raw file must remain byte-identical -- rollback never touches input.
    raw_hash_after = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    assert raw_hash_after == raw_hash_before

    rollback_path = settings.runs_dir / run_id / "rollback_report.json"
    assert rollback_path.exists()
    rollback_data = json.loads(rollback_path.read_text(encoding="utf-8"))
    assert rollback_data["files"]["dupid.csv"]["published"] is False

    metadata = json.loads((settings.runs_dir / run_id / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "rollback"
    # Phase 14: a rolled-back file never gets an output_hash -- nothing was published.
    assert metadata["files"]["dupid.csv"]["output_hash"] is None


def test_clean_endpoint_still_publishes_normal_data_after_gate_added():
    content = b"id,amount\n1,10\n2,20\n3,30\n4,40\n"
    run_id = _upload(content, filename="normal.csv")

    client.post("/api/analyze", json={"run_id": run_id})
    clean_response = client.post("/api/clean", json={"run_id": run_id})
    body = clean_response.json()
    file_result = body["files"]["normal.csv"]

    assert file_result["status"] == "cleaned"
    assert file_result["validation_report"]["overall_status"] in ("pass", "warning")

    settings = get_settings()
    csv_path = settings.repo_root / file_result["output_csv"]
    assert csv_path.exists()

    metadata = json.loads((settings.runs_dir / run_id / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "cleaned"


def test_clean_endpoint_404_for_nonexistent_run():
    response = client.post("/api/clean", json={"run_id": "run_does_not_exist"})
    assert response.status_code == 404
