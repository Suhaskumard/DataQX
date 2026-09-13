"""Cleaning endpoint: applies HIGH/MEDIUM-confidence transformations.

Reads raw files from data/input/<run_id>/ (never modified), writes cleaned output to
data/output/<run_id>/. File-based only -- no database, no server-side session state.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.services.audit_logging import append_rows_to_csv, build_log_rows
from app.services.cleaning import apply_cleaning
from app.services.ingestion import IngestionError, load_dataset
from app.services.issue_detection import detect_issues
from app.services.profiling import profile_dataset
from app.utils.filesystem import get_run_dir, safe_join

router = APIRouter()
logger = logging.getLogger(__name__)


class CleanRequest(BaseModel):
    run_id: str


@router.post("/clean")
def clean_run(request: CleanRequest) -> dict:
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

    output_dir = safe_join(settings.output_dir, request.run_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    file_results: dict[str, dict] = {}
    all_audit_rows: list[dict] = []
    all_cleaning_rows: list[dict] = []
    for file_path in raw_files:
        try:
            ingestion_result = load_dataset(file_path)
            profile = profile_dataset(ingestion_result.dataframe, source_path=file_path)
            issues = detect_issues(ingestion_result.dataframe, profile)
            cleaning_result = apply_cleaning(ingestion_result.dataframe, issues)

            stem = file_path.stem
            csv_path = safe_join(output_dir, f"{stem}_cleaned.csv")
            xlsx_path = safe_join(output_dir, f"{stem}_cleaned.xlsx")
            cleaning_result.cleaned_df.to_csv(csv_path, index=False)
            cleaning_result.cleaned_df.to_excel(xlsx_path, index=False)

            audit_rows, cleaning_rows = build_log_rows(
                request.run_id, file_path.name, issues, cleaning_result.log
            )
            all_audit_rows.extend(audit_rows)
            all_cleaning_rows.extend(cleaning_rows)

            file_results[file_path.name] = {
                "status": "cleaned",
                "output_csv": str(csv_path.relative_to(settings.repo_root)),
                "output_xlsx": str(xlsx_path.relative_to(settings.repo_root)),
                "rows_before": int(profile.row_count),
                "rows_after": int(len(cleaning_result.cleaned_df)),
                "columns_before": int(profile.column_count),
                "columns_after": int(len(cleaning_result.cleaned_df.columns)),
                "log": [entry.to_dict() for entry in cleaning_result.log],
                "skipped_low_confidence": cleaning_result.skipped_low_confidence,
            }
        except IngestionError as exc:
            file_results[file_path.name] = {"status": "failed", "reason": exc.reason}
        except Exception:
            logger.exception("Unexpected error cleaning %s", file_path)
            file_results[file_path.name] = {"status": "failed", "reason": "Could not clean this file."}

    run_dir = get_run_dir(request.run_id)
    result = {
        "run_id": request.run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "files": file_results,
    }
    (run_dir / "cleaning_log.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

    if all_cleaning_rows:
        pd.DataFrame(all_cleaning_rows).to_csv(run_dir / "cleaning_log.csv", index=False)

    append_rows_to_csv(settings.logs_dir / "audit_log.csv", all_audit_rows)
    append_rows_to_csv(settings.logs_dir / "cleaning_log.csv", all_cleaning_rows)

    metadata_path = run_dir / "run_metadata.json"
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["status"] = "cleaned"
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return result
