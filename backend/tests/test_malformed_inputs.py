"""Phase 22 -- Malformed/corrupt input handling tests.

Every case here must produce a friendly failure (a per-file "failed" status with a
specific reason, or a 4xx/JSON error) -- never an unhandled exception or a raw
traceback surfaced to the client.
"""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _upload(filename: str, content: bytes) -> str:
    response = client.post("/api/upload", files={"files": (filename, content, "application/octet-stream")})
    assert response.status_code == 200
    return response.json()["run_id"]


def test_corrupt_xlsx_fails_gracefully():
    run_id = _upload("broken.xlsx", b"this is not a real zip/xlsx file" * 10)

    response = client.post("/api/analyze", json={"run_id": run_id})
    assert response.status_code == 200
    result = response.json()["files"]["broken.xlsx"]
    assert result["status"] == "failed"
    assert "reason" in result


def test_corrupt_parquet_fails_gracefully():
    run_id = _upload("broken.parquet", b"not a real parquet footer" * 10)

    response = client.post("/api/analyze", json={"run_id": run_id})
    assert response.status_code == 200
    result = response.json()["files"]["broken.parquet"]
    assert result["status"] == "failed"
    assert "reason" in result


def test_malformed_json_fails_gracefully():
    run_id = _upload("broken.json", b'{"a": [1, 2, "unterminated string')

    response = client.post("/api/analyze", json={"run_id": run_id})
    assert response.status_code == 200
    result = response.json()["files"]["broken.json"]
    assert result["status"] == "failed"
    assert "reason" in result


def test_whitespace_only_csv_fails_gracefully():
    run_id = _upload("blank.csv", b"\n\n\n   \n\n")

    response = client.post("/api/analyze", json={"run_id": run_id})
    assert response.status_code == 200
    result = response.json()["files"]["blank.csv"]
    assert result["status"] == "failed"


def test_inconsistent_row_lengths_still_parses_with_warning():
    content = b"a,b,c\n1,2,3\n4,5\n6,7,8,9\n"
    run_id = _upload("ragged.csv", content)

    response = client.post("/api/analyze", json={"run_id": run_id})
    assert response.status_code == 200
    result = response.json()["files"]["ragged.csv"]
    assert result["status"] == "profiled"


def test_latin1_encoded_csv_does_not_crash():
    content = "name,city\nJosé,São Paulo\n".encode("latin-1")
    run_id = _upload("accented.csv", content)

    response = client.post("/api/analyze", json={"run_id": run_id})
    assert response.status_code == 200
    result = response.json()["files"]["accented.csv"]
    assert result["status"] in ("profiled", "failed")


def test_corrupt_file_analyze_reason_not_a_raw_traceback():
    run_id = _upload("broken.xlsx", b"garbage-not-xlsx" * 20)

    response = client.post("/api/analyze", json={"run_id": run_id})
    result = response.json()["files"]["broken.xlsx"]
    assert "Traceback" not in result["reason"]
    assert "File \"" not in result["reason"]


def test_analyze_nonexistent_run_id_returns_404_not_500():
    response = client.post("/api/analyze", json={"run_id": "run_totally_made_up"})
    assert response.status_code == 404


def test_clean_and_validate_survive_corrupt_parquet(monkeypatch):
    run_id = _upload("broken.parquet", b"not parquet at all" * 10)
    client.post("/api/analyze", json={"run_id": run_id})

    clean_response = client.post("/api/clean", json={"run_id": run_id})
    assert clean_response.status_code == 200

    validate_response = client.post("/api/validate", json={"run_id": run_id})
    assert validate_response.status_code == 200


