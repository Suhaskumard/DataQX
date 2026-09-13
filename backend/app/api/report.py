"""PDF report endpoint. Assembles DataQX_Report.pdf from already-persisted per-run
artifacts (see app.services.pdf_report) -- does not re-run the pipeline."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from app.core.config import get_settings
from app.services.pdf_report import generate_pdf_report
from app.utils.filesystem import safe_join

router = APIRouter()


@router.get("/report/{run_id}")
def get_report(run_id: str) -> Response:
    settings = get_settings()
    try:
        run_dir = safe_join(settings.runs_dir, run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id.")

    if not (run_dir / "profile.json").exists():
        raise HTTPException(
            status_code=404, detail=f"No analysis found for run '{run_id}'. Run /api/analyze first."
        )

    pdf_bytes = generate_pdf_report(run_dir, run_id)
    (run_dir / "DataQX_Report.pdf").write_bytes(pdf_bytes)

    return Response(content=pdf_bytes, media_type="application/pdf")
