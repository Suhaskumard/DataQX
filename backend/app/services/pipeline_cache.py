"""Internal per-run cache for the profile/issue-detection pipeline (Phase 21 Performance).

`/api/analyze`, `/api/clean`, and `/api/validate` each independently re-derive
profile_dataset()+detect_issues() for the same raw file -- deliberate in earlier
phases to keep every endpoint stateless/independently callable, but a real, measured
cost for larger datasets (DATAQX.pdf S59: avoid repeated conversions). This cache lets
whichever endpoint runs first persist the result to disk (still file-based, no
database, no server memory/session state) so a later call in the same run reuses it;
an endpoint called standalone still falls back to a full recompute with identical
output -- this is a pure speed change, never a behavior change.

Deliberately separate from the public `profile.json`/`issues.json` artifacts (written
only by /api/analyze) so their existing GET-endpoint contracts (404 until /api/analyze
has run) are completely untouched. Stores only the *base* issue list -- before
/api/analyze layers in project-plan `check_required_columns()` issues -- so /api/clean
and /api/validate see exactly the issue set they compute today.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.services.issue_detection import Issue
from app.services.profiling import ColumnProfile, DatasetProfile

_CACHE_FILENAME = "_pipeline_cache.json"


def _cache_path(run_dir: Path) -> Path:
    return run_dir / _CACHE_FILENAME


def _file_fingerprint(file_path: Path) -> dict:
    """Cheap, no-read identity check for the raw input file (size + mtime)."""
    stat = file_path.stat()
    return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def load_cache_entry(run_dir: Path, file_path: Path) -> tuple[DatasetProfile, list[Issue]] | None:
    """Returns the cached (profile, issues) for `file_path`, or None on a cache miss.

    Defense-in-depth, not a currently-exploitable-through-the-API fix: every upload
    gets a fresh run_id today, so `data/input/<run_id>/<filename>` is immutable for
    the run's lifetime -- but this cache has no other integrity check of its own, and
    silently-wrong output is the worst possible failure mode for a data-quality
    product. A size/mtime mismatch against the file actually on disk invalidates the
    entry (treated as a miss) rather than trusting a bare filename match forever.
    """
    cache_path = _cache_path(run_dir)
    if not cache_path.exists():
        return None

    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    entry = cache.get(file_path.name)
    if entry is None:
        return None

    if entry.get("fingerprint") != _file_fingerprint(file_path):
        return None

    profile_dict = dict(entry["profile"])
    columns = [ColumnProfile(**col) for col in profile_dict.pop("columns")]
    profile = DatasetProfile(**profile_dict, columns=columns)

    issues = [
        Issue(
            issue_type=item["issue_type"],
            column=item["column"],
            severity=item["severity"],
            affected_count=item["affected_count"],
            description=item["description"],
            details=item.get("details", {}),
        )
        for item in entry["issues"]
    ]

    return profile, issues


def save_cache_entry(run_dir: Path, file_path: Path, profile: DatasetProfile, issues: list[Issue]) -> None:
    cache_path = _cache_path(run_dir)
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}

    cache[file_path.name] = {
        "fingerprint": _file_fingerprint(file_path),
        "profile": profile.to_dict(),
        "issues": [issue.to_dict() for issue in issues],
    }

    run_dir.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2, default=str), encoding="utf-8")
