"""Alteryx readiness (DATAQX Phase 16). Focused on data-preparation workflow
compatibility (Join/Union/Filter/Formula/Summarize/Sort/Group) -- a readiness
assessment, not an Alteryx certification."""

from __future__ import annotations

import re

import pandas as pd

from app.services.issue_detection import Issue
from app.services.platform_rules.common import PlatformCheck, PlatformResult, build_result
from app.services.profiling import DatasetProfile
from app.services.semantic_roles import ColumnRole, columns_with_role

_BAD_FIELD_NAME_RE = re.compile(r"[^A-Za-z0-9_]")


def evaluate(
    df: pd.DataFrame,
    profile: DatasetProfile,
    issues: list[Issue],
    roles: list[ColumnRole],
    relationship_check: PlatformCheck | None = None,
) -> PlatformResult:
    checks: list[PlatformCheck] = []
    recommendations: list[str] = []

    schema_issue_columns = list(profile.constant_columns) + [
        c.original_name for c in profile.columns if c.missing_percentage == 100.0
    ]
    if schema_issue_columns:
        checks.append(
            PlatformCheck(
                "schema_stability", "warning",
                f"{len(schema_issue_columns)} constant or fully-empty column(s) add no value to a workflow.",
                {"columns": schema_issue_columns},
            )
        )
        recommendations.append("Drop constant/empty columns with a Select tool before downstream Formula/Summarize steps.")
    else:
        checks.append(PlatformCheck("schema_stability", "pass", "No constant or fully-empty columns."))

    bad_names = [c for c in df.columns if _BAD_FIELD_NAME_RE.search(str(c))]
    checks.append(
        PlatformCheck(
            "field_naming", "warning" if bad_names else "pass",
            f"{len(bad_names)} field name(s) contain spaces or special characters." if bad_names
            else "All field names are workflow-safe (alphanumeric/underscore).",
            {"columns": bad_names},
        )
    )
    if bad_names:
        recommendations.append("Rename fields with spaces/special characters using a Select tool before Formula steps.")

    mixed_type_issues = [i for i in issues if i.issue_type == "mixed_data_types"]
    if mixed_type_issues:
        checks.append(
            PlatformCheck(
                "numeric_parsing", "warning",
                f"{len(mixed_type_issues)} column(s) mix numeric and text values; Auto Field may mis-infer type.",
                {"columns": [i.column for i in mixed_type_issues]},
            )
        )
    else:
        checks.append(PlatformCheck("numeric_parsing", "pass", "No mixed numeric/text columns detected."))

    date_issue_types = {"invalid_date", "ambiguous_date_format", "future_date"}
    date_issues = [i for i in issues if i.issue_type in date_issue_types]
    if date_issues:
        checks.append(
            PlatformCheck(
                "date_parsing", "warning",
                f"{len(date_issues)} date-related issue(s) found; a DateTime tool may fail to parse these rows.",
                {"issue_types": sorted({i.issue_type for i in date_issues})},
            )
        )
    else:
        checks.append(PlatformCheck("date_parsing", "pass", "No date parsing issues found."))

    whitespace_issues = [i for i in issues if i.issue_type == "whitespace_formatting"]
    checks.append(
        PlatformCheck(
            "text_normalization", "warning" if whitespace_issues else "pass",
            f"{len(whitespace_issues)} column(s) have whitespace formatting issues that could break exact-match Join keys."
            if whitespace_issues else "No text normalization issues found.",
            {"columns": [i.column for i in whitespace_issues]},
        )
    )

    join_key_candidates = columns_with_role(roles, "primary_key")
    duplicate_id_issues = [i for i in issues if i.issue_type == "duplicate_id"]
    if duplicate_id_issues:
        checks.append(
            PlatformCheck(
                "join_keys", "fail",
                f"Duplicate values found in join-key candidate column(s): {[i.column for i in duplicate_id_issues]}.",
                {"columns": [i.column for i in duplicate_id_issues]},
            )
        )
        recommendations.append("A Join on a non-unique key will fan out rows -- deduplicate the key first.")
    elif join_key_candidates:
        checks.append(
            PlatformCheck(
                "join_keys", "pass",
                f"Join-key candidate(s) available and unique: {join_key_candidates}.",
                {"columns": join_key_candidates},
            )
        )
    else:
        checks.append(PlatformCheck("join_keys", "warning", "No obvious unique key column found for Join/Union alignment."))

    if relationship_check is not None:
        checks.append(relationship_check)

    field_roles = {col: "Join Key" for col in join_key_candidates}
    return build_result(
        "Alteryx", checks, field_roles=field_roles,
        recommendations=recommendations,
        export_recommendations=["CSV", "YXDB-compatible CSV/XLSX"],
    )
