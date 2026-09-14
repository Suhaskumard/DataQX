from pathlib import Path

from app.services.issue_detection import Issue
from app.services.pipeline_cache import load_cache_entry, save_cache_entry
from app.services.profiling import ColumnProfile, DatasetProfile


def _sample_profile() -> DatasetProfile:
    return DatasetProfile(
        row_count=3,
        column_count=1,
        file_size_bytes=52,
        memory_usage_bytes=128,
        duplicate_row_count=0,
        empty_row_count=0,
        empty_column_count=0,
        constant_columns=[],
        near_constant_columns=[],
        dataset_hash="abc123",
        columns=[
            ColumnProfile(
                original_name="name",
                clean_name="name",
                dtype="object",
                inferred_type="string",
                missing_count=0,
                missing_percentage=0.0,
                unique_count=3,
                unique_percentage=100.0,
                example_values=["Alice", "Bob", "Carol"],
            )
        ],
    )


def _sample_issues() -> list[Issue]:
    return [
        Issue(
            issue_type="whitespace_formatting",
            column="name",
            severity="low",
            affected_count=2,
            description="Leading/trailing whitespace.",
            details={"example": "Alice "},
        )
    ]


def _real_file(tmp_path: Path, name: str, content: bytes = b"a,name\n1,Alice\n") -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


def test_cache_miss_returns_none(tmp_path):
    assert load_cache_entry(tmp_path, tmp_path / "data.csv") is None


def test_save_then_load_round_trips_profile_and_issues(tmp_path):
    profile = _sample_profile()
    issues = _sample_issues()
    file_path = _real_file(tmp_path, "data.csv")

    save_cache_entry(tmp_path, file_path, profile, issues)
    loaded = load_cache_entry(tmp_path, file_path)

    assert loaded is not None
    loaded_profile, loaded_issues = loaded
    assert loaded_profile == profile
    assert loaded_issues == issues


def test_cache_is_scoped_per_filename(tmp_path):
    file_a = _real_file(tmp_path, "a.csv")
    file_b = _real_file(tmp_path, "b.csv")
    save_cache_entry(tmp_path, file_a, _sample_profile(), _sample_issues())

    assert load_cache_entry(tmp_path, file_b) is None
    assert load_cache_entry(tmp_path, file_a) is not None


def test_save_cache_entry_merges_multiple_files(tmp_path):
    file_a = _real_file(tmp_path, "a.csv")
    file_b = _real_file(tmp_path, "b.csv")
    save_cache_entry(tmp_path, file_a, _sample_profile(), _sample_issues())
    save_cache_entry(tmp_path, file_b, _sample_profile(), [])

    assert load_cache_entry(tmp_path, file_a) is not None
    loaded_b = load_cache_entry(tmp_path, file_b)
    assert loaded_b is not None
    assert loaded_b[1] == []


def test_cache_invalidated_when_underlying_file_content_changes(tmp_path):
    """Phase 25 hardening: the cache must not blindly trust a bare filename match --
    if the file on disk changes (different size/mtime) after a cache entry was saved,
    the stale entry must be treated as a miss, never served as if still valid."""
    file_path = _real_file(tmp_path, "data.csv", b"a,name\n1,Alice\n")
    save_cache_entry(tmp_path, file_path, _sample_profile(), _sample_issues())
    assert load_cache_entry(tmp_path, file_path) is not None

    # Simulate the file changing after the cache entry was written (different size).
    file_path.write_bytes(b"a,name\n1,Alice\n2,Bob\n3,Carol\n")

    assert load_cache_entry(tmp_path, file_path) is None
