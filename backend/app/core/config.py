"""Runtime configuration for DataQX backend.

No database configuration exists here or anywhere in this project. All paths point at
plain filesystem directories used for temporary processing and generated artifacts.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


# Repo root = two levels up from this file (backend/app/core/config.py -> backend/app -> backend -> repo root)
REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    app_name: str = "DataQX"
    app_version: str = "0.1.0"
    environment: str = field(default_factory=lambda: os.environ.get("DATAQX_ENV", "development"))

    repo_root: Path = REPO_ROOT

    data_dir: Path = REPO_ROOT / "data"
    input_dir: Path = REPO_ROOT / "data" / "input"
    output_dir: Path = REPO_ROOT / "data" / "output"
    temp_dir: Path = REPO_ROOT / "data" / "temp"
    samples_dir: Path = REPO_ROOT / "data" / "samples"

    reports_dir: Path = REPO_ROOT / "reports"
    runs_dir: Path = REPO_ROOT / "reports" / "runs"
    history_dir: Path = REPO_ROOT / "reports" / "history"

    logs_dir: Path = REPO_ROOT / "logs"
    config_dir: Path = REPO_ROOT / "config"

    max_upload_size_mb: int = field(default_factory=lambda: int(os.environ.get("DATAQX_MAX_UPLOAD_MB", "200")))


def get_settings() -> Settings:
    return Settings()
