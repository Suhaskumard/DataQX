"""Analyze endpoint: loads a run's raw file(s) and computes their profile.

File-based only: reads from data/input/<run_id>/, writes to reports/runs/<run_id>/.
No database, no server-side session state -- every request is scoped by run_id.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.services.audit_logging import append_rows_to_csv
from app.services.confidence import classify_issue
from app.services.drift import detect_drift, find_previous_profile, save_profile_snapshot
from app.services.ingestion import IngestionError, load_dataset
from app.services.issue_detection import detect_issues
from app.services.profiling import profile_dataset
from app.services.project_plan import check_required_columns, load_project_plan
from app.services.run_metadata import record_processing_time, update_run_metadata
from app.utils.filesystem import get_run_dir, safe_join

router = APIRouter()
logger = logging.getLogger(__name__)


class AnalyzeRequest(BaseModel):
    run_id: str


@router.post("/analyze")
def analyze_run(request: AnalyzeRequest) -> dict:
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
    project_plan = load_project_plan(run_dir)

    file_profiles: dict[str, dict] = {}
    file_issues: dict[str, list] = {}
    file_drift: dict[str, dict] = {}
    all_drift_rows: list[dict] = []
    for file_path in raw_files:
        try:
            ingestion_result = load_dataset(file_path)
            profile = profile_dataset(ingestion_result.dataframe, source_path=file_path)
            issues = detect_issues(ingestion_result.dataframe, profile)
            if project_plan is not None:
                issues = issues + check_required_columns(ingestion_result.dataframe, project_plan)
            issues_with_confidence = [
                {**issue.to_dict(), "confidence": classify_issue(issue).to_dict()} for issue in issues
            ]
            file_profiles[file_path.name] = {
                "status": "profiled",
                "detected_format": ingestion_result.detected_format,
                "ingestion_warnings": ingestion_result.warnings,
                "profile": profile.to_dict(),
                "issues": issues_with_confidence,
            }
            file_issues[file_path.name] = issues_with_confidence

            previous = find_previous_profile(settings.history_dir, file_path.name, exclude_run_id=request.run_id)
            if previous is None:
                drift_report = {"overall_status": "no_history", "compared_against": None, "findings": []}
            else:
                previous_run_id, previous_profile = previous
                report = detect_drift(profile, previous_profile)
                report.compared_against = previous_run_id
                drift_report = report.to_dict()
            file_drift[file_path.name] = drift_report
            all_drift_rows.append(
                {
                    "run_id": request.run_id,
                    "dataset": file_path.name,
                    "overall_status": drift_report["overall_status"],
                    "compared_against": drift_report["compared_against"],
                    "finding_count": len(drift_report["findings"]),
                }
            )

            save_profile_snapshot(settings.history_dir, file_path.name, request.run_id, profile)
        except IngestionError as exc:
            file_profiles[file_path.name] = {"status": "failed", "reason": exc.reason}
        except Exception:
            logger.exception("Unexpected error profiling %s", file_path)
            file_profiles[file_path.name] = {"status": "failed", "reason": "Could not analyze this file."}

    timestamp = datetime.now(timezone.utc).isoformat()
    result = {
        "run_id": request.run_id,
        "timestamp": timestamp,
        "files": file_profiles,
    }
    (run_dir / "profile.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

    issues_result = {
        "run_id": request.run_id,
        "timestamp": timestamp,
        "files": file_issues,
    }
    (run_dir / "issues.json").write_text(json.dumps(issues_result, indent=2, default=str), encoding="utf-8")

    drift_result = {
        "run_id": request.run_id,
        "timestamp": timestamp,
        "files": file_drift,
    }
    (run_dir / "drift_report.json").write_text(
        json.dumps(drift_result, indent=2, default=str), encoding="utf-8"
    )
    if all_drift_rows:
        append_rows_to_csv(
            settings.reports_dir / "drift_report.csv",
            all_drift_rows,
            columns=["run_id", "dataset", "overall_status", "compared_against", "finding_count"],
        )

    update_run_metadata(run_dir, status="profiled")
    record_processing_time(run_dir, "analyze", time.perf_counter() - start_time)

    return result


@router.get("/profile/{run_id}")
def get_profile(run_id: str) -> dict:
    settings = get_settings()
    try:
        run_dir = safe_join(settings.runs_dir, run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id.")

    profile_path = run_dir / "profile.json"
    if not profile_path.exists():
        raise HTTPException(status_code=404, detail=f"No profile found for run '{run_id}'. Run /api/analyze first.")

    return json.loads(profile_path.read_text(encoding="utf-8"))
