"""Phase 25 -- Error recovery / fault injection.

Forces a failure at each pipeline stage via monkeypatching and verifies: a friendly
response (never a raw traceback leaking to the client), the raw input file is
provably untouched (hash comparison, DATAQX.pdf Rule 4), no orphaned/partial output
artifact is left on disk from the failed attempt, and a subsequent normal run for a
fresh upload still succeeds (the failure doesn't poison global state).
"""

from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient

from app.core.config import get_settings
from main import app

client = TestClient(app)

CONTENT = b"id,status\n1,active\n2,active\n3,N/A\n4,inactive\n"


def _upload() -> tuple[str, str]:
    response = client.post("/api/upload", files={"files": ("data.csv", CONTENT, "text/csv")})
    assert response.status_code == 200
    return response.json()["run_id"], hashlib.sha256(CONTENT).hexdigest()


def _assert_raw_file_untouched(run_id: str, expected_hash: str):
    settings = get_settings()
    raw_path = settings.input_dir / run_id / "data.csv"
    assert raw_path.exists()
    assert hashlib.sha256(raw_path.read_bytes()).hexdigest() == expected_hash


def _assert_subsequent_normal_run_still_works():
    """The failure injected in one run must not poison any global/shared state that
    would break a completely independent, later run."""
    response = client.post("/api/upload", files={"files": ("data.csv", CONTENT, "text/csv")})
    assert response.status_code == 200
    run_id = response.json()["run_id"]
    assert client.post("/api/analyze", json={"run_id": run_id}).status_code == 200
    assert client.post("/api/clean", json={"run_id": run_id}).status_code == 200
    assert client.post("/api/validate", json={"run_id": run_id}).status_code == 200


def test_ingestion_failure_during_analyze_is_reported_per_file_not_a_crash(monkeypatch):
    run_id, expected_hash = _upload()

    def _raise(*args, **kwargs):
        raise RuntimeError("simulated ingestion failure")

    monkeypatch.setattr("app.api.analyze.load_dataset", _raise)

    response = client.post("/api/analyze", json={"run_id": run_id})
    assert response.status_code == 200
    assert response.json()["files"]["data.csv"]["status"] == "failed"

    _assert_raw_file_untouched(run_id, expected_hash)
    monkeypatch.undo()
    _assert_subsequent_normal_run_still_works()


def test_profiling_failure_during_analyze_is_reported_per_file_not_a_crash(monkeypatch):
    run_id, expected_hash = _upload()

    def _raise(*args, **kwargs):
        raise RuntimeError("simulated profiling failure")

    monkeypatch.setattr("app.api.analyze.profile_dataset", _raise)

    response = client.post("/api/analyze", json={"run_id": run_id})
    assert response.status_code == 200
    assert response.json()["files"]["data.csv"]["status"] == "failed"

    _assert_raw_file_untouched(run_id, expected_hash)
    monkeypatch.undo()
    _assert_subsequent_normal_run_still_works()


def test_issue_detection_failure_during_analyze_is_reported_per_file_not_a_crash(monkeypatch):
    run_id, expected_hash = _upload()

    def _raise(*args, **kwargs):
        raise RuntimeError("simulated issue-detection failure")

    monkeypatch.setattr("app.api.analyze.detect_issues", _raise)

    response = client.post("/api/analyze", json={"run_id": run_id})
    assert response.status_code == 200
    assert response.json()["files"]["data.csv"]["status"] == "failed"

    _assert_raw_file_untouched(run_id, expected_hash)
    monkeypatch.undo()
    _assert_subsequent_normal_run_still_works()


def test_cleaning_failure_during_clean_is_reported_per_file_not_a_crash(monkeypatch):
    run_id, expected_hash = _upload()
    assert client.post("/api/analyze", json={"run_id": run_id}).status_code == 200

    def _raise(*args, **kwargs):
        raise RuntimeError("simulated cleaning failure")

    monkeypatch.setattr("app.api.clean.apply_cleaning", _raise)

    response = client.post("/api/clean", json={"run_id": run_id})
    assert response.status_code == 200
    assert response.json()["files"]["data.csv"]["status"] == "failed"

    settings = get_settings()
    output_dir = settings.output_dir / run_id
    # No partial cleaned CSV/XLSX left behind from the failed attempt.
    assert not output_dir.exists() or list(output_dir.iterdir()) == []

    _assert_raw_file_untouched(run_id, expected_hash)
    monkeypatch.undo()
    _assert_subsequent_normal_run_still_works()


def test_validation_failure_during_validate_is_reported_per_file_not_a_crash(monkeypatch):
    run_id, expected_hash = _upload()
    assert client.post("/api/analyze", json={"run_id": run_id}).status_code == 200
    assert client.post("/api/clean", json={"run_id": run_id}).status_code == 200

    def _raise(*args, **kwargs):
        raise RuntimeError("simulated validation failure")

    monkeypatch.setattr("app.api.validate.validate_dataset", _raise)

    response = client.post("/api/validate", json={"run_id": run_id})
    assert response.status_code == 200
    assert response.json()["files"]["data.csv"]["status"] == "failed"

    _assert_raw_file_untouched(run_id, expected_hash)
    monkeypatch.undo()
    _assert_subsequent_normal_run_still_works()


def test_pdf_generation_failure_returns_friendly_500_not_raw_traceback(monkeypatch):
    run_id, expected_hash = _upload()
    assert client.post("/api/analyze", json={"run_id": run_id}).status_code == 200

    def _raise(*args, **kwargs):
        raise RuntimeError("simulated PDF generation failure")

    monkeypatch.setattr("app.api.report.generate_pdf_report", _raise)

    no_raise_client = TestClient(app, raise_server_exceptions=False)
    response = no_raise_client.post("/api/upload", files={"files": ("data.csv", CONTENT, "text/csv")})
    same_run_id = run_id  # reuse the original run's analyzed data

    response = no_raise_client.get(f"/api/report/{same_run_id}")
    assert response.status_code == 500
    assert "RuntimeError" not in response.text
    assert "Traceback" not in response.text

    settings = get_settings()
    report_path = settings.runs_dir / run_id / "DataQX_Report.pdf"
    assert not report_path.exists()  # no partial/corrupt PDF left behind

    _assert_raw_file_untouched(run_id, expected_hash)
    monkeypatch.undo()
    _assert_subsequent_normal_run_still_works()
