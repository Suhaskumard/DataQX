"""Lineage retrieval endpoint. File-based -- reads reports/runs/<run_id>/data_lineage.json."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.utils.filesystem import safe_join

router = APIRouter()


@router.get("/lineage/{run_id}")
def get_lineage(run_id: str) -> dict:
    settings = get_settings()
    try:
        run_dir = safe_join(settings.runs_dir, run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id.")

    lineage_path = run_dir / "data_lineage.json"
    if not lineage_path.exists():
        raise HTTPException(status_code=404, detail=f"No lineage found for run '{run_id}'. Run /api/clean first.")

    return json.loads(lineage_path.read_text(encoding="utf-8"))
