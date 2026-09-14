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
from app.services.performance_logging import log_stage
from app.services.analytics_readiness import evaluate_analytics_readiness
from app.services.pipeline_cache import load_cache_entry, save_cache_entry
from app.services.platform_rules.common import PlatformCheck, compute_score, status_from_checks
from app.services.profiling import profile_dataset
from app.services.project_plan import load_project_plan
from app.services.quality_score import compute_quality_score
from app.services.rollback import evaluate_gate
from app.services.semantic_roles import classify_columns, role_labels_by_column
from app.services.run_metadata import (
    accumulate_processing_time,
    compute_file_hash,
    record_processing_time,
    update_run_metadata,
)
from app.utils.filesystem import get_run_dir, safe_join
from app.utils.json_safe import sanitize_for_json

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
    file_analytics_readiness_after: dict[str, dict] = {}
    all_dictionary_rows: list[dict] = []
    any_rolled_back = False
    stage_totals = {"file_loading": 0.0, "profiling": 0.0, "issue_detection": 0.0, "output_generation": 0.0}
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

            cleaning_result = apply_cleaning(ingestion_result.dataframe, issues, protected_columns=protected_columns)

            audit_rows, cleaning_rows = build_log_rows(
                request.run_id, file_path.name, issues, cleaning_result.log, cleaning_result.protected_skips
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

            # "After" side -- computed for both published and rolled-back files, since
            # even an unpublished attempt is useful diagnostic context for *why* it's
            # still not good enough (mirrors the PDF report's "Remaining Issues"). Also
            # needed by the rollback gate itself, to catch a cleaning step that silently
            # destroyed recoverable data (e.g. valid dates -> null) even when every
            # other validation check still passes.
            cleaned_df = cleaning_result.cleaned_df
            after_profile = profile_dataset(cleaned_df)
            after_issues = detect_issues(cleaned_df, after_profile)
            gate = evaluate_gate(cleaned_df, before_profile=profile, after_profile=after_profile)
            before_readiness = evaluate_analytics_readiness(ingestion_result.dataframe, profile, issues)
            after_readiness = evaluate_analytics_readiness(cleaned_df, after_profile, after_issues)
            file_analytics_readiness_after[file_path.name] = after_readiness.to_dict()

            before_quality = compute_quality_score(
                ingestion_result.dataframe, profile, issues, None, before_readiness.overall_score
            )
            after_quality = compute_quality_score(
                cleaned_df, after_profile, after_issues, gate.validation_report, after_readiness.overall_score
            )
            file_quality[file_path.name] = {
                "before": before_quality.to_dict(),
                "after": after_quality.to_dict(),
                "published": gate.published,
            }

            before_snapshot = build_snapshot_metrics(
                ingestion_result.dataframe, profile, issues, before_quality.overall_score, before_readiness.overall_score
            )
            after_snapshot = build_snapshot_metrics(
                cleaned_df, after_profile, after_issues, after_quality.overall_score, after_readiness.overall_score
            )
            file_before_after[file_path.name] = build_before_after_summary(before_snapshot, after_snapshot)

            platform_field_roles = {
                name: platform_result.field_roles for name, platform_result in after_readiness.platforms.items()
            }
            semantic_role_labels = role_labels_by_column(classify_columns(after_profile))
            dictionary_rows = build_data_dictionary(
                after_profile, lineage_entries, cleaning_result.log, platform_field_roles, semantic_role_labels
            )
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

            stage_start = time.perf_counter()
            stem = file_path.stem
            csv_path = safe_join(output_dir, f"{stem}_cleaned.csv")
            xlsx_path = safe_join(output_dir, f"{stem}_cleaned.xlsx")
            cleaning_result.cleaned_df.to_csv(csv_path, index=False)
            cleaning_result.cleaned_df.to_excel(xlsx_path, index=False)
            stage_totals["output_generation"] += time.perf_counter() - stage_start

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
    (run_dir / "cleaning_log.json").write_text(json.dumps(sanitize_for_json(result), indent=2, default=str), encoding="utf-8")

    if all_cleaning_rows:
        pd.DataFrame(all_cleaning_rows).to_csv(run_dir / "cleaning_log.csv", index=False)

    if all_audit_rows:
        pd.DataFrame(all_audit_rows).to_csv(run_dir / "audit_log.csv", index=False)

    append_rows_to_csv(settings.logs_dir / "audit_log.csv", all_audit_rows)
    append_rows_to_csv(settings.logs_dir / "cleaning_log.csv", all_cleaning_rows)

    lineage_result = {
        "run_id": request.run_id,
        "timestamp": result["timestamp"],
        "files": file_lineage,
    }
    (run_dir / "data_lineage.json").write_text(
        json.dumps(sanitize_for_json(lineage_result), indent=2, default=str), encoding="utf-8"
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
            json.dumps(sanitize_for_json(rollback_result), indent=2, default=str), encoding="utf-8"
        )

    quality_result = {
        "run_id": request.run_id,
        "timestamp": result["timestamp"],
        "files": file_quality,
    }
    (run_dir / "quality_report.json").write_text(
        json.dumps(sanitize_for_json(quality_result), indent=2, default=str), encoding="utf-8"
    )

    before_after_result = {
        "run_id": request.run_id,
        "timestamp": result["timestamp"],
        "files": file_before_after,
    }
    (run_dir / "before_after_summary.json").write_text(
        json.dumps(sanitize_for_json(before_after_result), indent=2, default=str), encoding="utf-8"
    )

    # The Analytics Readiness snapshot written by /api/analyze reflects the raw,
    # pre-cleaning data and is never touched again by default -- once cleaning
    # publishes an improved dataset, every other view of "current" readiness
    # (Dashboard, the Analytics Readiness page, the PDF report) must stop showing
    # that stale pre-clean score instead of silently disagreeing with the correct,
    # freshly-computed "after" figure already shown on Before/After.
    if file_analytics_readiness_after:
        readiness_path = run_dir / "analytics_readiness.json"
        existing_readiness = (
            json.loads(readiness_path.read_text(encoding="utf-8")) if readiness_path.exists() else {"files": {}}
        )
        existing_files = existing_readiness.get("files", {})
        for filename, after_result in file_analytics_readiness_after.items():
            existing_platforms = existing_files.get(filename, {}).get("platforms", {})
            for platform_name, after_platform in after_result["platforms"].items():
                # Cross-file relationship checks depend on data this endpoint doesn't
                # recompute here (every file in the run, not just this one) and aren't
                # affected by column-level cleaning of a protected join key -- carry
                # them forward from the analyze-stage snapshot instead of dropping them.
                preserved_relationship_checks = [
                    c for c in existing_platforms.get(platform_name, {}).get("checks", [])
                    if c.get("check_name") == "foreign_key_relationships"
                ]
                if preserved_relationship_checks:
                    merged_checks = [PlatformCheck(**c) for c in after_platform["checks"] + preserved_relationship_checks]
                    after_platform["checks"] = [c.to_dict() for c in merged_checks]
                    after_platform["score"] = compute_score(merged_checks)
                    after_platform["status"] = status_from_checks(merged_checks)
                    after_platform["passed_checks"] = [c.to_dict() for c in merged_checks if c.status == "pass"]
                    after_platform["warnings"] = [c.to_dict() for c in merged_checks if c.status == "warning"]
                    after_platform["critical_issues"] = [c.to_dict() for c in merged_checks if c.status == "fail"]
            after_result["overall_score"] = round(
                sum(p["score"] for p in after_result["platforms"].values()) / len(after_result["platforms"])
            )
            existing_files[filename] = after_result
        existing_readiness["files"] = existing_files
        existing_readiness["run_id"] = request.run_id
        existing_readiness["timestamp"] = result["timestamp"]
        readiness_path.write_text(
            json.dumps(sanitize_for_json(existing_readiness), indent=2, default=str), encoding="utf-8"
        )

        overall_analytics_readiness_score = round(
            sum(f["overall_score"] for f in existing_files.values()) / len(existing_files)
        )
        update_run_metadata(run_dir, analytics_readiness=overall_analytics_readiness_score)
    before_after_rows = [
        {"dataset": dataset, "metric": metric, **values}
        for dataset, metrics in file_before_after.items()
        for metric, values in metrics.items()
    ]
    if before_after_rows:
        pd.DataFrame(before_after_rows).to_csv(run_dir / "before_after_summary.csv", index=False)

    if all_dictionary_rows:
        pd.DataFrame(all_dictionary_rows).to_csv(run_dir / "data_dictionary.csv", index=False)

    overall_quality_score = (
        round(sum(f["after"]["overall_score"] for f in file_quality.values()) / len(file_quality))
        if file_quality else None
    )

    update_run_metadata(
        run_dir,
        status="rollback" if any_rolled_back else "cleaned",
        files=metadata_files,
        quality_score=overall_quality_score,
    )
    record_processing_time(run_dir, "clean", time.perf_counter() - start_time)
    for stage, seconds in stage_totals.items():
        accumulate_processing_time(run_dir, stage, seconds)
        log_stage(settings.logs_dir, request.run_id, stage, seconds)

    return result
