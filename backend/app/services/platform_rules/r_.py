"""R analytics readiness (DATAQX Phase 16). Uses the same universal facts as
the Python profile; recommendations are R-flavored (factors, Date class) but
no R-specific cleaning logic is introduced into the universal cleaning engine."""

from __future__ import annotations

import pandas as pd

from app.services.issue_detection import Issue
from app.services.platform_rules.common import PlatformCheck, PlatformResult, build_result
from app.services.profiling import DatasetProfile
from app.services.semantic_roles import ColumnRole, columns_with_role


def evaluate(
    df: pd.DataFrame,
    profile: DatasetProfile,
    issues: list[Issue],
    roles: list[ColumnRole],
    relationship_check: PlatformCheck | None = None,
) -> PlatformResult:
    checks: list[PlatformCheck] = []
    recommendations: list[str] = []

    numeric_columns = columns_with_role(roles, "measure")
    categorical_columns = columns_with_role(roles, "dimension_attribute")
    datetime_columns = columns_with_role(roles, "date_dimension")
    identifier_columns = columns_with_role(roles, "primary_key")

    checks.append(
        PlatformCheck(
            "numeric_columns", "pass" if numeric_columns else "not_applicable",
            f"{len(numeric_columns)} numeric column(s) identified: {numeric_columns}.",
            {"columns": numeric_columns},
        )
    )
    checks.append(
        PlatformCheck(
            "categorical_columns", "pass" if categorical_columns else "not_applicable",
            f"{len(categorical_columns)} categorical column(s) can be imported as R factors: {categorical_columns}.",
            {"columns": categorical_columns},
        )
    )
    if categorical_columns:
        recommendations.append("Convert categorical columns to factors (as.factor()) after import with read.csv()/readr::read_csv().")

    if datetime_columns:
        checks.append(
            PlatformCheck(
                "datetime_columns", "pass",
                f"Datetime column(s) {datetime_columns} should be parsed with as.Date()/as.POSIXct().",
                {"columns": datetime_columns},
            )
        )
        recommendations.append("Parse date columns explicitly with as.Date() -- R will not infer dates on import.")
    else:
        checks.append(PlatformCheck("datetime_columns", "not_applicable", "No datetime column identified."))

    avg_missing = sum(c.missing_percentage for c in profile.columns) / len(profile.columns) if profile.columns else 0.0
    checks.append(
        PlatformCheck(
            "missingness", "warning" if avg_missing > 5.0 else "pass",
            f"Average missingness across columns is {avg_missing:.1f}%; these will import as NA."
            if avg_missing > 0 else "No missing values.",
            {"average_missing_percentage": round(avg_missing, 2)},
        )
    )

    duplicate_row_issues = [i for i in issues if i.issue_type == "duplicate_rows"]
    checks.append(
        PlatformCheck(
            "duplicates", "warning" if duplicate_row_issues else "pass",
            f"{sum(i.affected_count for i in duplicate_row_issues)} duplicate record(s) found (see duplicated())."
            if duplicate_row_issues else "No duplicate records.",
        )
    )

    outlier_issues = [i for i in issues if i.issue_type == "outlier"]
    checks.append(
        PlatformCheck(
            "outliers", "warning" if outlier_issues else "pass",
            f"Outlier(s) found in: {[i.column for i in outlier_issues]} (see boxplot.stats())." if outlier_issues
            else "No statistical outliers detected.",
            {"columns": [i.column for i in outlier_issues]},
        )
    )

    checks.append(
        PlatformCheck(
            "identifiers", "pass" if identifier_columns else "not_applicable",
            f"Identifier column(s) {identifier_columns} are typically excluded from model formulas."
            if identifier_columns else "No identifier column detected.",
            {"columns": identifier_columns},
        )
    )

    high_cardinality_issues = [i for i in issues if i.issue_type == "high_cardinality"]
    checks.append(
        PlatformCheck(
            "high_cardinality_fields", "warning" if high_cardinality_issues else "pass",
            f"High-cardinality field(s) {[i.column for i in high_cardinality_issues]} would produce a very large factor."
            if high_cardinality_issues else "No problematic high-cardinality fields.",
            {"columns": [i.column for i in high_cardinality_issues]},
        )
    )

    field_roles = {col: "Identifier" for col in identifier_columns}
    field_roles.update({col: "Factor Candidate" for col in categorical_columns})

    return build_result(
        "R", checks, field_roles=field_roles,
        recommendations=recommendations,
        export_recommendations=["CSV (read.csv/readr)", "RDS for preserving R types"],
    )
