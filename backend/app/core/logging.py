"""Logging setup for DataQX backend.

Console gets INFO+ for normal operation visibility. logs/errors.log gets WARNING+ so
technical stack traces never reach normal users (see DATAQX.pdf S56) but are always
captured on disk. File-based only -- no database-backed logging.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.core.config import get_settings

_CONFIGURED = False


def setup_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings = get_settings()
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    error_log_path: Path = settings.logs_dir / "errors.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(fmt)

    file_handler = logging.FileHandler(error_log_path, encoding="utf-8")
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(fmt)

    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    _CONFIGURED = True
