"""Issues retrieval endpoint. File-based -- reads reports/runs/<run_id>/issues.json."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.utils.filesystem import safe_join

router = APIRouter()


@router.get("/issues/{run_id}")
def get_issues(run_id: str) -> dict:
    settings = get_settings()
    try:
        run_dir = safe_join(settings.runs_dir, run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id.")

    issues_path = run_dir / "issues.json"
    if not issues_path.exists():
        raise HTTPException(status_code=404, detail=f"No issues found for run '{run_id}'. Run /api/analyze first.")

    return json.loads(issues_path.read_text(encoding="utf-8"))
