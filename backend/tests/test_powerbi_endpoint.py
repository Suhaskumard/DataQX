import json

from fastapi.testclient import TestClient

from app.core.config import get_settings
from main import app

client = TestClient(app)


def _upload(content: bytes, filename: str) -> str:
    response = client.post("/api/upload", files={"files": (filename, content, "text/csv")})
    assert response.status_code == 200
    return response.json()["run_id"]


def test_powerbi_endpoint_matches_disk_and_updates_run_metadata():
    content = b"id,amount\n1,10\n2,20\n3,30\n4,40\n"
    run_id = _upload(content, "data.csv")

    analyze_response = client.post("/api/analyze", json={"run_id": run_id})
    assert analyze_response.status_code == 200

    response = client.get(f"/api/powerbi/{run_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == run_id

    file_report = body["files"]["data.csv"]
    assert isinstance(file_report["score"], int)
    assert 0 <= file_report["score"] <= 100
    assert file_report["table_role"] in ("fact", "dimension", "unclassified")

    check_names = {c["check_name"] for c in file_report["checks"]}
    assert "duplicate_keys" in check_names
    assert "foreign_key_relationships" in check_names  # single-file run -> not_applicable

    fk_check = next(c for c in file_report["checks"] if c["check_name"] == "foreign_key_relationships")
    assert fk_check["status"] == "not_applicable"

    settings = get_settings()
    disk_report = json.loads(
        (settings.runs_dir / run_id / "powerbi_readiness.json").read_text(encoding="utf-8")
    )
    assert disk_report == body

    metadata = json.loads((settings.runs_dir / run_id / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["powerbi_readiness"] is not None
    assert metadata["powerbi_readiness"] == file_report["score"]


def test_powerbi_endpoint_404_before_analyze():
    run_id = _upload(b"a,b\n1,2\n", "data.csv")
    response = client.get(f"/api/powerbi/{run_id}")
    assert response.status_code == 404


def test_powerbi_endpoint_404_for_nonexistent_run():
    response = client.get("/api/powerbi/run_does_not_exist")
    assert response.status_code == 404
