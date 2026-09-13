"""Before/after summary retrieval endpoint. File-based -- reads
reports/runs/<run_id>/before_after_summary.json.

Added during Phase 20: computed since Phase 17, but never exposed via a GET endpoint
until the frontend needed one -- same gap pattern as Phase 19's quality endpoint.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.utils.filesystem import safe_join

router = APIRouter()


@router.get("/before-after/{run_id}")
def get_before_after(run_id: str) -> dict:
    settings = get_settings()
    try:
        run_dir = safe_join(settings.runs_dir, run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id.")

    summary_path = run_dir / "before_after_summary.json"
    if not summary_path.exists():
        raise HTTPException(
            status_code=404, detail=f"No before/after summary found for run '{run_id}'. Run /api/clean first."
        )

    return json.loads(summary_path.read_text(encoding="utf-8"))
