"""Audit log retrieval endpoint. File-based -- reads
reports/runs/<run_id>/audit_log.csv (written by /api/clean) and returns it as
JSON rows so the frontend can filter/search it without re-parsing a CSV."""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.utils.filesystem import safe_join
from app.utils.json_safe import sanitize_for_json

router = APIRouter()


@router.get("/audit/{run_id}")
def get_audit(run_id: str) -> dict:
    settings = get_settings()
    try:
        run_dir = safe_join(settings.runs_dir, run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id.")

    audit_path = run_dir / "audit_log.csv"
    if not audit_path.exists():
        raise HTTPException(status_code=404, detail=f"No audit log found for run '{run_id}'. Run /api/clean first.")

    rows = pd.read_csv(audit_path).to_dict("records")
    return {"run_id": run_id, "rows": sanitize_for_json(rows)}
