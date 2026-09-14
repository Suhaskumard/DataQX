"""Looker readiness (DATAQX Phase 16). Readiness assessment only."""

from __future__ import annotations

import re

import pandas as pd

from app.services.issue_detection import Issue
from app.services.platform_rules.common import PlatformCheck, PlatformResult, build_result
from app.services.profiling import DatasetProfile
from app.services.semantic_roles import ColumnRole, columns_with_role

_NAME_STYLE_RE = re.compile(r"^[a-z0-9_]+$")


def evaluate(
    df: pd.DataFrame,
    profile: DatasetProfile,
    issues: list[Issue],
    roles: list[ColumnRole],
    relationship_check: PlatformCheck | None = None,
) -> PlatformResult:
    checks: list[PlatformCheck] = []
    recommendations: list[str] = []

    measure_columns = columns_with_role(roles, "measure")
    checks.append(
        PlatformCheck(
            "potential_measures", "pass" if measure_columns else "warning",
            f"{len(measure_columns)} potential measure column(s) for LookML measures." if measure_columns
            else "No numeric columns available to define LookML measures.",
            {"columns": measure_columns},
        )
    )

    dimension_columns = columns_with_role(roles, "dimension_attribute")
    key_columns = columns_with_role(roles, "primary_key")
    checks.append(
        PlatformCheck(
            "potential_dimensions", "pass" if dimension_columns else "warning",
            f"{len(dimension_columns)} potential dimension column(s) for LookML dimensions." if dimension_columns
            else "No categorical columns available to define LookML dimensions.",
            {"columns": dimension_columns},
        )
    )

    checks.append(
        PlatformCheck(
            "potential_keys", "pass" if key_columns else "warning",
            f"Potential primary key(s): {key_columns}." if key_columns else "No obvious primary key column found.",
            {"columns": key_columns},
        )
    )

    duplicate_row_issues = [i for i in issues if i.issue_type == "duplicate_rows"]
    if duplicate_row_issues:
        checks.append(
            PlatformCheck(
                "grain_concern", "warning",
                f"{sum(i.affected_count for i in duplicate_row_issues)} duplicate row(s) suggest the table's grain is ambiguous.",
            )
        )
        recommendations.append("Grain Concern: deduplicate rows so each row represents exactly one fact at a known grain.")
    else:
        checks.append(PlatformCheck("grain_concern", "pass", "No duplicate rows; grain appears well-defined."))

    if relationship_check is not None:
        relationship_concern = PlatformCheck(
            "relationship_concern", relationship_check.status, relationship_check.message, relationship_check.details
        )
        checks.append(relationship_concern)

    inconsistent_names = [c for c in df.columns if not _NAME_STYLE_RE.match(str(c))]
    checks.append(
        PlatformCheck(
            "naming_consistency", "warning" if inconsistent_names else "pass",
            f"{len(inconsistent_names)} field name(s) don't follow snake_case, which LookML conventionally expects."
            if inconsistent_names else "Field names are consistently snake_case.",
            {"columns": inconsistent_names},
        )
    )

    high_cardinality_issues = [i for i in issues if i.issue_type == "high_cardinality"]
    checks.append(
        PlatformCheck(
            "high_cardinality_fields", "warning" if high_cardinality_issues else "pass",
            f"{len(high_cardinality_issues)} high-cardinality field(s) may be expensive to filter on in Looker."
            if high_cardinality_issues else "No problematic high-cardinality fields.",
            {"columns": [i.column for i in high_cardinality_issues]},
        )
    )

    field_roles = {}
    for col in key_columns:
        field_roles[col] = "Potential Key"
    for col in measure_columns:
        field_roles[col] = "Potential Measure"
    for col in dimension_columns:
        field_roles[col] = "Potential Dimension"

    return build_result(
        "Looker", checks, field_roles=field_roles,
        recommendations=recommendations,
        export_recommendations=["CSV via a supported database connection"],
    )
