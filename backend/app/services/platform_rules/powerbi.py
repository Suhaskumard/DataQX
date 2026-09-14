"""Power BI readiness (DATAQX Phase 16).

Evaluates tabular structure, measures, dimensions, date fields, keys and
currency/percentage representation. This is a *readiness assessment*, not an
official Microsoft certification -- language stays "Power BI Ready", never
"Microsoft Certified".
"""

from __future__ import annotations

import re

import pandas as pd

from app.services.issue_detection import Issue
from app.services.platform_rules.common import PlatformCheck, PlatformResult, build_result
from app.services.profiling import DatasetProfile
from app.services.semantic_roles import ColumnRole, classify_table_role, columns_with_role

_CURRENCY_NAME_RE = re.compile(r"price|amount|revenue|cost|total|subtotal|tax", re.IGNORECASE)
_PERCENT_NAME_RE = re.compile(r"percent|pct|rate", re.IGNORECASE)


def evaluate(
    df: pd.DataFrame,
    profile: DatasetProfile,
    issues: list[Issue],
    roles: list[ColumnRole],
    relationship_check: PlatformCheck | None = None,
) -> PlatformResult:
    checks: list[PlatformCheck] = []
    recommendations: list[str] = []

    mixed_type_issues = [i for i in issues if i.issue_type == "mixed_data_types"]
    if mixed_type_issues:
        checks.append(
            PlatformCheck(
                "mixed_data_types", "warning",
                f"{len(mixed_type_issues)} column(s) have mixed data types.",
                {"columns": [i.column for i in mixed_type_issues]},
            )
        )
        recommendations.append("Resolve mixed-type columns before loading into Power BI's type system.")
    else:
        checks.append(PlatformCheck("mixed_data_types", "pass", "No mixed-type columns detected."))

    date_invalid_total = sum(c.date_extra.get("invalid_count", 0) for c in profile.columns if c.date_extra)
    if date_invalid_total:
        checks.append(
            PlatformCheck(
                "date_validity", "warning",
                f"{date_invalid_total} invalid date value(s) found across date columns.",
                {"invalid_count": date_invalid_total},
            )
        )
    else:
        checks.append(PlatformCheck("date_validity", "pass", "All date values are valid."))

    duplicate_key_columns = {}
    for col in profile.columns:
        if col.inferred_type != "id":
            continue
        dup_count = int(df[col.original_name].dropna().duplicated().sum())
        if dup_count > 0:
            duplicate_key_columns[col.original_name] = dup_count
    if duplicate_key_columns:
        checks.append(
            PlatformCheck(
                "duplicate_keys", "fail",
                f"Duplicate key value(s) found: {duplicate_key_columns}.",
                {"violations": duplicate_key_columns},
            )
        )
        recommendations.append("Deduplicate key columns before building relationships in the Power BI model.")
    else:
        checks.append(PlatformCheck("duplicate_keys", "pass", "All key columns are unique."))

    high_cardinality_issues = [i for i in issues if i.issue_type == "high_cardinality"]
    if high_cardinality_issues:
        checks.append(
            PlatformCheck(
                "high_cardinality_fields", "warning",
                f"{len(high_cardinality_issues)} high-cardinality field(s) may not group well.",
                {"columns": [i.column for i in high_cardinality_issues]},
            )
        )
    else:
        checks.append(PlatformCheck("high_cardinality_fields", "pass", "No problematic high-cardinality fields."))

    date_dimension_columns = columns_with_role(roles, "date_dimension")
    if date_dimension_columns:
        checks.append(
            PlatformCheck(
                "date_dimension_present", "pass",
                f"Date dimension column(s) found: {date_dimension_columns}.",
                {"columns": date_dimension_columns},
            )
        )
    else:
        checks.append(
            PlatformCheck(
                "date_dimension_present", "warning",
                "No date/datetime column found; time-based analysis won't be possible.",
            )
        )
        recommendations.append("Add a date/datetime column to enable time-intelligence in Power BI.")

    measure_columns = columns_with_role(roles, "measure")
    checks.append(
        PlatformCheck(
            "measures_identified",
            "pass" if measure_columns else "warning",
            f"{len(measure_columns)} candidate measure column(s) identified."
            if measure_columns else "No numeric measure columns found.",
            {"columns": measure_columns},
        )
    )

    attribute_columns = columns_with_role(roles, "dimension_attribute")
    checks.append(
        PlatformCheck(
            "dimension_attributes_identified",
            "pass" if attribute_columns else "warning",
            f"{len(attribute_columns)} candidate dimension attribute(s) identified."
            if attribute_columns else "No dimension attribute columns found.",
            {"columns": attribute_columns},
        )
    )

    currency_like = [c for c in df.columns if _CURRENCY_NAME_RE.search(str(c))]
    percent_like = [c for c in df.columns if _PERCENT_NAME_RE.search(str(c))]
    checks.append(
        PlatformCheck(
            "currency_percentage_representation", "pass",
            f"Currency-like column(s): {currency_like}; percentage-like column(s): {percent_like}.",
            {"currency_like": currency_like, "percent_like": percent_like},
        )
    )

    if relationship_check is not None:
        checks.append(relationship_check)

    table_role = classify_table_role(roles)
    checks.append(
        PlatformCheck("table_role", "pass", f"Classified as a '{table_role}' table.", {"table_role": table_role})
    )

    field_roles = {c.column: c.role for c in roles}
    export_recommendations = ["CSV", "XLSX"] if not duplicate_key_columns else ["CSV (after deduplication)"]

    return build_result(
        "Power BI", checks,
        field_roles={col: ("Key" if role == "primary_key" else role) for col, role in field_roles.items()},
        recommendations=recommendations,
        export_recommendations=export_recommendations,
    )
