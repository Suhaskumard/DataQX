import json

from fastapi.testclient import TestClient

from app.core.config import get_settings
from main import app

client = TestClient(app)


def _upload(content: bytes, filename: str = "data.csv") -> str:
    response = client.post("/api/upload", files={"files": (filename, content, "text/csv")})
    assert response.status_code == 200
    return response.json()["run_id"]


def test_analyze_then_get_profile_roundtrip():
    content = b"id,amount\n1,100\n2,200\n3,300\n"
    run_id = _upload(content)

    analyze_response = client.post("/api/analyze", json={"run_id": run_id})
    assert analyze_response.status_code == 200
    body = analyze_response.json()
    assert body["run_id"] == run_id
    file_result = body["files"]["data.csv"]
    assert file_result["status"] == "profiled"
    assert file_result["profile"]["row_count"] == 3
    assert file_result["profile"]["column_count"] == 2

    settings = get_settings()
    profile_path = settings.runs_dir / run_id / "profile.json"
    assert profile_path.exists()
    on_disk = json.loads(profile_path.read_text(encoding="utf-8"))
    assert on_disk["files"]["data.csv"]["profile"]["row_count"] == 3

    get_response = client.get(f"/api/profile/{run_id}")
    assert get_response.status_code == 200
    assert get_response.json() == on_disk


def test_analyze_nonexistent_run_returns_404():
    response = client.post("/api/analyze", json={"run_id": "run_does_not_exist"})
    assert response.status_code == 404


def test_get_profile_before_analyze_returns_404():
    content = b"a,b\n1,2\n"
    run_id = _upload(content)

    response = client.get(f"/api/profile/{run_id}")
    assert response.status_code == 404


def test_analyze_updates_run_metadata_status():
    content = b"a,b\n1,2\n3,4\n"
    run_id = _upload(content)

    client.post("/api/analyze", json={"run_id": run_id})

    settings = get_settings()
    metadata = json.loads((settings.runs_dir / run_id / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "profiled"


def test_analyze_mean_matches_hand_calculation():
    content = b"amount\n10\n20\n30\n40\n50\n"
    run_id = _upload(content, filename="amounts.csv")

    response = client.post("/api/analyze", json={"run_id": run_id})
    profile = response.json()["files"]["amounts.csv"]["profile"]
    amount_col = next(c for c in profile["columns"] if c["original_name"] == "amount")

    assert amount_col["mean"] == 30.0
    assert amount_col["min"] == 10.0
    assert amount_col["max"] == 50.0


def test_infinity_in_data_never_leaks_into_written_profile_json():
    """profile.json is read raw by pdf_report.py (json.loads) and can be downloaded
    directly by a client -- it must always be strictly valid JSON, never containing
    the non-standard Infinity/-Infinity/NaN tokens Python's json.dumps allows by
    default for a column that legitimately contains inf/-inf sentinel values."""
    content = b"id,amount\n1,10\n2,inf\n3,-inf\n4,20\n"
    run_id = _upload(content, filename="data.csv")

    response = client.post("/api/analyze", json={"run_id": run_id})
    assert response.status_code == 200

    settings = get_settings()
    profile_text = (settings.runs_dir / run_id / "profile.json").read_text(encoding="utf-8")
    assert "Infinity" not in profile_text
    assert "NaN" not in profile_text

    # Confirms it's genuinely valid JSON, not just missing those two substrings.
    import json

    json.loads(profile_text)
