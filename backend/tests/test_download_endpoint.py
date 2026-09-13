from fastapi.testclient import TestClient

from app.core.config import get_settings
from main import app

client = TestClient(app)


def _upload(content: bytes, filename: str = "data.csv") -> str:
    response = client.post("/api/upload", files={"files": (filename, content, "text/csv")})
    assert response.status_code == 200
    return response.json()["run_id"]


def test_download_endpoint_serves_real_cleaned_csv():
    content = b"id,status\n1,active\n2,active\n3,N/A\n4,inactive\n"
    run_id = _upload(content)
    client.post("/api/analyze", json={"run_id": run_id})
    client.post("/api/clean", json={"run_id": run_id})

    response = client.get(f"/api/download/{run_id}/data_cleaned.csv")
    assert response.status_code == 200

    settings = get_settings()
    on_disk = (settings.output_dir / run_id / "data_cleaned.csv").read_bytes()
    assert response.content == on_disk


def test_download_endpoint_serves_run_artifact_from_reports_dir():
    content = b"id,status\n1,active\n2,active\n3,N/A\n4,inactive\n"
    run_id = _upload(content)
    client.post("/api/analyze", json={"run_id": run_id})
    client.post("/api/clean", json={"run_id": run_id})

    response = client.get(f"/api/download/{run_id}/cleaning_log.csv")
    assert response.status_code == 200
    assert len(response.content) > 0


def test_download_endpoint_rejects_path_traversal():
    content = b"a,b\n1,2\n"
    run_id = _upload(content)

    response = client.get(f"/api/download/{run_id}/..%2F..%2F..%2Fetc%2Fpasswd")
    assert response.status_code in (400, 404)  # never 200, never leaks a file outside the run


def test_download_endpoint_404_for_nonexistent_file():
    run_id = _upload(b"a,b\n1,2\n")
    response = client.get(f"/api/download/{run_id}/does_not_exist.csv")
    assert response.status_code == 404


def test_download_endpoint_404_for_nonexistent_run():
    response = client.get("/api/download/run_does_not_exist/anything.csv")
    assert response.status_code == 404
