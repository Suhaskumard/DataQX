import json

from fastapi.testclient import TestClient

from app.core.config import get_settings
from main import app

client = TestClient(app)


def _upload(content: bytes, filename: str) -> str:
    response = client.post("/api/upload", files={"files": (filename, content, "text/csv")})
    assert response.status_code == 200
    return response.json()["run_id"]


def test_analytics_readiness_endpoint_matches_disk_and_updates_run_metadata():
    content = b"id,amount\n1,10\n2,20\n3,30\n4,40\n"
    run_id = _upload(content, "data.csv")

    analyze_response = client.post("/api/analyze", json={"run_id": run_id})
    assert analyze_response.status_code == 200

    response = client.get(f"/api/analytics-readiness/{run_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == run_id

    file_report = body["files"]["data.csv"]
    assert isinstance(file_report["overall_score"], int)
    assert 0 <= file_report["overall_score"] <= 100

    # Every one of the ten platforms was actually evaluated (default: all platforms).
    assert set(file_report["platforms"].keys()) == {
        "power_bi", "tableau", "alteryx", "excel", "looker",
        "looker_studio", "qlik", "sql", "python", "r",
    }

    powerbi_report = file_report["platforms"]["power_bi"]
    assert powerbi_report["platform"] == "Power BI"
    check_names = {c["check_name"] for c in powerbi_report["checks"]}
    assert "duplicate_keys" in check_names
    assert "table_role" in check_names
    assert "foreign_key_relationships" in check_names  # single-file run -> not_applicable

    fk_check = next(c for c in powerbi_report["checks"] if c["check_name"] == "foreign_key_relationships")
    assert fk_check["status"] == "not_applicable"

    settings = get_settings()
    disk_report = json.loads(
        (settings.runs_dir / run_id / "analytics_readiness.json").read_text(encoding="utf-8")
    )
    assert disk_report == body

    metadata = json.loads((settings.runs_dir / run_id / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["analytics_readiness"] is not None
    assert metadata["analytics_readiness"] == file_report["overall_score"]


def test_analytics_readiness_endpoint_404_before_analyze():
    run_id = _upload(b"a,b\n1,2\n", "data.csv")
    response = client.get(f"/api/analytics-readiness/{run_id}")
    assert response.status_code == 404


def test_analytics_readiness_endpoint_404_for_nonexistent_run():
    response = client.get("/api/analytics-readiness/run_does_not_exist")
    assert response.status_code == 404
