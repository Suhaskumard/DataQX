from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _upload(content: bytes, filename: str = "data.csv") -> str:
    response = client.post("/api/upload", files={"files": (filename, content, "text/csv")})
    assert response.status_code == 200
    return response.json()["run_id"]


def test_issues_endpoint_returns_detected_issues():
    content = b"customer_id,status\n1,active\n2,active\n3,N/A\n4,active\n5,inactive\n"
    run_id = _upload(content)

    analyze_response = client.post("/api/analyze", json={"run_id": run_id})
    assert analyze_response.status_code == 200

    issues_response = client.get(f"/api/issues/{run_id}")
    assert issues_response.status_code == 200
    body = issues_response.json()
    assert body["run_id"] == run_id

    issue_types = {issue["issue_type"] for issue in body["files"]["data.csv"]}
    assert "missing_value_placeholder" in issue_types


def test_issues_endpoint_404_before_analyze():
    content = b"a,b\n1,2\n"
    run_id = _upload(content)

    response = client.get(f"/api/issues/{run_id}")
    assert response.status_code == 404


def test_issues_endpoint_404_for_nonexistent_run():
    response = client.get("/api/issues/run_does_not_exist")
    assert response.status_code == 404
