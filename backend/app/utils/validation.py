"""Upload validation helpers.

Extension allow-listing only -- actual file content/format parsing is Phase 4
(Multi-Format Ingestion). Filename sanitization guards against path traversal and
unsafe characters before anything touches the filesystem.
"""

from __future__ import annotations

import re
from pathlib import Path

ALLOWED_DATASET_EXTENSIONS = {
    ".csv",
    ".tsv",
    ".txt",
    ".xlsx",
    ".xls",
    ".json",
    ".parquet",
    ".xml",
    ".feather",
}

_SAFE_CHARS_RE = re.compile(r"[^A-Za-z0-9._-]")


class UploadValidationError(Exception):
    """Raised for a friendly, user-facing upload rejection reason."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def sanitize_filename(raw_name: str) -> str:
    """Strip any directory components and unsafe characters from an uploaded filename.

    Never trust a client-supplied filename as a path. Path.name discards any
    directory portion (including "../" traversal attempts); the remaining
    characters are then restricted to a safe set.
    """
    name = Path(raw_name or "").name
    if not name or name in (".", ".."):
        raise UploadValidationError("Filename is missing or invalid.")

    stem = Path(name).stem
    suffix = Path(name).suffix

    safe_stem = _SAFE_CHARS_RE.sub("_", stem).strip("._") or "file"
    safe_suffix = _SAFE_CHARS_RE.sub("", suffix)

    return f"{safe_stem}{safe_suffix}"


def validate_extension(filename: str) -> None:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_DATASET_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_DATASET_EXTENSIONS))
        raise UploadValidationError(
            f"Unsupported file type '{ext or '(none)'}'. Allowed types: {allowed}."
        )
