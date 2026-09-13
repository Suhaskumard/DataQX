"""Analyze endpoint: loads a run's raw file(s) and computes their profile.

File-based only: reads from data/input/<run_id>/, writes to reports/runs/<run_id>/.
No database, no server-side session state -- every request is scoped by run_id.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.services.ingestion import IngestionError, load_dataset
from app.services.issue_detection import detect_issues
from app.services.profiling import profile_dataset
from app.utils.filesystem import get_run_dir, safe_join

router = APIRouter()
logger = logging.getLogger(__name__)


class AnalyzeRequest(BaseModel):
    run_id: str


@router.post("/analyze")
def analyze_run(request: AnalyzeRequest) -> dict:
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

    file_profiles: dict[str, dict] = {}
    file_issues: dict[str, list] = {}
    for file_path in raw_files:
        try:
            ingestion_result = load_dataset(file_path)
            profile = profile_dataset(ingestion_result.dataframe, source_path=file_path)
            issues = detect_issues(ingestion_result.dataframe, profile)
            file_profiles[file_path.name] = {
                "status": "profiled",
                "detected_format": ingestion_result.detected_format,
                "ingestion_warnings": ingestion_result.warnings,
                "profile": profile.to_dict(),
                "issues": [issue.to_dict() for issue in issues],
            }
            file_issues[file_path.name] = [issue.to_dict() for issue in issues]
        except IngestionError as exc:
            file_profiles[file_path.name] = {"status": "failed", "reason": exc.reason}
        except Exception:
            logger.exception("Unexpected error profiling %s", file_path)
            file_profiles[file_path.name] = {"status": "failed", "reason": "Could not analyze this file."}

    run_dir = get_run_dir(request.run_id)
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

    metadata_path = run_dir / "run_metadata.json"
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["status"] = "profiled"
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

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
