"""Data Drift (DATAQX.pdf S35).

Compares a run's current profile against previously saved profile snapshots. File-
based only -- no database. Successive uploads sharing a filename are treated as
successive versions of the same dataset, since there's no database to track dataset
identity across runs; this is the only stateless signal available.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.services.profiling import ColumnProfile, DatasetProfile

_MISSINGNESS_DRIFT_THRESHOLD_POINTS = 10.0
_VOLUME_DRIFT_RELATIVE_THRESHOLD = 0.2
_DISTRIBUTION_DRIFT_RELATIVE_THRESHOLD = 0.2

_SAFE_NAME_RE = re.compile(r"[^0-9a-zA-Z]+")


def _sanitize_dataset_name(name: str) -> str:
    return _SAFE_NAME_RE.sub("_", Path(name).stem).strip("_").lower() or "dataset"


@dataclass
class DriftFinding:
    drift_type: str
    column: str | None
    severity: str
    description: str
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DriftReport:
    overall_status: str  # no_history | no_drift | drift_detected
    compared_against: str | None
    findings: list[DriftFinding] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "overall_status": self.overall_status,
            "compared_against": self.compared_against,
            "findings": [f.to_dict() for f in self.findings],
        }


def _profile_to_dict(profile: DatasetProfile) -> dict:
    return profile.to_dict()


def _profile_from_dict(data: dict) -> DatasetProfile:
    columns = [ColumnProfile(**col) for col in data["columns"]]
    return DatasetProfile(
        row_count=data["row_count"],
        column_count=data["column_count"],
        file_size_bytes=data["file_size_bytes"],
        memory_usage_bytes=data["memory_usage_bytes"],
        duplicate_row_count=data["duplicate_row_count"],
        empty_row_count=data["empty_row_count"],
        empty_column_count=data["empty_column_count"],
        constant_columns=data["constant_columns"],
        near_constant_columns=data["near_constant_columns"],
        dataset_hash=data["dataset_hash"],
        columns=columns,
    )


def save_profile_snapshot(history_dir: Path, dataset_name: str, run_id: str, profile: DatasetProfile) -> Path:
    dataset_dir = history_dir / _sanitize_dataset_name(dataset_name)
    dataset_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = dataset_dir / f"profile_{run_id}.json"
    snapshot_path.write_text(json.dumps(_profile_to_dict(profile), indent=2, default=str), encoding="utf-8")
    return snapshot_path


def find_previous_profile(
    history_dir: Path, dataset_name: str, exclude_run_id: str
) -> tuple[str, DatasetProfile] | None:
    dataset_dir = history_dir / _sanitize_dataset_name(dataset_name)
    if not dataset_dir.exists():
        return None

    snapshots = sorted(
        (p for p in dataset_dir.glob("profile_*.json") if f"profile_{exclude_run_id}.json" != p.name),
    )
    if not snapshots:
        return None

    latest = snapshots[-1]
    run_id = latest.stem.removeprefix("profile_")
    data = json.loads(latest.read_text(encoding="utf-8"))
    return run_id, _profile_from_dict(data)


def _column_map(profile: DatasetProfile) -> dict[str, ColumnProfile]:
    return {c.original_name: c for c in profile.columns}


def detect_drift(current: DatasetProfile, previous: DatasetProfile) -> DriftReport:
    findings: list[DriftFinding] = []

    current_cols = _column_map(current)
    previous_cols = _column_map(previous)

    new_columns = sorted(set(current_cols) - set(previous_cols))
    removed_columns = sorted(set(previous_cols) - set(current_cols))
    common_columns = sorted(set(current_cols) & set(previous_cols))

    if new_columns:
        findings.append(
            DriftFinding(
                drift_type="schema_drift_new_columns",
                column=None,
                severity="medium",
                description=f"New column(s) appeared: {new_columns}.",
                details={"new_columns": new_columns},
            )
        )
    if removed_columns:
        findings.append(
            DriftFinding(
                drift_type="schema_drift_removed_columns",
                column=None,
                severity="high",
                description=f"Column(s) removed: {removed_columns}.",
                details={"removed_columns": removed_columns},
            )
        )

    for col in common_columns:
        if current_cols[col].inferred_type != previous_cols[col].inferred_type:
            findings.append(
                DriftFinding(
                    drift_type="schema_drift_type_change",
                    column=col,
                    severity="medium",
                    description=f"Column '{col}' type changed from '{previous_cols[col].inferred_type}' to '{current_cols[col].inferred_type}'.",
                    details={"previous_type": previous_cols[col].inferred_type, "current_type": current_cols[col].inferred_type},
                )
            )

    if previous.row_count > 0:
        relative_change = abs(current.row_count - previous.row_count) / previous.row_count
        if relative_change > _VOLUME_DRIFT_RELATIVE_THRESHOLD:
            findings.append(
                DriftFinding(
                    drift_type="volume_drift",
                    column=None,
                    severity="medium",
                    description=f"Row count changed from {previous.row_count} to {current.row_count} ({relative_change:.1%}).",
                    details={"previous_row_count": previous.row_count, "current_row_count": current.row_count},
                )
            )

    for col in common_columns:
        missing_delta = current_cols[col].missing_percentage - previous_cols[col].missing_percentage
        if missing_delta > _MISSINGNESS_DRIFT_THRESHOLD_POINTS:
            findings.append(
                DriftFinding(
                    drift_type="missingness_drift",
                    column=col,
                    severity="high",
                    description=f"Column '{col}' missingness increased from {previous_cols[col].missing_percentage:.1f}% to {current_cols[col].missing_percentage:.1f}%.",
                    details={
                        "previous_missing_percentage": previous_cols[col].missing_percentage,
                        "current_missing_percentage": current_cols[col].missing_percentage,
                    },
                )
            )

    for col in common_columns:
        cur_extra = current_cols[col].categorical_extra
        prev_extra = previous_cols[col].categorical_extra
        if cur_extra and prev_extra:
            cur_categories = {c["value"] for c in cur_extra.get("top_categories", [])}
            prev_categories = {c["value"] for c in prev_extra.get("top_categories", [])}
            new_categories = sorted(cur_categories - prev_categories)
            removed_categories = sorted(prev_categories - cur_categories)
            if new_categories or removed_categories:
                findings.append(
                    DriftFinding(
                        drift_type="category_drift",
                        column=col,
                        severity="low",
                        description=f"Column '{col}' categories changed (new: {new_categories}, removed: {removed_categories}).",
                        details={"new_categories": new_categories, "removed_categories": removed_categories},
                    )
                )

    for col in common_columns:
        cur_mean, prev_mean = current_cols[col].mean, previous_cols[col].mean
        cur_std, prev_std = current_cols[col].std, previous_cols[col].std
        if cur_mean is not None and prev_mean is not None and prev_mean != 0:
            mean_relative_change = abs(cur_mean - prev_mean) / abs(prev_mean)
            if mean_relative_change > _DISTRIBUTION_DRIFT_RELATIVE_THRESHOLD:
                findings.append(
                    DriftFinding(
                        drift_type="distribution_drift_mean",
                        column=col,
                        severity="medium",
                        description=f"Column '{col}' mean shifted from {prev_mean:.2f} to {cur_mean:.2f} ({mean_relative_change:.1%}).",
                        details={"previous_mean": prev_mean, "current_mean": cur_mean},
                    )
                )
        if cur_std is not None and prev_std is not None and prev_std != 0:
            std_relative_change = abs(cur_std - prev_std) / abs(prev_std)
            if std_relative_change > _DISTRIBUTION_DRIFT_RELATIVE_THRESHOLD:
                findings.append(
                    DriftFinding(
                        drift_type="distribution_drift_std",
                        column=col,
                        severity="low",
                        description=f"Column '{col}' standard deviation shifted from {prev_std:.2f} to {cur_std:.2f} ({std_relative_change:.1%}).",
                        details={"previous_std": prev_std, "current_std": cur_std},
                    )
                )

    overall_status = "drift_detected" if findings else "no_drift"
    return DriftReport(overall_status=overall_status, compared_against=None, findings=findings)
