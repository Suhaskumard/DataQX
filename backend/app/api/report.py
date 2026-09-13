"""PDF report endpoint. Assembles DataQX_Report.pdf from already-persisted per-run
artifacts (see app.services.pdf_report) -- does not re-run the pipeline."""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Response

from app.core.config import get_settings
from app.services.pdf_report import generate_pdf_report
from app.services.performance_logging import identify_bottleneck, log_stage
from app.services.run_metadata import accumulate_processing_time, read_run_metadata, update_run_metadata
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

    stage_start = time.perf_counter()
    pdf_bytes = generate_pdf_report(run_dir, run_id)
    pdf_generation_seconds = time.perf_counter() - stage_start
    (run_dir / "DataQX_Report.pdf").write_bytes(pdf_bytes)

    accumulate_processing_time(run_dir, "pdf_generation", pdf_generation_seconds)
    log_stage(settings.logs_dir, run_id, "pdf_generation", pdf_generation_seconds)

    metadata = read_run_metadata(run_dir)
    all_times = metadata.get("processing_time_seconds", {})
    sub_stage_times = {k: v for k, v in all_times.items() if k not in ("upload", "analyze", "clean", "validate")}
    bottleneck = identify_bottleneck(sub_stage_times)
    if bottleneck is not None:
        update_run_metadata(run_dir, bottleneck_stage=bottleneck["stage"], bottleneck_seconds=bottleneck["seconds"])

    return Response(content=pdf_bytes, media_type="application/pdf")
