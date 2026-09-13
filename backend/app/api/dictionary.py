"""Data dictionary retrieval endpoint. File-based -- reads
reports/runs/<run_id>/data_dictionary.csv.

Added during Phase 20: computed since Phase 17 (as a CSV, per S42), but never exposed
via a GET endpoint until the frontend needed one -- same gap pattern as Phase 19's
quality endpoint.
"""

from __future__ import annotations

import math

import pandas as pd
from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.utils.filesystem import safe_join

router = APIRouter()


def _clean_for_json(value):
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


@router.get("/dictionary/{run_id}")
def get_dictionary(run_id: str) -> dict:
    settings = get_settings()
    try:
        run_dir = safe_join(settings.runs_dir, run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id.")

    dictionary_path = run_dir / "data_dictionary.csv"
    if not dictionary_path.exists():
        raise HTTPException(
            status_code=404, detail=f"No data dictionary found for run '{run_id}'. Run /api/clean first."
        )

    df = pd.read_csv(dictionary_path)
    files: dict[str, list[dict]] = {}
    for dataset_name, group in df.groupby("dataset"):
        rows = group.drop(columns=["dataset"]).to_dict("records")
        files[dataset_name] = [{k: _clean_for_json(v) for k, v in row.items()} for row in rows]

    return {"run_id": run_id, "files": files}
