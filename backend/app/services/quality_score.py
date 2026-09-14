"""Data Quality Score (DATAQX.pdf S40).

Seven real, computed dimensions -- never an invented number (S63). Each dimension's
formula ships in the output (`methodology`) so the score is fully auditable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

from app.services.issue_detection import Issue
from app.services.profiling import DatasetProfile
from app.services.validation import ValidationReport

_VALIDATION_STATUS_SCORE = {"pass": 100.0, "warning": 80.0, "fail": 40.0}

METHODOLOGY = {
    "completeness": "100 - average missing_percentage across columns",
    "validity": "100 - (rows affected by impossible_value/invalid_date/mixed_data_types issues / total rows * 100)",
    "consistency": "100 - (rows affected by category_inconsistency/whitespace_formatting issues / total rows * 100)",
    "uniqueness": "100 - duplicate row percentage - duplicate ID percentage (if any ID column exists)",
    "integrity": "derived from the Validation Engine's overall status: pass=100, warning=80, fail=40",
    "schema_quality": "100 - 10 points per constant or fully-empty column",
    "analytics_readiness": "Phase 16's own computed Analytics Readiness overall score, reused directly",
}


@dataclass
class QualityScoreResult:
    overall_score: int
    dimensions: dict = field(default_factory=dict)
    methodology: dict = field(default_factory=lambda: dict(METHODOLOGY))

    def to_dict(self) -> dict:
        return asdict(self)


def _completeness(profile: DatasetProfile) -> float:
    if not profile.columns:
        return 100.0
    avg_missing = sum(c.missing_percentage for c in profile.columns) / len(profile.columns)
    return max(0.0, 100.0 - avg_missing)


def _affected_row_fraction(issues: list[Issue], issue_types: set[str], row_count: int) -> float:
    if row_count == 0:
        return 0.0
    affected = sum(i.affected_count for i in issues if i.issue_type in issue_types)
    return min(1.0, affected / row_count)


def _validity(issues: list[Issue], row_count: int) -> float:
    fraction = _affected_row_fraction(issues, {"impossible_value", "invalid_date", "mixed_data_types"}, row_count)
    return max(0.0, 100.0 - fraction * 100.0)


def _consistency(issues: list[Issue], row_count: int) -> float:
    fraction = _affected_row_fraction(issues, {"category_inconsistency", "whitespace_formatting"}, row_count)
    return max(0.0, 100.0 - fraction * 100.0)


def _uniqueness(df: pd.DataFrame, profile: DatasetProfile) -> float:
    row_count = len(df)
    if row_count == 0:
        return 100.0
    duplicate_row_pct = profile.duplicate_row_count / row_count * 100.0

    duplicate_id_pct = 0.0
    id_columns = [c for c in profile.columns if c.inferred_type == "id"]
    if id_columns:
        total_dup = 0
        for col in id_columns:
            total_dup += int(df[col.original_name].dropna().duplicated().sum())
        duplicate_id_pct = total_dup / row_count * 100.0

    return max(0.0, 100.0 - duplicate_row_pct - duplicate_id_pct)


def _integrity(validation_report: ValidationReport | None) -> float:
    if validation_report is None:
        return 100.0
    return _VALIDATION_STATUS_SCORE.get(validation_report.overall_status, 100.0)


def _schema_quality(profile: DatasetProfile) -> float:
    problem_columns = len(profile.constant_columns) + profile.empty_column_count
    return max(0.0, 100.0 - problem_columns * 10.0)


def compute_quality_score(
    df: pd.DataFrame,
    profile: DatasetProfile,
    issues: list[Issue],
    validation_report: ValidationReport | None,
    analytics_readiness_score: float,
) -> QualityScoreResult:
    dimensions = {
        "completeness": round(_completeness(profile), 2),
        "validity": round(_validity(issues, profile.row_count), 2),
        "consistency": round(_consistency(issues, profile.row_count), 2),
        "uniqueness": round(_uniqueness(df, profile), 2),
        "integrity": round(_integrity(validation_report), 2),
        "schema_quality": round(_schema_quality(profile), 2),
        "analytics_readiness": round(float(analytics_readiness_score), 2),
    }
    overall = round(sum(dimensions.values()) / len(dimensions))
    return QualityScoreResult(overall_score=overall, dimensions=dimensions)
