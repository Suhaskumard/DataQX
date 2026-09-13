from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _upload(content: bytes, filename: str = "data.csv") -> str:
    response = client.post("/api/upload", files={"files": (filename, content, "text/csv")})
    assert response.status_code == 200
    return response.json()["run_id"]


def test_performance_endpoint_404_for_nonexistent_run():
    response = client.get("/api/performance/run_does_not_exist")
    assert response.status_code == 404


def test_performance_endpoint_reflects_real_recorded_stages():
    run_id = _upload(b"id,name\n1,Alice \n2,Bob\n3, Carol\n")
    client.post("/api/analyze", json={"run_id": run_id})
    client.post("/api/clean", json={"run_id": run_id})
    client.post("/api/validate", json={"run_id": run_id})

    response = client.get(f"/api/performance/{run_id}")
    assert response.status_code == 200
    body = response.json()

    assert body["run_id"] == run_id
    times = body["processing_time_seconds"]
    for stage in ["upload", "analyze", "clean", "validate", "file_loading", "profiling", "issue_detection"]:
        assert stage in times
        assert times[stage] >= 0

    assert body["bottleneck_stage"] in times
    assert body["bottleneck_seconds"] == times[body["bottleneck_stage"]]


def test_performance_endpoint_available_right_after_upload():
    run_id = _upload(b"a,b\n1,2\n")
    response = client.get(f"/api/performance/{run_id}")
    assert response.status_code == 200
    body = response.json()
    assert "upload" in body["processing_time_seconds"]
    assert body["bottleneck_stage"] is None  # no bottleneck computed until /api/validate runs
