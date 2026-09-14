import hashlib
import json

from app.services.project_plan import parse_project_plan
from app.services.run_metadata import (
    accumulate_processing_time,
    compute_file_hash,
    derive_project_name,
    record_processing_time,
    update_run_metadata,
)


def test_compute_file_hash_matches_manual_sha256(tmp_path):
    path = tmp_path / "sample.csv"
    content = b"id,name\n1,Alice\n"
    path.write_bytes(content)

    assert compute_file_hash(path) == hashlib.sha256(content).hexdigest()


def test_update_run_metadata_preserves_untouched_top_level_fields(tmp_path):
    run_dir = tmp_path
    update_run_metadata(run_dir, run_id="run_1", status="uploaded")

    update_run_metadata(run_dir, status="profiled")

    metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["run_id"] == "run_1"  # preserved
    assert metadata["status"] == "profiled"  # updated
    assert "updated_at" in metadata


def test_update_run_metadata_deep_merges_per_file_updates_without_clobbering(tmp_path):
    run_dir = tmp_path
    update_run_metadata(run_dir, run_id="run_1", files={"data.csv": {"input_hash": "abc123"}})
    update_run_metadata(run_dir, files={"data.csv": {"output_hash": "def456"}})

    metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
    file_entry = metadata["files"]["data.csv"]
    assert file_entry["input_hash"] == "abc123"  # from first call, not clobbered
    assert file_entry["output_hash"] == "def456"  # from second call


def test_record_processing_time_accumulates_stages(tmp_path):
    run_dir = tmp_path
    update_run_metadata(run_dir, run_id="run_1")

    record_processing_time(run_dir, "upload", 0.05)
    record_processing_time(run_dir, "analyze", 0.12)

    metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["processing_time_seconds"]["upload"] == 0.05
    assert metadata["processing_time_seconds"]["analyze"] == 0.12


def test_accumulate_processing_time_adds_across_calls(tmp_path):
    run_dir = tmp_path
    update_run_metadata(run_dir, run_id="run_1")

    accumulate_processing_time(run_dir, "file_loading", 0.10)
    accumulate_processing_time(run_dir, "file_loading", 0.25)

    metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["processing_time_seconds"]["file_loading"] == 0.35


def test_accumulate_processing_time_does_not_affect_other_stages(tmp_path):
    run_dir = tmp_path
    update_run_metadata(run_dir, run_id="run_1")

    record_processing_time(run_dir, "analyze", 1.0)
    accumulate_processing_time(run_dir, "profiling", 0.2)

    metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["processing_time_seconds"]["analyze"] == 1.0
    assert metadata["processing_time_seconds"]["profiling"] == 0.2


def test_derive_project_name_from_objective():
    plan = parse_project_plan(
        "# Plan\n\n## Project Objective\nPrepare quarterly sales data for the West region revenue dashboard now.\n"
    )
    name = derive_project_name(plan)
    assert name == "Prepare quarterly sales data for the West region"


def test_derive_project_name_none_when_no_plan():
    assert derive_project_name(None) is None


def test_derive_project_name_none_when_no_objective():
    plan = parse_project_plan("# Plan\n\n## Required Columns\n- id\n")
    assert derive_project_name(plan) is None


def test_write_run_metadata_is_atomic_no_temp_file_left_behind(tmp_path):
    """write_run_metadata must write via a temp-file-then-replace so a crash mid-write
    can never leave run_metadata.json truncated/corrupt."""
    from app.services.run_metadata import write_run_metadata

    write_run_metadata(tmp_path, {"run_id": "run_1"})

    metadata_path = tmp_path / "run_metadata.json"
    assert metadata_path.exists()
    assert json.loads(metadata_path.read_text(encoding="utf-8"))["run_id"] == "run_1"
    # No leftover .tmp file from the atomic-write helper.
    assert list(tmp_path.glob("*.tmp")) == []


def test_read_run_metadata_recovers_from_corrupt_file_instead_of_raising(tmp_path):
    """A truncated/corrupt run_metadata.json (e.g. from an old crash, before the
    atomic-write fix existed) must degrade to an empty dict, not raise."""
    from app.services.run_metadata import read_run_metadata

    (tmp_path / "run_metadata.json").write_text('{"run_id": "run_1", "trunc', encoding="utf-8")

    assert read_run_metadata(tmp_path) == {}
