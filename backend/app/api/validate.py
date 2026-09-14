"""Validation endpoint: runs the Validation Engine against a run's cleaned data.

Re-derives the ingestion->profiling->detection->cleaning pipeline (stateless,
consistent with the other endpoints) rather than depending on stored intermediate
state. File-based only -- writes reports/runs/<run_id>/validation_report.json.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.services.cleaning import apply_cleaning
from app.services.ingestion import IngestionError, load_dataset
from app.services.issue_detection import detect_issues
from app.services.performance_logging import identify_bottleneck, log_stage
from app.services.pipeline_cache import load_cache_entry, save_cache_entry
from app.services.profiling import profile_dataset
from app.services.run_metadata import (
    accumulate_processing_time,
    read_run_metadata,
    record_processing_time,
    update_run_metadata,
)
from app.services.validation import validate_dataset
from app.utils.filesystem import get_run_dir, safe_join
from app.utils.json_safe import sanitize_for_json

router = APIRouter()
logger = logging.getLogger(__name__)


class ValidateRequest(BaseModel):
    run_id: str


@router.post("/validate")
def validate_run(request: ValidateRequest) -> dict:
    start_time = time.perf_counter()
    settings = get_settings()
    try:
        input_dir = safe_join(settings.input_dir, request.run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id.")

    if not input_dir.exists() or not input_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"No uploaded files found for run '{request.run_id}'.")

    raw_files = sorted(p for p in input_dir.iterdir() if p.is_file())
    if not raw_files:
        raise HTTPException(status_code=404, detail=f"No uploaded files found for run '{request.run_id}'.")

    run_dir = get_run_dir(request.run_id)
    file_results: dict[str, dict] = {}
    stage_totals = {"file_loading": 0.0, "profiling": 0.0, "issue_detection": 0.0}
    for file_path in raw_files:
        try:
            stage_start = time.perf_counter()
            ingestion_result = load_dataset(file_path)
            stage_totals["file_loading"] += time.perf_counter() - stage_start

            stage_start = time.perf_counter()
            cached = load_cache_entry(run_dir, file_path)
            if cached is not None:
                profile, issues = cached
                stage_totals["profiling"] += time.perf_counter() - stage_start
            else:
                stage_start = time.perf_counter()
                profile = profile_dataset(ingestion_result.dataframe, source_path=file_path)
                stage_totals["profiling"] += time.perf_counter() - stage_start

                stage_start = time.perf_counter()
                issues = detect_issues(ingestion_result.dataframe, profile)
                stage_totals["issue_detection"] += time.perf_counter() - stage_start

                save_cache_entry(run_dir, file_path, profile, issues)

            cleaning_result = apply_cleaning(ingestion_result.dataframe, issues)
            report = validate_dataset(cleaning_result.cleaned_df)

            file_results[file_path.name] = {
                "status": "validated",
                "overall_status": report.overall_status,
                "checks": [check.to_dict() for check in report.checks],
            }
        except IngestionError as exc:
            file_results[file_path.name] = {"status": "failed", "reason": exc.reason}
        except Exception:
            logger.exception("Unexpected error validating %s", file_path)
            file_results[file_path.name] = {"status": "failed", "reason": "Could not validate this file."}

    result = {
        "run_id": request.run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "files": file_results,
    }
    (run_dir / "validation_report.json").write_text(
        json.dumps(sanitize_for_json(result), indent=2, default=str), encoding="utf-8"
    )

    update_run_metadata(run_dir, status="validated")
    record_processing_time(run_dir, "validate", time.perf_counter() - start_time)
    for stage, seconds in stage_totals.items():
        accumulate_processing_time(run_dir, stage, seconds)
        log_stage(settings.logs_dir, request.run_id, stage, seconds)

    # Validate is the last stage of the standard upload -> analyze -> clean -> validate
    # pipeline (DATAQX.pdf S58: identify the most expensive stage from real values).
    # Only the S57-named sub-stages are compared -- "upload"/"analyze"/"clean"/"validate"
    # are coarse per-endpoint wrappers that contain those sub-stages, so including them
    # would trivially always win without pointing at the actual expensive work.
    metadata = read_run_metadata(run_dir)
    all_times = metadata.get("processing_time_seconds", {})
    sub_stage_times = {
        k: v
        for k, v in all_times.items()
        if k not in ("upload", "analyze", "clean", "validate")
    }
    bottleneck = identify_bottleneck(sub_stage_times)
    if bottleneck is not None:
        update_run_metadata(run_dir, bottleneck_stage=bottleneck["stage"], bottleneck_seconds=bottleneck["seconds"])

    return result
