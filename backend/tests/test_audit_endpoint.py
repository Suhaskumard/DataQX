import pandas as pd
from fastapi.testclient import TestClient

from app.core.config import get_settings
from main import app

client = TestClient(app)


def _upload(content: bytes, filename: str = "data.csv") -> str:
    response = client.post("/api/upload", files={"files": (filename, content, "text/csv")})
    assert response.status_code == 200
    return response.json()["run_id"]


def test_audit_endpoint_matches_disk_csv():
    content = b"id,status,notes\n1,active,normal\n2,active,normal\n3,N/A,normal\n4,inactive,normal\n"
    run_id = _upload(content)

    client.post("/api/analyze", json={"run_id": run_id})
    client.post("/api/clean", json={"run_id": run_id})

    response = client.get(f"/api/audit/{run_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == run_id
    assert len(body["rows"]) > 0

    row = body["rows"][0]
    for column in ("timestamp", "run_id", "dataset", "column", "issue_type", "action", "confidence", "severity", "status"):
        assert column in row

    status_row = next(r for r in body["rows"] if r["column"] == "status")
    assert status_row["issue_type"] == "missing_value_placeholder"

    settings = get_settings()
    disk_csv = pd.read_csv(settings.runs_dir / run_id / "audit_log.csv")
    assert len(disk_csv) == len(body["rows"])


def test_audit_endpoint_404_before_clean():
    content = b"a,b\n1,2\n"
    run_id = _upload(content)
    client.post("/api/analyze", json={"run_id": run_id})

    response = client.get(f"/api/audit/{run_id}")
    assert response.status_code == 404


def test_audit_endpoint_404_for_nonexistent_run():
    response = client.get("/api/audit/run_does_not_exist")
    assert response.status_code == 404
