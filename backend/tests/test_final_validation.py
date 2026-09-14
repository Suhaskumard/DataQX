"""Phase 24 -- Final End-to-End Validation.

Drives the real data/samples/ fixtures (customers.csv + orders.csv, satisfying
DATAQX.pdf S61's required issue-type coverage) through the complete real workflow
S71 describes -- Upload -> Project Plan -> Analyze -> Clean -> Validate -> Lineage ->
Drift -> Power BI -> Reports -> Download -- and verifies every S67 per-run artifact
actually exists on disk and is downloadable, that the multi-file referential-
integrity check catches the real orphan foreign key, and that the issues the fixture
was built to contain are the issues actually detected. Every assertion here is
against real, previously-executed output (see the exploratory run used to build this
fixture) -- nothing is asserted based on assumption (S63).
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings
from main import app

client = TestClient(app)

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "data" / "samples"
CUSTOMERS_CSV = SAMPLES_DIR / "customers.csv"
ORDERS_CSV = SAMPLES_DIR / "orders.csv"

PROJECT_PLAN_TEXT = "# Final Validation\nObjective: verify the complete real pipeline against realistic messy data."


def test_final_validation_full_workflow_every_artifact_and_real_issues():
    settings = get_settings()
    assert CUSTOMERS_CSV.exists() and ORDERS_CSV.exists()

    # ---- Upload (multi-file, with a project plan) ----
    with open(CUSTOMERS_CSV, "rb") as f1, open(ORDERS_CSV, "rb") as f2:
        upload_response = client.post(
            "/api/upload",
            files=[
                ("files", ("customers.csv", f1, "text/csv")),
                ("files", ("orders.csv", f2, "text/csv")),
            ],
            data={"project_plan_text": PROJECT_PLAN_TEXT},
        )
    assert upload_response.status_code == 200
    upload_body = upload_response.json()
    run_id = upload_body["run_id"]
    statuses = {f["original_name"]: f["status"] for f in upload_body["files"]}
    assert statuses == {"customers.csv": "saved", "orders.csv": "saved"}
    assert upload_body["project_plan"]["status"] == "saved"

    # ---- Analyze: confirm the real S61 issue types this fixture was built for ----
    analyze_response = client.post("/api/analyze", json={"run_id": run_id})
    assert analyze_response.status_code == 200
    customers_issues = {i["issue_type"] for i in analyze_response.json()["files"]["customers.csv"]["issues"]}
    expected_issue_types = {
        "missing_value_placeholder",  # "N/A" name placeholder
        "duplicate_rows",             # fully duplicated row (customer_id 9)
        "duplicate_id",               # same duplicate, seen from the ID-uniqueness angle
        "mixed_data_types",           # "abc" in age, "1,500" in revenue
        "category_inconsistency",     # "Gold" vs "gold" casing variants
        "whitespace_formatting",      # padded name
        "invalid_date",               # mixed date formats in signup_date
        "negative_value",             # negative quantity
    }
    assert expected_issue_types.issubset(customers_issues)

    # ---- Clean ----
    clean_response = client.post("/api/clean", json={"run_id": run_id})
    assert clean_response.status_code == 200
    clean_body = clean_response.json()
    assert clean_body["files"]["customers.csv"]["status"] == "cleaned"
    assert clean_body["files"]["orders.csv"]["status"] == "cleaned"

    # ---- Validate ----
    validate_response = client.post("/api/validate", json={"run_id": run_id})
    assert validate_response.status_code == 200
    assert validate_response.json()["files"]["customers.csv"]["overall_status"] == "pass"

    # ---- Power BI / referential integrity: the real orphan (customer_id 999) ----
    readiness_response = client.get(f"/api/analytics-readiness/{run_id}")
    assert readiness_response.status_code == 200
    orders_powerbi = readiness_response.json()["files"]["orders.csv"]["platforms"]["power_bi"]
    orders_checks = {c["check_name"]: c for c in orders_powerbi["checks"]}
    fk_check = orders_checks["foreign_key_relationships"]
    assert fk_check["status"] == "warning"
    assert fk_check["details"]["findings"]["customer_id"]["orphan_examples"] == ["999"]

    # ---- Lineage / Drift ----
    assert client.get(f"/api/lineage/{run_id}").status_code == 200
    assert client.get(f"/api/drift/{run_id}").status_code == 200

    # ---- Dictionary / Before-After / Quality / Report ----
    assert client.get(f"/api/dictionary/{run_id}").status_code == 200
    assert client.get(f"/api/before-after/{run_id}").status_code == 200
    assert client.get(f"/api/quality/{run_id}").status_code == 200
    report_response = client.get(f"/api/report/{run_id}")
    assert report_response.status_code == 200
    assert report_response.content[:4] == b"%PDF"

    run_dir = settings.runs_dir / run_id
    output_dir_customers = settings.output_dir / run_id

    # ---- Every S67 per-run artifact exists on disk, real and non-empty ----
    per_run_artifacts = [
        run_dir / "profile.json",
        run_dir / "cleaning_log.json",
        run_dir / "cleaning_log.csv",
        run_dir / "audit_log.csv",  # the Phase 24 fix: now written per-run
        run_dir / "data_lineage.json",
        run_dir / "data_lineage.csv",
        run_dir / "drift_report.json",
        run_dir / "validation_report.json",
        run_dir / "before_after_summary.json",
        run_dir / "before_after_summary.csv",
        run_dir / "quality_report.json",
        run_dir / "data_dictionary.csv",
        run_dir / "DataQX_Report.pdf",
        output_dir_customers / "customers_cleaned.csv",
        output_dir_customers / "customers_cleaned.xlsx",
        output_dir_customers / "orders_cleaned.csv",
    ]
    for artifact in per_run_artifacts:
        assert artifact.exists(), f"missing artifact: {artifact}"
        assert artifact.stat().st_size > 0, f"empty artifact: {artifact}"

    # ---- Every artifact is downloadable through the real API, not just present on disk ----
    downloadable_filenames = [
        "customers_cleaned.csv",
        "customers_cleaned.xlsx",
        "orders_cleaned.csv",
        "cleaning_log.csv",
        "audit_log.csv",
        "data_lineage.csv",
        "data_dictionary.csv",
        "before_after_summary.csv",
        "drift_report.json",
        "validation_report.json",
    ]
    for filename in downloadable_filenames:
        download_response = client.get(f"/api/download/{run_id}/{filename}")
        assert download_response.status_code == 200, f"download failed for {filename}"
        assert len(download_response.content) > 0

    # ---- Run metadata reflects the completed chain ----
    metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["run_id"] == run_id
    assert metadata["quality_score"] is not None
    assert metadata["analytics_readiness"] is not None
