"""Dataset + project plan upload endpoint.

Stateless: identity flows entirely through run_id and the filesystem. Raw uploaded
datasets are written under data/input/<run_id>/ -- a fresh directory per run, so an
upload can never overwrite a previous run's raw file (DATAQX.pdf S10).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile

from app.core.config import get_settings
from app.services.project_plan import parse_project_plan
from app.services.run_metadata import compute_file_hash, derive_project_name, record_processing_time, update_run_metadata
from app.utils.filesystem import generate_run_id, get_run_dir, safe_join, save_upload_stream
from app.utils.validation import UploadValidationError, sanitize_filename, validate_extension

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/upload")
async def upload_dataset(
    files: list[UploadFile] = File(...),
    project_plan_file: Optional[UploadFile] = File(None),
    project_plan_text: Optional[str] = Form(None),
) -> dict:
    start_time = time.perf_counter()
    settings = get_settings()
    run_id = generate_run_id()
    input_dir = safe_join(settings.input_dir, run_id)
    input_dir.mkdir(parents=True, exist_ok=True)
    run_dir = get_run_dir(run_id)

    max_size_bytes = settings.max_upload_size_mb * 1024 * 1024
    results = []
    metadata_files: dict[str, dict] = {}

    for upload in files:
        original_name = upload.filename or "unnamed"
        file_result = {"original_name": original_name}
        try:
            safe_name = sanitize_filename(original_name)
            validate_extension(safe_name)
            dest_path = safe_join(input_dir, safe_name)
            size_bytes = save_upload_stream(upload.file, dest_path, max_size_bytes)
            input_hash = compute_file_hash(dest_path)
            file_result.update(
                {
                    "status": "saved",
                    "saved_name": safe_name,
                    "size_bytes": size_bytes,
                    "path": str(dest_path.relative_to(settings.repo_root)),
                    "input_hash": input_hash,
                }
            )
            metadata_files[safe_name] = {"input_hash": input_hash, "output_hash": None, "status": "saved"}
        except UploadValidationError as exc:
            file_result.update({"status": "rejected", "reason": exc.reason})
            metadata_files[original_name] = {"input_hash": None, "output_hash": None, "status": "rejected"}
        except Exception:
            logger.exception("Unexpected error saving upload %s", original_name)
            file_result.update({"status": "rejected", "reason": "Could not process this file."})
            metadata_files[original_name] = {"input_hash": None, "output_hash": None, "status": "rejected"}
        finally:
            await upload.close()
        results.append(file_result)

    project_plan_result = None
    plan_text = project_plan_text
    if project_plan_file is not None:
        raw = await project_plan_file.read()
        try:
            plan_text = raw.decode("utf-8")
        except UnicodeDecodeError:
            project_plan_result = {"status": "rejected", "reason": "Project plan must be UTF-8 text."}
        await project_plan_file.close()

    if plan_text and project_plan_result is None:
        plan_path = run_dir / "project_plan.md"
        plan_path.write_text(plan_text, encoding="utf-8")
        project_plan_result = {"status": "saved", "path": str(plan_path.relative_to(settings.repo_root))}

    parsed_plan = parse_project_plan(plan_text) if (plan_text and project_plan_result and project_plan_result["status"] == "saved") else None

    response = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "uploaded",
        "files": results,
        "project_plan": project_plan_result,
    }

    update_run_metadata(
        run_dir,
        run_id=run_id,
        timestamp=response["timestamp"],
        status="uploaded",
        project_name=derive_project_name(parsed_plan),
        project_plan=project_plan_result,
        files=metadata_files,
        quality_score=None,
        powerbi_readiness=None,
    )
    record_processing_time(run_dir, "upload", time.perf_counter() - start_time)

    return response
