import json

import pandas as pd
from fastapi.testclient import TestClient

from app.core.config import get_settings
from main import app

client = TestClient(app)


def _upload(content: bytes, filename: str = "data.csv") -> str:
    response = client.post("/api/upload", files={"files": (filename, content, "text/csv")})
    assert response.status_code == 200
    return response.json()["run_id"]


def test_lineage_endpoint_matches_disk_artifacts():
    content = b"id,status,notes\n1,active,normal\n2,active,normal\n3,N/A,normal\n4,inactive,normal\n"
    run_id = _upload(content)

    client.post("/api/analyze", json={"run_id": run_id})
    client.post("/api/clean", json={"run_id": run_id})

    response = client.get(f"/api/lineage/{run_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == run_id

    file_lineage = body["files"]["data.csv"]
    status_entries = [e for e in file_lineage if e["source_column"] == "status"]
    assert len(status_entries) == 1
    assert status_entries[0]["rule"] == "missing_value_placeholder"
    assert status_entries[0]["confidence"] == "MEDIUM"

    notes_entries = [e for e in file_lineage if e["source_column"] == "notes"]
    assert len(notes_entries) == 1
    assert notes_entries[0]["transformation"] == "unchanged"

    settings = get_settings()
    disk_json = json.loads((settings.runs_dir / run_id / "data_lineage.json").read_text(encoding="utf-8"))
    assert disk_json == body

    disk_csv = pd.read_csv(settings.runs_dir / run_id / "data_lineage.csv")
    assert "lineage_id" in disk_csv.columns
    assert len(disk_csv) == len(file_lineage)


def test_lineage_endpoint_404_before_clean():
    content = b"a,b\n1,2\n"
    run_id = _upload(content)
    client.post("/api/analyze", json={"run_id": run_id})

    response = client.get(f"/api/lineage/{run_id}")
    assert response.status_code == 404


def test_lineage_endpoint_404_for_nonexistent_run():
    response = client.get("/api/lineage/run_does_not_exist")
    assert response.status_code == 404
