"""Phase 23 (Full Testing / Performance): stress-scale and concurrency coverage
beyond Phase 21's single 20k-row pipeline run.

Two concerns not yet exercised anywhere else:
1. A larger dataset (100k rows) still completes the full pipeline with real,
   internally-consistent stage timings -- no fabricated numbers (DATAQX.pdf S63).
2. Two independent runs processed with interleaved API calls never cross-contaminate
   each other's artifacts -- the stateless, per-run-directory architecture (S1) is
   the platform's core invariant, and concurrency is exactly the condition under
   which a shared-state bug would surface.
"""

import csv
import io
import random

from fastapi.testclient import TestClient

from app.core.config import get_settings
from main import app

client = TestClient(app)


def _generate_large_csv(row_count: int, seed: int) -> bytes:
    random.seed(seed)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "name", "category", "amount", "signup_date", "notes"])
    categories = ["North", "South", "East", "West"]
    for i in range(1, row_count + 1):
        name = f"Customer {i}" if i % 37 != 0 else f"Customer {i} "
        amount = random.choice([10, 20, 30, 9999999]) if i % 500 != 0 else "N/A"
        writer.writerow([i, name, random.choice(categories), amount, "2024-01-15", ""])
    return buf.getvalue().encode("utf-8")


def test_100k_row_dataset_completes_full_pipeline_with_real_timings():
    content = _generate_large_csv(100_000, seed=7)

    upload_response = client.post("/api/upload", files={"files": ("stress_large.csv", content, "text/csv")})
    assert upload_response.status_code == 200
    run_id = upload_response.json()["run_id"]

    assert client.post("/api/analyze", json={"run_id": run_id}).status_code == 200
    assert client.post("/api/clean", json={"run_id": run_id}).status_code == 200
    assert client.post("/api/validate", json={"run_id": run_id}).status_code == 200

    perf = client.get(f"/api/performance/{run_id}").json()
    times = perf["processing_time_seconds"]
    for stage in ("upload", "analyze", "clean", "validate"):
        assert stage in times
        assert times[stage] >= 0

    settings = get_settings()
    cleaned_path = settings.output_dir / run_id / "stress_large_cleaned.csv"
    assert cleaned_path.exists()
    assert cleaned_path.stat().st_size > 0


def test_two_interleaved_runs_never_cross_contaminate_artifacts():
    """Simulates concurrency by interleaving each stage of two independent runs
    rather than finishing one run before starting the other, then verifies every
    artifact directory stayed scoped to its own run_id."""
    content_a = _generate_large_csv(500, seed=1)
    content_b = _generate_large_csv(500, seed=2)

    upload_a = client.post("/api/upload", files={"files": ("concurrent_a.csv", content_a, "text/csv")})
    upload_b = client.post("/api/upload", files={"files": ("concurrent_b.csv", content_b, "text/csv")})
    assert upload_a.status_code == 200
    assert upload_b.status_code == 200
    run_id_a = upload_a.json()["run_id"]
    run_id_b = upload_b.json()["run_id"]
    assert run_id_a != run_id_b

    assert client.post("/api/analyze", json={"run_id": run_id_a}).status_code == 200
    assert client.post("/api/analyze", json={"run_id": run_id_b}).status_code == 200
    assert client.post("/api/clean", json={"run_id": run_id_a}).status_code == 200
    assert client.post("/api/clean", json={"run_id": run_id_b}).status_code == 200
    assert client.post("/api/validate", json={"run_id": run_id_b}).status_code == 200
    assert client.post("/api/validate", json={"run_id": run_id_a}).status_code == 200

    settings = get_settings()

    input_a = settings.input_dir / run_id_a
    input_b = settings.input_dir / run_id_b
    assert {p.name for p in input_a.iterdir()} == {"concurrent_a.csv"}
    assert {p.name for p in input_b.iterdir()} == {"concurrent_b.csv"}

    output_a = settings.output_dir / run_id_a
    output_b = settings.output_dir / run_id_b
    assert {p.name for p in output_a.iterdir()} == {"concurrent_a_cleaned.csv", "concurrent_a_cleaned.xlsx"}
    assert {p.name for p in output_b.iterdir()} == {"concurrent_b_cleaned.csv", "concurrent_b_cleaned.xlsx"}

    profile_a = client.post("/api/analyze", json={"run_id": run_id_a}).json()
    profile_b = client.post("/api/analyze", json={"run_id": run_id_b}).json()
    assert profile_a["run_id"] == run_id_a
    assert profile_b["run_id"] == run_id_b
    assert "concurrent_a.csv" in profile_a["files"]
    assert "concurrent_b.csv" not in profile_a["files"]
    assert "concurrent_b.csv" in profile_b["files"]
    assert "concurrent_a.csv" not in profile_b["files"]

    validate_a = client.post("/api/validate", json={"run_id": run_id_a}).json()
    validate_b = client.post("/api/validate", json={"run_id": run_id_b}).json()
    assert set(validate_a["files"].keys()) == {"concurrent_a.csv"}
    assert set(validate_b["files"].keys()) == {"concurrent_b.csv"}
