from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _upload(content: bytes, filename: str = "data.csv") -> str:
    response = client.post("/api/upload", files={"files": (filename, content, "text/csv")})
    assert response.status_code == 200
    return response.json()["run_id"]


def test_quality_endpoint_returns_real_report_matching_disk():
    import json

    from app.core.config import get_settings

    content = b"id,status\n1,active\n2,active\n3,N/A\n4,inactive\n"
    run_id = _upload(content)
    client.post("/api/analyze", json={"run_id": run_id})
    client.post("/api/clean", json={"run_id": run_id})

    response = client.get(f"/api/quality/{run_id}")
    assert response.status_code == 200
    body = response.json()

    settings = get_settings()
    disk = json.loads((settings.runs_dir / run_id / "quality_report.json").read_text(encoding="utf-8"))
    assert body == disk
    assert "overall_score" in body["files"]["data.csv"]["after"]


def test_quality_endpoint_404_before_clean():
    run_id = _upload(b"a,b\n1,2\n")
    client.post("/api/analyze", json={"run_id": run_id})
    response = client.get(f"/api/quality/{run_id}")
    assert response.status_code == 404


def test_quality_endpoint_404_for_nonexistent_run():
    response = client.get("/api/quality/run_does_not_exist")
    assert response.status_code == 404
