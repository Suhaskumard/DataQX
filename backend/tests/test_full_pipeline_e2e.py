"""Phase 23 -- Full end-to-end pipeline test.

Runs one dataset through every stage of the pipeline in a single continuous run --
upload (with a project plan) -> analyze -> clean -> validate -> lineage -> drift ->
Power BI -> dictionary -> before/after -> quality -> report -> download -> performance
-- and asserts both the API response shape and the real on-disk artifact at every
step. No stage here is exercised in isolation elsewhere against this same run_id, so
this is the first test that proves the whole chain works together, not just each
link individually (DATAQX.pdf S62 "End-to-end" + S65 Phase 24's "verify every
artifact", pulled forward one phase as a regression baseline).
"""

from __future__ import annotations

import io
import json

from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.core.config import get_settings
from main import app

client = TestClient(app)

# Deliberately contains several S61 issue types: a missing value ("N/A"), a duplicate
# row (rows for id=3 repeated), and a bad/impossible age (-5) -- so every downstream
# stage (cleaning, validation, quality scoring, lineage, the PDF report) has real,
# non-trivial content to act on rather than a clean no-op dataset.
DATASET_CONTENT = (
    b"customer_id,status,age\n"
    b"1,active,25\n"
    b"2,active,30\n"
    b"3,N/A,-5\n"
    b"3,N/A,-5\n"
    b"4,inactive,40\n"
)
DATASET_FILENAME = "full_pipeline_customers.csv"
PROJECT_PLAN_TEXT = "# Full Pipeline E2E Test\nObjective: verify every stage produces real artifacts."


def test_full_pipeline_upload_through_download_produces_every_artifact():
    settings = get_settings()

    # ---- Upload (with a project plan, exercising Phase 13 integration) ----
    upload_response = client.post(
        "/api/upload",
        files={"files": (DATASET_FILENAME, DATASET_CONTENT, "text/csv")},
        data={"project_plan_text": PROJECT_PLAN_TEXT},
    )
    assert upload_response.status_code == 200
    upload_body = upload_response.json()
    run_id = upload_body["run_id"]
    assert upload_body["files"][0]["status"] == "saved"
    assert upload_body["project_plan"]["status"] == "saved"

    raw_path = settings.input_dir / run_id / DATASET_FILENAME
    assert raw_path.exists()
    assert raw_path.read_bytes() == DATASET_CONTENT  # original never modified

    # ---- Analyze ----
    analyze_response = client.post("/api/analyze", json={"run_id": run_id})
    assert analyze_response.status_code == 200
    analyze_body = analyze_response.json()
    assert analyze_body["files"][DATASET_FILENAME]["status"] == "profiled"
    assert (settings.runs_dir / run_id / "profile.json").exists()

    # ---- Clean ----
    clean_response = client.post("/api/clean", json={"run_id": run_id})
    assert clean_response.status_code == 200
    clean_body = clean_response.json()
    file_clean_result = clean_body["files"][DATASET_FILENAME]
    assert file_clean_result["status"] == "cleaned"
    stem = DATASET_FILENAME.rsplit(".", 1)[0]
    cleaned_csv_path = settings.output_dir / run_id / f"{stem}_cleaned.csv"
    assert cleaned_csv_path.exists()
    assert cleaned_csv_path.stat().st_size > 0
    assert (settings.logs_dir / "cleaning_log.csv").exists()

    # ---- Validate ----
    validate_response = client.post("/api/validate", json={"run_id": run_id})
    assert validate_response.status_code == 200
    validate_body = validate_response.json()
    assert validate_body["files"][DATASET_FILENAME]["status"] == "validated"
    assert (settings.runs_dir / run_id / "validation_report.json").exists()

    # ---- Lineage ----
    lineage_response = client.get(f"/api/lineage/{run_id}")
    assert lineage_response.status_code == 200
    lineage_body = lineage_response.json()
    assert lineage_body["run_id"] == run_id
    assert len(lineage_body["files"][DATASET_FILENAME]) > 0  # at least one real transformation recorded
    assert (settings.runs_dir / run_id / "data_lineage.json").exists()

    # ---- Drift ----
    drift_response = client.get(f"/api/drift/{run_id}")
    assert drift_response.status_code == 200
    drift_body = drift_response.json()
    assert drift_body["run_id"] == run_id
    assert DATASET_FILENAME in drift_body["files"]

    # ---- Power BI readiness ----
    powerbi_response = client.get(f"/api/powerbi/{run_id}")
    assert powerbi_response.status_code == 200
    powerbi_body = powerbi_response.json()
    file_powerbi = powerbi_body["files"][DATASET_FILENAME]
    assert isinstance(file_powerbi["score"], int)
    assert 0 <= file_powerbi["score"] <= 100

    # ---- Data dictionary ----
    dictionary_response = client.get(f"/api/dictionary/{run_id}")
    assert dictionary_response.status_code == 200
    dictionary_rows = dictionary_response.json()["files"][DATASET_FILENAME]
    column_names = {row["original_name"] for row in dictionary_rows}
    assert column_names == {"customer_id", "status", "age"}

    # ---- Before / after comparison ----
    before_after_response = client.get(f"/api/before-after/{run_id}")
    assert before_after_response.status_code == 200
    before_after_body = before_after_response.json()
    assert "missing_values" in before_after_body["files"][DATASET_FILENAME]
    assert (settings.runs_dir / run_id / "before_after_summary.json").exists()

    # ---- Quality score ----
    quality_response = client.get(f"/api/quality/{run_id}")
    assert quality_response.status_code == 200
    quality_body = quality_response.json()
    after_score = quality_body["files"][DATASET_FILENAME]["after"]["overall_score"]
    assert 0 <= after_score <= 100
    assert (settings.runs_dir / run_id / "quality_report.json").exists()

    # ---- PDF report ----
    report_response = client.get(f"/api/report/{run_id}")
    assert report_response.status_code == 200
    assert report_response.content[:4] == b"%PDF"
    report_path = settings.runs_dir / run_id / "DataQX_Report.pdf"
    assert report_path.exists()
    reader = PdfReader(io.BytesIO(report_response.content))
    report_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert DATASET_FILENAME in report_text
    assert run_id in report_text

    # ---- Downloads: cleaned dataset + a reports-dir artifact ----
    download_cleaned_response = client.get(f"/api/download/{run_id}/{stem}_cleaned.csv")
    assert download_cleaned_response.status_code == 200
    assert download_cleaned_response.content == cleaned_csv_path.read_bytes()

    download_lineage_response = client.get(f"/api/download/{run_id}/data_lineage.csv")
    assert download_lineage_response.status_code == 200
    assert len(download_lineage_response.content) > 0

    # ---- Performance ----
    performance_response = client.get(f"/api/performance/{run_id}")
    assert performance_response.status_code == 200
    processing_times = performance_response.json()["processing_time_seconds"]
    for stage in ("upload", "analyze", "clean", "validate", "pdf_generation"):
        assert stage in processing_times
        assert processing_times[stage] >= 0

    # ---- Final run metadata reflects the completed chain ----
    metadata = json.loads((settings.runs_dir / run_id / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["run_id"] == run_id
    assert metadata["quality_score"] is not None
    assert metadata["powerbi_readiness"] is not None
