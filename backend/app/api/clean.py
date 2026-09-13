"""Cleaning endpoint: applies HIGH/MEDIUM-confidence transformations.

Reads raw files from data/input/<run_id>/ (never modified), writes cleaned output to
data/output/<run_id>/. File-based only -- no database, no server-side session state.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.services.audit_logging import append_rows_to_csv, build_log_rows
from app.services.before_after import build_before_after_summary, build_snapshot_metrics
from app.services.cleaning import apply_cleaning
from app.services.data_dictionary import build_data_dictionary
from app.services.ingestion import IngestionError, load_dataset
from app.services.issue_detection import detect_issues
from app.services.lineage import build_lineage
from app.services.powerbi import assess_single_file_readiness
from app.services.profiling import profile_dataset
from app.services.project_plan import load_project_plan
from app.services.quality_score import compute_quality_score
from app.services.rollback import evaluate_gate
from app.services.run_metadata import compute_file_hash, record_processing_time, update_run_metadata
from app.utils.filesystem import get_run_dir, safe_join

router = APIRouter()
logger = logging.getLogger(__name__)


class CleanRequest(BaseModel):
    run_id: str


@router.post("/clean")
def clean_run(request: CleanRequest) -> dict:
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

    output_dir = safe_join(settings.output_dir, request.run_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    run_dir = get_run_dir(request.run_id)
    project_plan = load_project_plan(run_dir)
    protected_columns = set(project_plan.protected_columns) if project_plan else set()

    file_results: dict[str, dict] = {}
    all_audit_rows: list[dict] = []
    all_cleaning_rows: list[dict] = []
    file_lineage: dict[str, list[dict]] = {}
    all_lineage_rows: list[dict] = []
    rollback_reports: dict[str, dict] = {}
    metadata_files: dict[str, dict] = {}
    file_quality: dict[str, dict] = {}
    file_before_after: dict[str, dict] = {}
    all_dictionary_rows: list[dict] = []
    any_rolled_back = False
    for file_path in raw_files:
        try:
            ingestion_result = load_dataset(file_path)
            profile = profile_dataset(ingestion_result.dataframe, source_path=file_path)
            issues = detect_issues(ingestion_result.dataframe, profile)
            cleaning_result = apply_cleaning(ingestion_result.dataframe, issues, protected_columns=protected_columns)

            audit_rows, cleaning_rows = build_log_rows(
                request.run_id, file_path.name, issues, cleaning_result.log
            )
            all_audit_rows.extend(audit_rows)
            all_cleaning_rows.extend(cleaning_rows)

            lineage_entries = build_lineage(
                file_path.name,
                list(ingestion_result.dataframe.columns),
                list(cleaning_result.cleaned_df.columns),
                cleaning_result.log,
            )
            lineage_dicts = [entry.to_dict() for entry in lineage_entries]
            file_lineage[file_path.name] = lineage_dicts
            all_lineage_rows.extend(lineage_dicts)

            gate = evaluate_gate(cleaning_result.cleaned_df)

            # "After" side -- computed for both published and rolled-back files, since
            # even an unpublished attempt is useful diagnostic context for *why* it's
            # still not good enough (mirrors the PDF report's "Remaining Issues").
            cleaned_df = cleaning_result.cleaned_df
            after_profile = profile_dataset(cleaned_df)
            after_issues = detect_issues(cleaned_df, after_profile)
            before_powerbi = assess_single_file_readiness(ingestion_result.dataframe, profile, issues)
            after_powerbi = assess_single_file_readiness(cleaned_df, after_profile, after_issues)

            before_quality = compute_quality_score(
                ingestion_result.dataframe, profile, issues, None, before_powerbi.score
            )
            after_quality = compute_quality_score(
                cleaned_df, after_profile, after_issues, gate.validation_report, after_powerbi.score
            )
            file_quality[file_path.name] = {
                "before": before_quality.to_dict(),
                "after": after_quality.to_dict(),
                "published": gate.published,
            }

            before_snapshot = build_snapshot_metrics(
                ingestion_result.dataframe, profile, issues, before_quality.overall_score, before_powerbi.score
            )
            after_snapshot = build_snapshot_metrics(
                cleaned_df, after_profile, after_issues, after_quality.overall_score, after_powerbi.score
            )
            file_before_after[file_path.name] = build_before_after_summary(before_snapshot, after_snapshot)

            dictionary_rows = build_data_dictionary(after_profile, lineage_entries, cleaning_result.log)
            for row in dictionary_rows:
                all_dictionary_rows.append({"dataset": file_path.name, **row})

            if not gate.published:
                any_rolled_back = True
                rollback_reports[file_path.name] = gate.to_dict()
                metadata_files[file_path.name] = {"output_hash": None, "status": "rollback"}
                file_results[file_path.name] = {
                    "status": "rolled_back",
                    "reason": gate.reason,
                    "validation_report": gate.validation_report.to_dict(),
                }
                continue

            stem = file_path.stem
            csv_path = safe_join(output_dir, f"{stem}_cleaned.csv")
            xlsx_path = safe_join(output_dir, f"{stem}_cleaned.xlsx")
            cleaning_result.cleaned_df.to_csv(csv_path, index=False)
            cleaning_result.cleaned_df.to_excel(xlsx_path, index=False)

            metadata_files[file_path.name] = {"output_hash": compute_file_hash(csv_path), "status": "cleaned"}

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
                "validation_report": gate.validation_report.to_dict(),
            }
        except IngestionError as exc:
            file_results[file_path.name] = {"status": "failed", "reason": exc.reason}
        except Exception:
            logger.exception("Unexpected error cleaning %s", file_path)
            file_results[file_path.name] = {"status": "failed", "reason": "Could not clean this file."}

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

    lineage_result = {
        "run_id": request.run_id,
        "timestamp": result["timestamp"],
        "files": file_lineage,
    }
    (run_dir / "data_lineage.json").write_text(
        json.dumps(lineage_result, indent=2, default=str), encoding="utf-8"
    )
    if all_lineage_rows:
        pd.DataFrame(all_lineage_rows).to_csv(run_dir / "data_lineage.csv", index=False)

    if rollback_reports:
        rollback_result = {
            "run_id": request.run_id,
            "timestamp": result["timestamp"],
            "files": rollback_reports,
        }
        (run_dir / "rollback_report.json").write_text(
            json.dumps(rollback_result, indent=2, default=str), encoding="utf-8"
        )

    quality_result = {
        "run_id": request.run_id,
        "timestamp": result["timestamp"],
        "files": file_quality,
    }
    (run_dir / "quality_report.json").write_text(
        json.dumps(quality_result, indent=2, default=str), encoding="utf-8"
    )

    before_after_result = {
        "run_id": request.run_id,
        "timestamp": result["timestamp"],
        "files": file_before_after,
    }
    (run_dir / "before_after_summary.json").write_text(
        json.dumps(before_after_result, indent=2, default=str), encoding="utf-8"
    )
    before_after_rows = [
        {"dataset": dataset, "metric": metric, **values}
        for dataset, metrics in file_before_after.items()
        for metric, values in metrics.items()
    ]
    if before_after_rows:
        pd.DataFrame(before_after_rows).to_csv(run_dir / "before_after_summary.csv", index=False)

    if all_dictionary_rows:
        pd.DataFrame(all_dictionary_rows).to_csv(run_dir / "data_dictionary.csv", index=False)

    update_run_metadata(
        run_dir,
        status="rollback" if any_rolled_back else "cleaned",
        files=metadata_files,
    )
    record_processing_time(run_dir, "clean", time.perf_counter() - start_time)

    return result
