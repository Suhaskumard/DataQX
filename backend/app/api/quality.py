"""Quality score retrieval endpoint. File-based -- reads
reports/runs/<run_id>/quality_report.json.

Added during Phase 19 (Dashboard Integration): every other artifact (issues, lineage,
drift, Power BI readiness) already had a matching GET endpoint since the phase that
produced it; quality_report.json (Phase 17) was a real, if minor, gap -- the frontend
dashboard needs a way to fetch it, same as everything else.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.utils.filesystem import safe_join

router = APIRouter()


@router.get("/quality/{run_id}")
def get_quality(run_id: str) -> dict:
    settings = get_settings()
    try:
        run_dir = safe_join(settings.runs_dir, run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id.")

    quality_path = run_dir / "quality_report.json"
    if not quality_path.exists():
        raise HTTPException(
            status_code=404, detail=f"No quality report found for run '{run_id}'. Run /api/clean first."
        )

    return json.loads(quality_path.read_text(encoding="utf-8"))
