"""Tableau readiness (DATAQX Phase 16). Readiness assessment only -- never
claims Tableau certification."""

from __future__ import annotations

import re

import pandas as pd

from app.services.issue_detection import Issue
from app.services.platform_rules.common import PlatformCheck, PlatformResult, build_result
from app.services.profiling import DatasetProfile
from app.services.semantic_roles import ColumnRole, columns_with_role

_GEO_NAME_RE = re.compile(r"country|state|city|region|zip|postal|latitude|longitude|\blat\b|\blng\b|\bgeo\b", re.IGNORECASE)


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
            f"{len(measure_columns)} potential measure column(s) identified." if measure_columns
            else "No numeric measure columns found for aggregation.",
            {"columns": measure_columns},
        )
    )

    dimension_columns = columns_with_role(roles, "dimension_attribute")
    checks.append(
        PlatformCheck(
            "potential_dimensions", "pass" if dimension_columns else "warning",
            f"{len(dimension_columns)} potential dimension column(s) identified." if dimension_columns
            else "No categorical dimension columns found.",
            {"columns": dimension_columns},
        )
    )

    date_columns = columns_with_role(roles, "date_dimension")
    checks.append(
        PlatformCheck(
            "potential_date_field", "pass" if date_columns else "warning",
            f"Potential date field(s): {date_columns}." if date_columns else "No date field found for time-series analysis.",
            {"columns": date_columns},
        )
    )

    geo_columns = [c for c in df.columns if _GEO_NAME_RE.search(str(c))]
    checks.append(
        PlatformCheck(
            "potential_geographic_field", "pass" if geo_columns else "not_applicable",
            f"Potential geographic field(s): {geo_columns}." if geo_columns else "No geographic field names detected.",
            {"columns": geo_columns},
        )
    )

    mixed_type_issues = [i for i in issues if i.issue_type == "mixed_data_types"]
    if mixed_type_issues:
        checks.append(
            PlatformCheck(
                "data_type_consistency", "warning",
                f"{len(mixed_type_issues)} column(s) have mixed data types.",
                {"columns": [i.column for i in mixed_type_issues]},
            )
        )
        recommendations.append("Resolve mixed-type columns so Tableau infers a single field type per column.")
    else:
        checks.append(PlatformCheck("data_type_consistency", "pass", "All columns have consistent data types."))

    duplicate_row_issues = [i for i in issues if i.issue_type == "duplicate_rows"]
    if duplicate_row_issues:
        checks.append(
            PlatformCheck(
                "duplicate_records", "warning",
                f"{sum(i.affected_count for i in duplicate_row_issues)} duplicate row(s) found; may inflate aggregations.",
            )
        )
    else:
        checks.append(PlatformCheck("duplicate_records", "pass", "No duplicate rows found."))

    high_cardinality_issues = [i for i in issues if i.issue_type == "high_cardinality"]
    if high_cardinality_issues:
        checks.append(
            PlatformCheck(
                "high_cardinality_fields", "warning",
                f"{len(high_cardinality_issues)} high-cardinality field(s) may be slow to filter/group in Tableau.",
                {"columns": [i.column for i in high_cardinality_issues]},
            )
        )
    else:
        checks.append(PlatformCheck("high_cardinality_fields", "pass", "No problematic high-cardinality fields."))

    near_unique_measures = [
        c.original_name for c in profile.columns
        if c.original_name in measure_columns and c.unique_percentage >= 95.0
    ]
    if near_unique_measures:
        checks.append(
            PlatformCheck(
                "aggregation_safety", "warning",
                f"Measure column(s) {near_unique_measures} are almost entirely unique values; SUM/AVG may not be meaningful.",
                {"columns": near_unique_measures},
            )
        )
        recommendations.append("Aggregation Warning: verify near-unique numeric columns are true measures, not identifiers.")
    else:
        checks.append(PlatformCheck("aggregation_safety", "pass", "Measure columns aggregate safely."))

    if relationship_check is not None:
        checks.append(relationship_check)

    field_roles = {}
    for col in measure_columns:
        field_roles[col] = "Potential Measure"
    for col in dimension_columns:
        field_roles[col] = "Potential Dimension"
    for col in date_columns:
        field_roles[col] = "Potential Date Field"
    for col in geo_columns:
        field_roles[col] = "Potential Geographic Field"

    return build_result(
        "Tableau", checks, field_roles=field_roles,
        recommendations=recommendations,
        export_recommendations=["CSV", "XLSX"],
    )
