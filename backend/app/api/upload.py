"""Dataset + project plan upload endpoint.

Stateless: identity flows entirely through run_id and the filesystem. Raw uploaded
datasets are written under data/input/<run_id>/ -- a fresh directory per run, so an
upload can never overwrite a previous run's raw file (DATAQX.pdf S10).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile

from app.core.config import get_settings
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
    settings = get_settings()
    run_id = generate_run_id()
    input_dir = safe_join(settings.input_dir, run_id)
    input_dir.mkdir(parents=True, exist_ok=True)
    run_dir = get_run_dir(run_id)

    max_size_bytes = settings.max_upload_size_mb * 1024 * 1024
    results = []

    for upload in files:
        original_name = upload.filename or "unnamed"
        file_result = {"original_name": original_name}
        try:
            safe_name = sanitize_filename(original_name)
            validate_extension(safe_name)
            dest_path = safe_join(input_dir, safe_name)
            size_bytes = save_upload_stream(upload.file, dest_path, max_size_bytes)
            file_result.update(
                {
                    "status": "saved",
                    "saved_name": safe_name,
                    "size_bytes": size_bytes,
                    "path": str(dest_path.relative_to(settings.repo_root)),
                }
            )
        except UploadValidationError as exc:
            file_result.update({"status": "rejected", "reason": exc.reason})
        except Exception:
            logger.exception("Unexpected error saving upload %s", original_name)
            file_result.update({"status": "rejected", "reason": "Could not process this file."})
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

    run_metadata = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "uploaded",
        "files": results,
        "project_plan": project_plan_result,
    }
    (run_dir / "run_metadata.json").write_text(
        json.dumps(run_metadata, indent=2), encoding="utf-8"
    )

    return run_metadata
