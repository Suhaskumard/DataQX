"""Analytics readiness retrieval endpoint. File-based -- reads
reports/runs/<run_id>/analytics_readiness.json. Supersedes the old
Power-BI-only /api/powerbi endpoint; Power BI is now one of several platforms
evaluated (see app.services.analytics_readiness)."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.utils.filesystem import safe_join

router = APIRouter()


@router.get("/analytics-readiness/{run_id}")
def get_analytics_readiness(run_id: str) -> dict:
    settings = get_settings()
    try:
        run_dir = safe_join(settings.runs_dir, run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id.")

    readiness_path = run_dir / "analytics_readiness.json"
    if not readiness_path.exists():
        raise HTTPException(
            status_code=404, detail=f"No analytics readiness report found for run '{run_id}'. Run /api/analyze first."
        )

    return json.loads(readiness_path.read_text(encoding="utf-8"))
