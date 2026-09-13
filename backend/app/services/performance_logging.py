"""Performance Monitoring & Bottleneck Detection (DATAQX.pdf S57/S58).

File-based only, no database. `log_stage()` appends every measured stage timing to a
global (cross-run) `logs/performance.log` and `logs/performance_log.csv`, independent
of the per-run `processing_time_seconds` already recorded in run_metadata.json by
`app.services.run_metadata.record_processing_time`. `identify_bottleneck()` finds the
most expensive stage from real measured values -- S58 requires actual measurement,
never an assumed or fabricated number.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.services.audit_logging import append_rows_to_csv

PERFORMANCE_LOG_COLUMNS = ["timestamp", "run_id", "stage", "seconds"]


def log_stage(logs_dir: Path, run_id: str, stage: str, seconds: float) -> None:
    """Append one measured stage timing to logs/performance.log and performance_log.csv."""
    timestamp = datetime.now(timezone.utc).isoformat()
    rounded = round(seconds, 6)

    logs_dir.mkdir(parents=True, exist_ok=True)
    log_line = f"{timestamp} | run_id={run_id} | stage={stage} | seconds={rounded}\n"
    with open(logs_dir / "performance.log", "a", encoding="utf-8") as f:
        f.write(log_line)

    append_rows_to_csv(
        logs_dir / "performance_log.csv",
        [{"timestamp": timestamp, "run_id": run_id, "stage": stage, "seconds": rounded}],
        columns=PERFORMANCE_LOG_COLUMNS,
    )


def identify_bottleneck(processing_times: dict[str, float]) -> dict | None:
    """Return {"stage": ..., "seconds": ...} for the slowest measured stage, or None if empty."""
    if not processing_times:
        return None
    stage = max(processing_times, key=processing_times.get)
    return {"stage": stage, "seconds": processing_times[stage]}
