"""Performance endpoint: exposes a run's measured stage timings and bottleneck
(DATAQX.pdf S57/S58). Reads run_metadata.json -- no re-computation, no database."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.services.run_metadata import read_run_metadata
from app.utils.filesystem import safe_join

router = APIRouter()


@router.get("/performance/{run_id}")
def get_performance(run_id: str) -> dict:
    settings = get_settings()
    try:
        run_dir = safe_join(settings.runs_dir, run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id.")

    metadata_path = run_dir / "run_metadata.json"
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail=f"No run metadata found for run '{run_id}'.")

    metadata = read_run_metadata(run_dir)
    return {
        "run_id": run_id,
        "processing_time_seconds": metadata.get("processing_time_seconds", {}),
        "bottleneck_stage": metadata.get("bottleneck_stage"),
        "bottleneck_seconds": metadata.get("bottleneck_seconds"),
    }
