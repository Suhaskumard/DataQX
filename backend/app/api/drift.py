"""Drift retrieval endpoint. File-based -- reads reports/runs/<run_id>/drift_report.json."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.utils.filesystem import safe_join

router = APIRouter()


@router.get("/drift/{run_id}")
def get_drift(run_id: str) -> dict:
    settings = get_settings()
    try:
        run_dir = safe_join(settings.runs_dir, run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id.")

    drift_path = run_dir / "drift_report.json"
    if not drift_path.exists():
        raise HTTPException(status_code=404, detail=f"No drift report found for run '{run_id}'. Run /api/analyze first.")

    return json.loads(drift_path.read_text(encoding="utf-8"))
