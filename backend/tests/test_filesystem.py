from pathlib import Path

import pytest

from app.core.config import get_settings
from app.utils.filesystem import ensure_directories, generate_run_id, get_run_dir, safe_join


def test_ensure_directories_creates_expected_dirs_and_is_idempotent():
    settings = get_settings()
    ensure_directories()
    ensure_directories()  # must not raise the second time

    for directory in (
        settings.output_dir,
        settings.temp_dir,
        settings.runs_dir,
        settings.history_dir,
        settings.logs_dir,
        settings.config_dir,
    ):
        assert directory.exists()
        assert directory.is_dir()


def test_generate_run_id_is_unique_and_well_formed():
    run_id_a = generate_run_id()
    run_id_b = generate_run_id()

    assert run_id_a != run_id_b
    assert run_id_a.startswith("run_")
    # Expected shape: run_<YYYYMMDD>_<HHMMSS>_<8-char suffix>
    parts = run_id_a.split("_")
    assert len(parts) == 4
    assert parts[0] == "run"
    assert len(parts[1]) == 8 and parts[1].isdigit()  # YYYYMMDD
    assert len(parts[2]) == 6 and parts[2].isdigit()  # HHMMSS
    assert len(parts[3]) == 8


def test_get_run_dir_creates_expected_path():
    settings = get_settings()
    run_id = generate_run_id()
    run_dir = get_run_dir(run_id)

    assert run_dir == settings.runs_dir / run_id
    assert run_dir.exists()
    assert run_dir.is_dir()


def test_safe_join_allows_valid_relative_path(tmp_path: Path):
    result = safe_join(tmp_path, "subdir", "file.txt")
    assert result == (tmp_path / "subdir" / "file.txt").resolve()


def test_safe_join_rejects_path_traversal(tmp_path: Path):
    with pytest.raises(ValueError):
        safe_join(tmp_path, "..", "..", "etc", "passwd")
