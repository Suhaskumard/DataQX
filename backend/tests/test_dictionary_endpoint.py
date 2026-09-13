from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _upload(content: bytes, filename: str = "data.csv") -> str:
    response = client.post("/api/upload", files={"files": (filename, content, "text/csv")})
    assert response.status_code == 200
    return response.json()["run_id"]


def test_dictionary_endpoint_returns_real_rows_matching_columns():
    content = b"id,status\n1,active\n2,active\n3,N/A\n4,inactive\n"
    run_id = _upload(content)
    client.post("/api/analyze", json={"run_id": run_id})
    client.post("/api/clean", json={"run_id": run_id})

    response = client.get(f"/api/dictionary/{run_id}")
    assert response.status_code == 200
    body = response.json()

    rows = body["files"]["data.csv"]
    column_names = {row["original_name"] for row in rows}
    assert column_names == {"id", "status"}

    status_row = next(r for r in rows if r["original_name"] == "status")
    assert status_row["cleaning_actions"] is not None
    id_row = next(r for r in rows if r["original_name"] == "id")
    assert id_row["cleaning_actions"] is None  # NaN correctly converted to null, not "nan" string


def test_dictionary_endpoint_404_before_clean():
    run_id = _upload(b"a,b\n1,2\n")
    client.post("/api/analyze", json={"run_id": run_id})
    response = client.get(f"/api/dictionary/{run_id}")
    assert response.status_code == 404


def test_dictionary_endpoint_404_for_nonexistent_run():
    response = client.get("/api/dictionary/run_does_not_exist")
    assert response.status_code == 404
