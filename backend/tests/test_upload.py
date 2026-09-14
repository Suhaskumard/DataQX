import hashlib
import json

from fastapi.testclient import TestClient

from app.core.config import get_settings
from main import app

client = TestClient(app)


def test_valid_csv_upload_saved_byte_identical():
    content = b"id,name\n1,Alice\n2,Bob\n"
    response = client.post(
        "/api/upload",
        files={"files": ("customers.csv", content, "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    run_id = body["run_id"]
    assert len(body["files"]) == 1
    file_result = body["files"][0]
    assert file_result["status"] == "saved"
    assert file_result["saved_name"] == "customers.csv"

    settings = get_settings()
    saved_path = settings.input_dir / run_id / "customers.csv"
    assert saved_path.exists()
    assert saved_path.read_bytes() == content
    assert hashlib.sha256(saved_path.read_bytes()).hexdigest() == hashlib.sha256(content).hexdigest()


def test_disallowed_extension_rejected():
    response = client.post(
        "/api/upload",
        files={"files": ("malware.exe", b"not a real exe", "application/octet-stream")},
    )
    assert response.status_code == 200
    body = response.json()
    file_result = body["files"][0]
    assert file_result["status"] == "rejected"
    assert "Unsupported file type" in file_result["reason"]

    settings = get_settings()
    run_dir = settings.input_dir / body["run_id"]
    assert not any(run_dir.iterdir()) if run_dir.exists() else True


def test_empty_file_rejected():
    response = client.post(
        "/api/upload",
        files={"files": ("empty.csv", b"", "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    file_result = body["files"][0]
    assert file_result["status"] == "rejected"
    assert "empty" in file_result["reason"].lower()


def test_oversized_file_rejected_and_cleaned_up(monkeypatch):
    from app.core.config import Settings

    tiny_settings = Settings(max_upload_size_mb=0)  # ~0 MB effective cap -> anything trips it

    def fake_get_settings():
        return tiny_settings

    monkeypatch.setattr("app.api.upload.get_settings", fake_get_settings)

    content = b"a" * 10_000  # 10 KB, larger than the 0-byte-ish cap
    response = client.post(
        "/api/upload",
        files={"files": ("big.csv", content, "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    file_result = body["files"][0]
    assert file_result["status"] == "rejected"
    assert "maximum allowed size" in file_result["reason"]

    # No leftover partial file under this run's input dir.
    run_dir = tiny_settings.input_dir / body["run_id"]
    if run_dir.exists():
        assert list(run_dir.iterdir()) == []


def test_path_traversal_filename_is_sanitized():
    content = b"col1,col2\n1,2\n"
    response = client.post(
        "/api/upload",
        files={"files": ("../../evil.csv", content, "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    file_result = body["files"][0]
    assert file_result["status"] == "saved"
    assert ".." not in file_result["saved_name"]
    assert "/" not in file_result["saved_name"] and "\\" not in file_result["saved_name"]

    settings = get_settings()
    run_id = body["run_id"]
    saved_path = settings.input_dir / run_id / file_result["saved_name"]
    assert saved_path.exists()
    # Must stay inside this run's input directory, not escape to data/input/ or above.
    assert saved_path.parent == (settings.input_dir / run_id)


def test_colliding_sanitized_filenames_are_disambiguated_not_overwritten():
    """Two distinct original filenames that sanitize to the same safe name must not
    silently overwrite each other on disk while both report status="saved"."""
    content_a = b"a,b\n1,2\n"
    content_b = b"a,b\n3,4\n"
    response = client.post(
        "/api/upload",
        files=[
            ("files", ("sales@2024.csv", content_a, "text/csv")),
            ("files", ("sales#2024.csv", content_b, "text/csv")),
        ],
    )
    assert response.status_code == 200
    body = response.json()
    saved_names = [f["saved_name"] for f in body["files"] if f["status"] == "saved"]
    assert len(saved_names) == 2
    assert len(set(saved_names)) == 2  # distinct names -- no collision

    settings = get_settings()
    run_dir = settings.input_dir / body["run_id"]
    on_disk = {p.name: p.read_bytes() for p in run_dir.iterdir()}
    assert on_disk[saved_names[0]] == content_a
    assert on_disk[saved_names[1]] == content_b


def test_project_plan_text_saved():
    content = b"id\n1\n"
    response = client.post(
        "/api/upload",
        files={"files": ("data.csv", content, "text/csv")},
        data={"project_plan_text": "# My Project\nObjective: test."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["project_plan"]["status"] == "saved"

    settings = get_settings()
    plan_path = settings.runs_dir / body["run_id"] / "project_plan.md"
    assert plan_path.exists()
    assert plan_path.read_text(encoding="utf-8") == "# My Project\nObjective: test."


def test_multiple_files_mixed_validity():
    good_content = b"a,b\n1,2\n"
    response = client.post(
        "/api/upload",
        files=[
            ("files", ("good.csv", good_content, "text/csv")),
            ("files", ("bad.exe", b"xx", "application/octet-stream")),
        ],
    )
    assert response.status_code == 200
    body = response.json()
    statuses = {f["original_name"]: f["status"] for f in body["files"]}
    assert statuses["good.csv"] == "saved"
    assert statuses["bad.exe"] == "rejected"


def test_run_metadata_written():
    content = b"a\n1\n"
    response = client.post(
        "/api/upload",
        files={"files": ("data.csv", content, "text/csv")},
    )
    body = response.json()
    settings = get_settings()
    metadata_path = settings.runs_dir / body["run_id"] / "run_metadata.json"
    assert metadata_path.exists()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["run_id"] == body["run_id"]
    assert metadata["status"] == "uploaded"
    assert "timestamp" in metadata

    # Phase 14: consolidated fields.
    expected_hash = hashlib.sha256(content).hexdigest()
    assert metadata["files"]["data.csv"]["input_hash"] == expected_hash
    assert metadata["files"]["data.csv"]["output_hash"] is None
    assert metadata["quality_score"] is None  # never fabricated (S63)
    assert metadata["analytics_readiness"] is None
    assert metadata["processing_time_seconds"]["upload"] > 0


def test_same_filename_across_runs_never_collides():
    content_a = b"version,1\n"
    content_b = b"version,2\n"

    response_a = client.post(
        "/api/upload", files={"files": ("data.csv", content_a, "text/csv")}
    )
    response_b = client.post(
        "/api/upload", files={"files": ("data.csv", content_b, "text/csv")}
    )

    run_id_a = response_a.json()["run_id"]
    run_id_b = response_b.json()["run_id"]
    assert run_id_a != run_id_b

    settings = get_settings()
    path_a = settings.input_dir / run_id_a / "data.csv"
    path_b = settings.input_dir / run_id_b / "data.csv"
    assert path_a.read_bytes() == content_a
    assert path_b.read_bytes() == content_b
