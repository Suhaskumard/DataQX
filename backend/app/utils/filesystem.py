"""Filesystem utilities for DataQX.

All state is file-based. There is no database. Run identity flows through a run_id and
a per-run directory under reports/runs/, not server-side session state.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

from app.core.config import get_settings
from app.utils.validation import UploadValidationError

_CHUNK_SIZE = 1024 * 1024  # 1 MB


def ensure_directories() -> None:
    """Create the runtime processing/output/log directories if missing.

    Does not touch data/input or data/samples -- those hold user-provided data and are
    never created/modified by the backend on its own.
    """
    settings = get_settings()
    for directory in (
        settings.output_dir,
        settings.temp_dir,
        settings.runs_dir,
        settings.history_dir,
        settings.logs_dir,
        settings.config_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def generate_run_id() -> str:
    """Generate a sortable, unique run id: run_<UTC timestamp>_<short uuid>."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    return f"run_{timestamp}_{suffix}"


def get_run_dir(run_id: str) -> Path:
    """Return (and create) the per-run artifact directory for the given run_id."""
    settings = get_settings()
    run_dir = settings.runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def safe_join(base: Path, *parts: str) -> Path:
    """Join path parts onto base, rejecting any result that escapes base.

    Raises ValueError on path traversal attempts (e.g. "..", absolute paths).
    """
    base_resolved = base.resolve()
    candidate = base_resolved.joinpath(*parts).resolve()
    if candidate != base_resolved and base_resolved not in candidate.parents:
        raise ValueError(f"Unsafe path outside of base directory: {parts!r}")
    return candidate


def save_upload_stream(source: BinaryIO, dest_path: Path, max_size_bytes: int) -> int:
    """Write an uploaded file's contents to dest_path in chunks.

    Aborts (deletes the partial file) and raises UploadValidationError if the file is
    empty or exceeds max_size_bytes, so an oversized upload never fully lands on disk.
    Returns the number of bytes written on success.
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    try:
        with open(dest_path, "wb") as out:
            while True:
                chunk = source.read(_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_size_bytes:
                    raise UploadValidationError(
                        f"File exceeds the maximum allowed size of {max_size_bytes} bytes."
                    )
                out.write(chunk)
    except UploadValidationError:
        dest_path.unlink(missing_ok=True)
        raise

    if total == 0:
        dest_path.unlink(missing_ok=True)
        raise UploadValidationError("File is empty.")

    return total
