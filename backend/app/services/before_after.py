"""Before/After Comparison (DATAQX.pdf S41).

Compares real, already-computed before/after metrics -- nothing estimated.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.services.issue_detection import Issue
from app.services.profiling import DatasetProfile

BEFORE_AFTER_METRICS = (
    "row_count",
    "column_count",
    "missing_values",
    "duplicate_rows",
    "duplicate_ids",
    "invalid_values",
    "invalid_dates",
    "outliers",
    "quality_score",
    "analytics_readiness",
)


@dataclass
class SnapshotMetrics:
    row_count: int
    column_count: int
    missing_values: int
    duplicate_rows: int
    duplicate_ids: int
    invalid_values: int
    invalid_dates: int
    outliers: int
    quality_score: float
    analytics_readiness: float


def build_snapshot_metrics(
    df: pd.DataFrame,
    profile: DatasetProfile,
    issues: list[Issue],
    quality_score: float,
    analytics_readiness: float,
) -> SnapshotMetrics:
    duplicate_ids = 0
    for col in profile.columns:
        if col.inferred_type == "id":
            duplicate_ids += int(df[col.original_name].dropna().duplicated().sum())

    def _affected(issue_types: set[str]) -> int:
        return sum(i.affected_count for i in issues if i.issue_type in issue_types)

    return SnapshotMetrics(
        row_count=profile.row_count,
        column_count=profile.column_count,
        missing_values=sum(c.missing_count for c in profile.columns),
        duplicate_rows=profile.duplicate_row_count,
        duplicate_ids=duplicate_ids,
        invalid_values=_affected({"impossible_value", "negative_value", "mixed_data_types"}),
        invalid_dates=_affected({"invalid_date"}),
        outliers=_affected({"outlier"}),
        quality_score=quality_score,
        analytics_readiness=analytics_readiness,
    )


def build_before_after_summary(before: SnapshotMetrics, after: SnapshotMetrics) -> dict:
    summary = {}
    for metric in BEFORE_AFTER_METRICS:
        before_value = getattr(before, metric)
        after_value = getattr(after, metric)
        summary[metric] = {
            "before": before_value,
            "after": after_value,
            "change": after_value - before_value,
        }
    return summary
