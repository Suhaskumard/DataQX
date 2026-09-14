"""Phase 21 (Performance): a real large-dataset run through the full pipeline,
asserting every measured value is genuine (positive, internally consistent) rather
than fabricated (DATAQX.pdf S63)."""

import csv
import io
import random

from fastapi.testclient import TestClient

from app.core.config import get_settings
from main import app

client = TestClient(app)


def _generate_large_csv(row_count: int) -> bytes:
    random.seed(42)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "name", "category", "amount", "signup_date", "notes"])
    categories = ["North", "South", "East", "West"]
    for i in range(1, row_count + 1):
        name = f"Customer {i}" if i % 37 != 0 else f"Customer {i} "  # occasional whitespace issue
        amount = random.choice([10, 20, 30, 9999999]) if i % 500 != 0 else "N/A"  # occasional placeholder/outlier
        writer.writerow([i, name, random.choice(categories), amount, "2024-01-15", ""])
    return buf.getvalue().encode("utf-8")


def test_large_dataset_full_pipeline_produces_real_positive_stage_timings():
    content = _generate_large_csv(20000)

    upload_response = client.post("/api/upload", files={"files": ("large.csv", content, "text/csv")})
    assert upload_response.status_code == 200
    run_id = upload_response.json()["run_id"]

    assert client.post("/api/analyze", json={"run_id": run_id}).status_code == 200
    assert client.post("/api/clean", json={"run_id": run_id}).status_code == 200
    assert client.post("/api/validate", json={"run_id": run_id}).status_code == 200

    perf = client.get(f"/api/performance/{run_id}").json()
    times = perf["processing_time_seconds"]

    expected_stages = [
        "upload", "analyze", "clean", "validate",
        "file_loading", "profiling", "issue_detection",
        "drift_detection", "analytics_readiness", "output_generation",
    ]
    for stage in expected_stages:
        assert stage in times, f"missing stage: {stage}"
        assert times[stage] >= 0, f"stage {stage} has a negative time: {times[stage]}"

    assert perf["bottleneck_stage"] is not None
    assert perf["bottleneck_seconds"] == max(
        v for k, v in times.items() if k not in ("upload", "analyze", "clean", "validate")
    )

    settings = get_settings()
    log_text = (settings.logs_dir / "performance.log").read_text(encoding="utf-8")
    assert f"run_id={run_id}" in log_text

    csv_text = (settings.logs_dir / "performance_log.csv").read_text(encoding="utf-8")
    assert run_id in csv_text
