from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_at_api_prefix():
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "DataQX"
    assert "version" in body
    assert "timestamp" in body


def test_health_at_root():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "DataQX"
