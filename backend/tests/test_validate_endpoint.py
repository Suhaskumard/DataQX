import json

from fastapi.testclient import TestClient

from app.core.config import get_settings
from main import app

client = TestClient(app)


def _upload(content: bytes, filename: str = "data.csv") -> str:
    response = client.post("/api/upload", files={"files": (filename, content, "text/csv")})
    assert response.status_code == 200
    return response.json()["run_id"]


def test_validate_endpoint_reports_duplicate_id_failure():
    # customer_id has 19 rows -> 95% unique with one duplicate, name matches "id"
    # pattern -> inferred as an ID column; duplicate IDs are LOW confidence and never
    # auto-fixed, so validation should legitimately fail on id_uniqueness.
    # The duplicated-ID row has a DIFFERENT status value from its counterpart so the
    # two rows are not also full-row duplicates -- otherwise the (correct) HIGH-
    # confidence duplicate_rows cleanup would remove the extra row first, coincidentally
    # resolving the ID collision before validation ever sees it.
    rows = [f"{i},active" for i in range(1, 19)] + ["18,inactive"]
    content = ("customer_id,status\n" + "\n".join(rows) + "\n").encode()
    run_id = _upload(content)

    client.post("/api/analyze", json={"run_id": run_id})
    client.post("/api/clean", json={"run_id": run_id})
    response = client.post("/api/validate", json={"run_id": run_id})

    assert response.status_code == 200
    body = response.json()
    file_result = body["files"]["data.csv"]
    assert file_result["status"] == "validated"

    check_statuses = {c["check_name"]: c["status"] for c in file_result["checks"]}
    assert check_statuses["id_uniqueness"] == "fail"
    assert file_result["overall_status"] == "fail"

    settings = get_settings()
    disk_report = json.loads(
        (settings.runs_dir / run_id / "validation_report.json").read_text(encoding="utf-8")
    )
    assert disk_report == body

    metadata = json.loads((settings.runs_dir / run_id / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "validated"


def test_validate_endpoint_passes_for_clean_data():
    content = b"id,amount\n1,10\n2,20\n3,30\n4,40\n"
    run_id = _upload(content)

    client.post("/api/analyze", json={"run_id": run_id})
    client.post("/api/clean", json={"run_id": run_id})
    response = client.post("/api/validate", json={"run_id": run_id})

    assert response.status_code == 200
    file_result = response.json()["files"]["data.csv"]
    assert file_result["overall_status"] == "pass"


def test_validate_endpoint_404_for_nonexistent_run():
    response = client.post("/api/validate", json={"run_id": "run_does_not_exist"})
    assert response.status_code == 404


def test_validate_standalone_without_prior_analyze_or_clean_still_works():
    """Phase 21: /validate must still fully re-derive the pipeline (cache-miss fallback)
    when called without /analyze or /clean ever having run for this run_id -- the new
    disk cache is an optimization for the common sequence, never a hard dependency."""
    content = b"id,amount\n1,10\n2,20\n3,30\n4,40\n"
    run_id = _upload(content)

    response = client.post("/api/validate", json={"run_id": run_id})

    assert response.status_code == 200
    file_result = response.json()["files"]["data.csv"]
    assert file_result["status"] == "validated"
    assert file_result["overall_status"] == "pass"


def test_analyze_then_validate_reuses_cached_profile_and_issues():
    """A cache hit in /validate should be measurably faster than /analyze's own cold
    computation of the same stage -- a real, proportional check, not a fabricated number.

    Uses a multi-column, several-thousand-row dataset: a real (measured, not assumed)
    benchmark showed that for a very narrow 2-column dataset, profile_dataset() is so
    cheap that the JSON-deserialization cost of reading the cache back can actually
    exceed it -- the caching win only shows up once per-column analysis (categorical
    top-N, text/unicode scans, numeric stats across several columns) gives the cold
    path real work to skip. That is the realistic shape this optimization targets.
    """
    rows = "\n".join(
        f"{i},Person {i},{['North', 'South', 'East', 'West'][i % 4]},{i * 1.5},2024-01-15,"
        for i in range(1, 5001)
    )
    content = f"id,name,category,amount,signup_date,notes\n{rows}\n".encode()
    run_id = _upload(content)

    client.post("/api/analyze", json={"run_id": run_id})
    perf_after_analyze = client.get(f"/api/performance/{run_id}").json()["processing_time_seconds"]
    cold_profiling_time = perf_after_analyze["profiling"]

    client.post("/api/validate", json={"run_id": run_id})
    perf_after_validate = client.get(f"/api/performance/{run_id}").json()["processing_time_seconds"]
    # profiling accumulates across endpoints (Phase 21), so the increment /validate added
    # is the new total minus what /analyze had already recorded.
    validate_profiling_increment = perf_after_validate["profiling"] - cold_profiling_time

    assert validate_profiling_increment < cold_profiling_time
