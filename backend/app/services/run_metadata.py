"""File-Based Run Metadata (DATAQX.pdf S34).

Consolidates run_metadata.json reads/writes into one shared helper instead of every
endpoint hand-rolling its own json.loads/mutate/json.dumps. File-based only, no
database. quality_score/powerbi_readiness are left null until the phases that
actually compute them exist -- S63 forbids inventing scores.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from app.services.project_plan import ProjectPlan

_MAX_PROJECT_NAME_WORDS = 8


def compute_file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_run_metadata(run_dir: Path) -> dict:
    metadata_path = run_dir / "run_metadata.json"
    if not metadata_path.exists():
        return {}
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def write_run_metadata(run_dir: Path, metadata: dict) -> None:
    metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
    (run_dir / "run_metadata.json").write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")


def update_run_metadata(run_dir: Path, files: dict | None = None, **top_level_updates) -> dict:
    """Read-merge-write run_metadata.json.

    Top-level keys in `top_level_updates` overwrite existing values. `files` is
    deep-merged per filename (and per-field within a filename) so different
    endpoints can each update their own per-file fields without clobbering the
    other's -- e.g. upload sets input_hash, clean later adds output_hash for the
    same file entry.
    """
    metadata = read_run_metadata(run_dir)
    metadata.update(top_level_updates)

    if files:
        existing_files = metadata.setdefault("files", {})
        for filename, file_updates in files.items():
            existing_files.setdefault(filename, {}).update(file_updates)

    write_run_metadata(run_dir, metadata)
    return metadata


def record_processing_time(run_dir: Path, stage: str, seconds: float) -> None:
    metadata = read_run_metadata(run_dir)
    processing_time = metadata.setdefault("processing_time_seconds", {})
    processing_time[stage] = round(seconds, 6)
    write_run_metadata(run_dir, metadata)


def accumulate_processing_time(run_dir: Path, stage: str, seconds: float) -> None:
    """Add to a stage's recorded time rather than overwrite it.

    Used for the finer-grained S57 stages (file_loading, profiling, issue_detection,
    ...) that occur across multiple endpoints (/analyze, /clean, /validate) for the
    same run -- an overwrite would silently discard an earlier endpoint's measurement.
    S58's bottleneck detection wants each stage's true cumulative cost across the run.
    """
    metadata = read_run_metadata(run_dir)
    processing_time = metadata.setdefault("processing_time_seconds", {})
    processing_time[stage] = round(processing_time.get(stage, 0.0) + seconds, 6)
    write_run_metadata(run_dir, metadata)


def derive_project_name(project_plan: ProjectPlan | None) -> str | None:
    if project_plan is None or not project_plan.objective:
        return None
    words = project_plan.objective.split()
    return " ".join(words[:_MAX_PROJECT_NAME_WORDS])
