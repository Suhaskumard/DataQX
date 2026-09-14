"""SQL analytics readiness (DATAQX Phase 16). Identifies key/normalization
candidates -- never automatically redesigns the user's database."""

from __future__ import annotations

import re

import pandas as pd

from app.services.issue_detection import Issue
from app.services.platform_rules.common import PlatformCheck, PlatformResult, build_result
from app.services.profiling import DatasetProfile
from app.services.semantic_roles import ColumnRole, columns_with_role

_MULTI_VALUE_DELIMITERS_RE = re.compile("|".join(re.escape(d) for d in (",", ";", "|")))


def evaluate(
    df: pd.DataFrame,
    profile: DatasetProfile,
    issues: list[Issue],
    roles: list[ColumnRole],
    relationship_check: PlatformCheck | None = None,
) -> PlatformResult:
    checks: list[PlatformCheck] = []
    recommendations: list[str] = []

    pk_candidates = columns_with_role(roles, "primary_key")
    checks.append(
        PlatformCheck(
            "primary_key_candidates", "pass" if pk_candidates else "warning",
            f"Primary key candidate(s): {pk_candidates}." if pk_candidates
            else "No column with sufficiently unique, ID-like values found for a primary key.",
            {"columns": pk_candidates},
        )
    )

    fk_candidates = [c for c in df.columns if str(c).lower().endswith("_id") and c not in pk_candidates]
    checks.append(
        PlatformCheck(
            "foreign_key_candidates", "pass" if fk_candidates else "not_applicable",
            f"Foreign key candidate(s): {fk_candidates}." if fk_candidates else "No foreign-key-shaped column found.",
            {"columns": fk_candidates},
        )
    )

    duplicate_id_issues = [i for i in issues if i.issue_type == "duplicate_id"]
    if duplicate_id_issues:
        checks.append(
            PlatformCheck(
                "duplicates", "fail",
                f"Primary key candidate(s) {[i.column for i in duplicate_id_issues]} contain duplicate values.",
                {"columns": [i.column for i in duplicate_id_issues]},
            )
        )
        recommendations.append("Resolve duplicate key values before enforcing a PRIMARY KEY constraint.")
    else:
        checks.append(PlatformCheck("duplicates", "pass", "No duplicate values in key candidate columns."))

    pk_nulls = {
        col: profile_col.missing_count
        for col in pk_candidates
        for profile_col in profile.columns
        if profile_col.original_name == col and profile_col.missing_count > 0
    }
    if pk_nulls:
        checks.append(
            PlatformCheck(
                "nullability", "fail",
                f"Primary key candidate(s) contain NULL value(s): {pk_nulls}.",
                {"violations": pk_nulls},
            )
        )
        recommendations.append("A PRIMARY KEY/NOT NULL column cannot contain nulls -- backfill or drop those rows.")
    else:
        checks.append(PlatformCheck("nullability", "pass", "Key candidate columns contain no NULL values."))

    mixed_type_issues = [i for i in issues if i.issue_type == "mixed_data_types"]
    checks.append(
        PlatformCheck(
            "data_types", "warning" if mixed_type_issues else "pass",
            f"{len(mixed_type_issues)} column(s) mix types; a single SQL column type cannot represent both."
            if mixed_type_issues else "Every column maps to a single consistent SQL type.",
            {"columns": [i.column for i in mixed_type_issues]},
        )
    )

    if relationship_check is not None:
        checks.append(relationship_check)

    multi_value_columns = []
    for col in df.columns:
        if col in pk_candidates or col in fk_candidates:
            continue
        series = df[col].dropna().astype(str)
        if len(series) == 0:
            continue
        delimiter_hits = series.str.contains(_MULTI_VALUE_DELIMITERS_RE)
        if delimiter_hits.mean() > 0.5:
            multi_value_columns.append(col)
    checks.append(
        PlatformCheck(
            "multi_value_cells", "warning" if multi_value_columns else "pass",
            f"Column(s) {multi_value_columns} appear to pack multiple values per cell (normalization concern)."
            if multi_value_columns else "No columns appear to pack multiple delimited values per cell.",
            {"columns": multi_value_columns},
        )
    )
    if multi_value_columns:
        recommendations.append("Normalize delimited multi-value columns into a separate related table (1NF).")

    near_constant = list(profile.near_constant_columns)
    checks.append(
        PlatformCheck(
            "normalization_concerns", "warning" if near_constant else "pass",
            f"Near-constant column(s) {near_constant} add little analytical value in a fact table."
            if near_constant else "No near-constant columns detected.",
            {"columns": near_constant},
        )
    )

    # Naming-based key roles take precedence over the generic type-based role: an
    # `*_id`-suffixed column that happens to be numeric (e.g. all-constant test
    # data, or a small sample) is a foreign key by convention, never a genuine
    # measure -- applying key roles last means they always win the display label.
    dimension_candidates = columns_with_role(roles, "dimension_attribute")
    measure_candidates = columns_with_role(roles, "measure")
    field_roles = {col: "Dimension Candidate" for col in dimension_candidates}
    field_roles.update({col: "Fact Candidate" for col in measure_candidates})
    field_roles.update({col: "Primary Key Candidate" for col in pk_candidates})
    field_roles.update({col: "Foreign Key Candidate" for col in fk_candidates})

    return build_result(
        "SQL", checks, field_roles=field_roles,
        recommendations=recommendations,
        export_recommendations=["CSV for bulk load (COPY/LOAD DATA)"],
    )
