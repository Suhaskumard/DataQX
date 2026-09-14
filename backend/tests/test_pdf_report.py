from fastapi.testclient import TestClient
from pypdf import PdfReader
import io

from app.core.config import get_settings
from app.services.pdf_report import generate_pdf_report
from main import app

client = TestClient(app)


def _upload(content: bytes, filename: str) -> str:
    response = client.post("/api/upload", files={"files": (filename, content, "text/csv")})
    assert response.status_code == 200
    return response.json()["run_id"]


def _extract_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def test_report_without_validation_shows_honest_not_run_note():
    content = b"id,status\n1,active\n2,active\n3,N/A\n4,inactive\n"
    run_id = _upload(content, "data.csv")
    client.post("/api/analyze", json={"run_id": run_id})
    client.post("/api/clean", json={"run_id": run_id})
    # Deliberately do NOT call /api/validate.

    settings = get_settings()
    run_dir = settings.runs_dir / run_id
    pdf_bytes = generate_pdf_report(run_dir, run_id)
    text = _extract_text(pdf_bytes)

    assert "data.csv" in text
    assert run_id in text
    assert "Validation was not run for this report" in text
    # The Validation Gates section specifically must never show a fabricated
    # "Overall: PASS/WARNING/FAIL" line when /api/validate was never called --
    # other sections (e.g. Analytics Readiness) legitimately contain "PASS" for
    # their own, unrelated checks, so this must be scoped to that one section.
    validation_section = text.split("Validation Gates", 1)[1].split("Analytics Readiness", 1)[0]
    assert "Overall:" not in validation_section


def test_report_with_validation_shows_real_status():
    content = b"id,status\n1,active\n2,active\n3,N/A\n4,inactive\n"
    run_id = _upload(content, "data.csv")
    client.post("/api/analyze", json={"run_id": run_id})
    client.post("/api/clean", json={"run_id": run_id})
    validate_response = client.post("/api/validate", json={"run_id": run_id})
    overall_status = validate_response.json()["files"]["data.csv"]["overall_status"]

    settings = get_settings()
    run_dir = settings.runs_dir / run_id
    pdf_bytes = generate_pdf_report(run_dir, run_id)
    text = _extract_text(pdf_bytes)

    assert f"Overall: {overall_status.upper()}" in text


def test_report_contains_real_quality_score():
    content = b"id,status\n1,active\n2,active\n3,N/A\n4,inactive\n"
    run_id = _upload(content, "data.csv")
    client.post("/api/analyze", json={"run_id": run_id})
    clean_response = client.post("/api/clean", json={"run_id": run_id})

    settings = get_settings()
    run_dir = settings.runs_dir / run_id
    pdf_bytes = generate_pdf_report(run_dir, run_id)
    text = _extract_text(pdf_bytes)

    import json

    quality = json.loads((run_dir / "quality_report.json").read_text(encoding="utf-8"))
    after_score = quality["files"]["data.csv"]["after"]["overall_score"]
    assert f"{after_score}/100" in text


def test_report_survives_ampersand_and_angle_brackets_in_column_name():
    """ReportLab Paragraph() parses text as XML-like markup -- an unescaped '&'/'<'/
    '>' in a real column name must not raise, and must still render as literal text
    (not be silently dropped or misinterpreted as markup)."""
    content = b"id,Rating & Review <5>,status\n1,5,active\n2,3,N/A\n"
    run_id = _upload(content, "data.csv")
    client.post("/api/analyze", json={"run_id": run_id})
    client.post("/api/clean", json={"run_id": run_id})

    settings = get_settings()
    run_dir = settings.runs_dir / run_id
    pdf_bytes = generate_pdf_report(run_dir, run_id)  # must not raise

    text = _extract_text(pdf_bytes)
    assert "Rating & Review" in text


def test_report_renders_nan_as_na_not_literal_nan_string():
    import math

    from app.services.pdf_report import _esc

    assert _esc(float("nan")) == "N/A"
    assert _esc(float("inf")) == "N/A"
    assert _esc(None) == "N/A"
    assert _esc("Sales & Marketing") == "Sales &amp; Marketing"
