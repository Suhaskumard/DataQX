"""Generic per-run file download endpoint (named in DATAQX.pdf S52).

Serves a named artifact from either data/output/<run_id>/ (cleaned datasets) or
reports/runs/<run_id>/ (logs, reports, lineage, etc.) -- whichever actually contains
it. Uses the existing safe_join path-safety helper so a traversal attempt (e.g.
"../../secrets.txt") is rejected rather than resolved.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.utils.filesystem import safe_join

router = APIRouter()


@router.get("/download/{run_id}/{filename}")
def download_file(run_id: str, filename: str) -> FileResponse:
    settings = get_settings()

    for base_dir in (settings.output_dir, settings.runs_dir):
        try:
            run_subdir = safe_join(base_dir, run_id)
            candidate = safe_join(run_subdir, filename)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid run_id or filename.")

        if candidate.exists() and candidate.is_file():
            return FileResponse(candidate, filename=filename)

    raise HTTPException(
        status_code=404, detail=f"File '{filename}' not found for run '{run_id}'."
    )
