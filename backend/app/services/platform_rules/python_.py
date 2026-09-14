"""Python / data-science readiness (DATAQX Phase 16). Identifies column roles
useful for pandas/scikit-learn workflows -- does not claim any ML
preprocessing beyond what is actually implemented here."""

from __future__ import annotations

import re

import pandas as pd

from app.services.issue_detection import Issue
from app.services.platform_rules.common import PlatformCheck, PlatformResult, build_result
from app.services.profiling import DatasetProfile
from app.services.semantic_roles import ColumnRole, columns_with_role

_TARGET_NAME_RE = re.compile(r"target|label|outcome|churn|default|class|y$", re.IGNORECASE)


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
            f"{len(categorical_columns)} categorical column(s) identified: {categorical_columns}.",
            {"columns": categorical_columns},
        )
    )
    checks.append(
        PlatformCheck(
            "datetime_columns", "pass" if datetime_columns else "not_applicable",
            f"{len(datetime_columns)} datetime column(s) identified: {datetime_columns}.",
            {"columns": datetime_columns},
        )
    )

    avg_missing = sum(c.missing_percentage for c in profile.columns) / len(profile.columns) if profile.columns else 0.0
    if avg_missing > 0:
        checks.append(
            PlatformCheck(
                "missing_values", "warning" if avg_missing > 5.0 else "pass",
                f"Average missingness across columns is {avg_missing:.1f}%; consider an imputation strategy.",
                {"average_missing_percentage": round(avg_missing, 2)},
            )
        )
        if avg_missing > 5.0:
            recommendations.append("Handle missing values explicitly (e.g. pandas .fillna()/.dropna()) before modeling.")
    else:
        checks.append(PlatformCheck("missing_values", "pass", "No missing values."))

    outlier_issues = [i for i in issues if i.issue_type == "outlier"]
    checks.append(
        PlatformCheck(
            "outliers", "warning" if outlier_issues else "pass",
            f"Outlier(s) found in: {[i.column for i in outlier_issues]}." if outlier_issues
            else "No statistical outliers detected.",
            {"columns": [i.column for i in outlier_issues]},
        )
    )

    duplicate_row_issues = [i for i in issues if i.issue_type == "duplicate_rows"]
    checks.append(
        PlatformCheck(
            "duplicate_records", "warning" if duplicate_row_issues else "pass",
            f"{sum(i.affected_count for i in duplicate_row_issues)} duplicate record(s) found." if duplicate_row_issues
            else "No duplicate records.",
        )
    )

    checks.append(
        PlatformCheck(
            "identifiers", "pass" if identifier_columns else "not_applicable",
            f"Identifier column(s) {identifier_columns} should typically be excluded from model features."
            if identifier_columns else "No identifier column detected.",
            {"columns": identifier_columns},
        )
    )
    if identifier_columns:
        recommendations.append("Exclude identifier columns from feature matrices; they carry no predictive signal.")

    constant_issues = [i for i in issues if i.issue_type == "constant_column"]
    checks.append(
        PlatformCheck(
            "constant_columns", "warning" if constant_issues else "pass",
            f"Constant column(s) {[i.column for i in constant_issues]} carry zero variance." if constant_issues
            else "No zero-variance columns.",
            {"columns": [i.column for i in constant_issues]},
        )
    )

    high_cardinality_issues = [i for i in issues if i.issue_type == "high_cardinality"]
    checks.append(
        PlatformCheck(
            "high_cardinality_fields", "warning" if high_cardinality_issues else "pass",
            f"High-cardinality field(s) {[i.column for i in high_cardinality_issues]} may need target/hash encoding."
            if high_cardinality_issues else "No problematic high-cardinality fields.",
            {"columns": [i.column for i in high_cardinality_issues]},
        )
    )

    target_candidates = [c for c in df.columns if _TARGET_NAME_RE.search(str(c))]
    feature_candidates = [c for c in df.columns if c not in target_candidates and c not in identifier_columns]
    checks.append(
        PlatformCheck(
            "possible_target_variable", "pass" if target_candidates else "not_applicable",
            f"Possible target column(s) based on naming: {target_candidates}." if target_candidates
            else "No column name suggests a target/label variable.",
            {"columns": target_candidates},
        )
    )
    checks.append(
        PlatformCheck(
            "possible_feature_variables", "pass",
            f"{len(feature_candidates)} column(s) are possible feature variables.",
            {"columns": feature_candidates},
        )
    )

    field_roles = {col: "Identifier" for col in identifier_columns}
    field_roles.update({col: "Target Candidate" for col in target_candidates})

    return build_result(
        "Python", checks, field_roles=field_roles,
        recommendations=recommendations,
        export_recommendations=["CSV (pandas.read_csv)", "Parquet for larger volumes"],
    )
