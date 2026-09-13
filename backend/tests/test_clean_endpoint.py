import hashlib
import json

from fastapi.testclient import TestClient

from app.core.config import get_settings
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


def test_clean_endpoint_404_for_nonexistent_run():
    response = client.post("/api/clean", json={"run_id": "run_does_not_exist"})
    assert response.status_code == 404
