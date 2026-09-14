"""Looker Studio readiness (DATAQX Phase 16). Readiness assessment only --
never claims Google certification."""

from __future__ import annotations

import re

import pandas as pd

from app.services.issue_detection import Issue
from app.services.platform_rules.common import PlatformCheck, PlatformResult, build_result
from app.services.profiling import DatasetProfile
from app.services.semantic_roles import ColumnRole, columns_with_role

_CONNECTOR_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_ ]+$")


def evaluate(
    df: pd.DataFrame,
    profile: DatasetProfile,
    issues: list[Issue],
    roles: list[ColumnRole],
    relationship_check: PlatformCheck | None = None,
) -> PlatformResult:
    checks: list[PlatformCheck] = []
    recommendations: list[str] = []

    unsafe_headers = [c for c in df.columns if not _CONNECTOR_SAFE_NAME_RE.match(str(c))]
    checks.append(
        PlatformCheck(
            "connector_friendly_headers", "warning" if unsafe_headers else "pass",
            f"{len(unsafe_headers)} header(s) contain characters that can confuse the file-upload connector."
            if unsafe_headers else "All headers are connector-friendly.",
            {"columns": unsafe_headers},
        )
    )
    if unsafe_headers:
        recommendations.append("Simplify header names to letters, numbers, spaces and underscores for reliable connector field mapping.")

    mixed_type_issues = [i for i in issues if i.issue_type == "mixed_data_types"]
    checks.append(
        PlatformCheck(
            "primitive_data_types", "warning" if mixed_type_issues else "pass",
            f"{len(mixed_type_issues)} column(s) mix types; Looker Studio's auto-detected field type may be wrong."
            if mixed_type_issues else "All columns map cleanly to a single primitive type.",
            {"columns": [i.column for i in mixed_type_issues]},
        )
    )

    date_columns = columns_with_role(roles, "date_dimension")
    date_invalid_total = sum(c.date_extra.get("invalid_count", 0) for c in profile.columns if c.date_extra)
    checks.append(
        PlatformCheck(
            "date_fields", "warning" if date_invalid_total else ("pass" if date_columns else "not_applicable"),
            f"{date_invalid_total} invalid date value(s) found." if date_invalid_total
            else (f"Date field(s) available: {date_columns}." if date_columns else "No date field present."),
            {"columns": date_columns},
        )
    )

    numeric_columns = columns_with_role(roles, "measure")
    checks.append(
        PlatformCheck(
            "numeric_fields", "pass" if numeric_columns else "warning",
            f"Numeric field(s) available for metrics: {numeric_columns}." if numeric_columns
            else "No numeric fields available to use as a Looker Studio metric.",
            {"columns": numeric_columns},
        )
    )

    categorical_columns = columns_with_role(roles, "dimension_attribute")
    checks.append(
        PlatformCheck(
            "categorical_fields", "pass" if categorical_columns else "warning",
            f"Categorical field(s) available for dimensions: {categorical_columns}." if categorical_columns
            else "No categorical fields available for dimension breakdowns.",
            {"columns": categorical_columns},
        )
    )

    avg_missing = sum(c.missing_percentage for c in profile.columns) / len(profile.columns) if profile.columns else 0.0
    checks.append(
        PlatformCheck(
            "missing_values", "warning" if avg_missing > 10.0 else "pass",
            f"Average missingness across columns is {avg_missing:.1f}%.",
            {"average_missing_percentage": round(avg_missing, 2)},
        )
    )

    checks.append(
        PlatformCheck(
            "aggregation_usability", "pass" if numeric_columns else "warning",
            "At least one metric field can be summed/averaged." if numeric_columns
            else "No metric field is available for default aggregation.",
        )
    )

    field_roles = {col: "Metric" for col in numeric_columns}
    field_roles.update({col: "Dimension" for col in categorical_columns})
    field_roles.update({col: "Date Dimension" for col in date_columns})

    return build_result(
        "Looker Studio", checks, field_roles=field_roles,
        recommendations=recommendations,
        export_recommendations=["CSV (Google Sheets or file-upload connector)"],
    )
