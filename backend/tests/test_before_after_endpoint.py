import json

from fastapi.testclient import TestClient

from app.core.config import get_settings
from main import app

client = TestClient(app)


def _upload(content: bytes, filename: str = "data.csv") -> str:
    response = client.post("/api/upload", files={"files": (filename, content, "text/csv")})
    assert response.status_code == 200
    return response.json()["run_id"]


def test_before_after_endpoint_matches_disk():
    content = b"id,status\n1,active\n2,active\n3,N/A\n4,inactive\n"
    run_id = _upload(content)
    client.post("/api/analyze", json={"run_id": run_id})
    client.post("/api/clean", json={"run_id": run_id})

    response = client.get(f"/api/before-after/{run_id}")
    assert response.status_code == 200
    body = response.json()

    settings = get_settings()
    disk = json.loads((settings.runs_dir / run_id / "before_after_summary.json").read_text(encoding="utf-8"))
    assert body == disk
    assert "missing_values" in body["files"]["data.csv"]


def test_before_after_endpoint_404_before_clean():
    run_id = _upload(b"a,b\n1,2\n")
    client.post("/api/analyze", json={"run_id": run_id})
    response = client.get(f"/api/before-after/{run_id}")
    assert response.status_code == 404


def test_before_after_endpoint_404_for_nonexistent_run():
    response = client.get("/api/before-after/run_does_not_exist")
    assert response.status_code == 404
