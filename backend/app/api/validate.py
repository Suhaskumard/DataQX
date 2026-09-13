"""Validation endpoint: runs the Validation Engine against a run's cleaned data.

Re-derives the ingestion->profiling->detection->cleaning pipeline (stateless,
consistent with the other endpoints) rather than depending on stored intermediate
state. File-based only -- writes reports/runs/<run_id>/validation_report.json.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.services.cleaning import apply_cleaning
from app.services.ingestion import IngestionError, load_dataset
from app.services.issue_detection import detect_issues
from app.services.profiling import profile_dataset
from app.services.validation import validate_dataset
from app.utils.filesystem import get_run_dir, safe_join

router = APIRouter()
logger = logging.getLogger(__name__)


class ValidateRequest(BaseModel):
    run_id: str


@router.post("/validate")
def validate_run(request: ValidateRequest) -> dict:
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

    file_results: dict[str, dict] = {}
    for file_path in raw_files:
        try:
            ingestion_result = load_dataset(file_path)
            profile = profile_dataset(ingestion_result.dataframe, source_path=file_path)
            issues = detect_issues(ingestion_result.dataframe, profile)
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

    run_dir = get_run_dir(request.run_id)
    result = {
        "run_id": request.run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "files": file_results,
    }
    (run_dir / "validation_report.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )

    metadata_path = run_dir / "run_metadata.json"
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["status"] = "validated"
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return result
