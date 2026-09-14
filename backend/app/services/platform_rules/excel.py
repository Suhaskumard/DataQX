"""Excel readiness (DATAQX Phase 16). Evaluates tabular structure and export
compatibility -- does not introduce Excel-specific cleaning into the universal
cleaning engine (`app.services.cleaning`), only reads its output."""

from __future__ import annotations

import pandas as pd

from app.services.issue_detection import Issue
from app.services.platform_rules.common import PlatformCheck, PlatformResult, build_result
from app.services.profiling import DatasetProfile
from app.services.semantic_roles import ColumnRole

_EXCEL_ROW_LIMIT = 1_048_576
_LONG_TEXT_THRESHOLD = 200


def evaluate(
    df: pd.DataFrame,
    profile: DatasetProfile,
    issues: list[Issue],
    roles: list[ColumnRole],
    relationship_check: PlatformCheck | None = None,
) -> PlatformResult:
    checks: list[PlatformCheck] = []
    recommendations: list[str] = []

    duplicate_headers = [c for c in set(df.columns) if list(df.columns).count(c) > 1]
    unnamed_columns = [c for c in df.columns if str(c).startswith("Unnamed:") or str(c).strip() == ""]
    header_problems = duplicate_headers + unnamed_columns
    checks.append(
        PlatformCheck(
            "single_header_row", "fail" if header_problems else "pass",
            f"Problematic header(s): {header_problems}." if header_problems
            else "A single, clean header row was detected.",
            {"duplicate_headers": duplicate_headers, "unnamed_columns": unnamed_columns},
        )
    )
    if header_problems:
        recommendations.append("Fix duplicate or unnamed column headers before exporting to Excel.")

    if profile.empty_row_count or profile.empty_column_count:
        checks.append(
            PlatformCheck(
                "blank_rows_columns", "warning",
                f"{profile.empty_row_count} fully-empty row(s), {profile.empty_column_count} fully-empty column(s) found.",
                {"empty_rows": profile.empty_row_count, "empty_columns": profile.empty_column_count},
            )
        )
    else:
        checks.append(PlatformCheck("blank_rows_columns", "pass", "No fully-blank rows or columns."))

    mixed_type_issues = [i for i in issues if i.issue_type == "mixed_data_types"]
    if mixed_type_issues:
        checks.append(
            PlatformCheck(
                "mixed_types", "warning",
                f"{len(mixed_type_issues)} column(s) mix numeric and text values, which Excel may format inconsistently.",
                {"columns": [i.column for i in mixed_type_issues]},
            )
        )
    else:
        checks.append(PlatformCheck("mixed_types", "pass", "No mixed-type columns."))

    date_invalid_total = sum(c.date_extra.get("invalid_count", 0) for c in profile.columns if c.date_extra)
    checks.append(
        PlatformCheck(
            "date_values", "warning" if date_invalid_total else "pass",
            f"{date_invalid_total} invalid date value(s) found." if date_invalid_total else "All date values are valid.",
        )
    )

    long_text_columns = [
        c.original_name for c in profile.columns
        if c.text_extra and any(len(str(v)) > _LONG_TEXT_THRESHOLD for v in c.example_values)
    ]
    checks.append(
        PlatformCheck(
            "long_text_fields", "warning" if long_text_columns else "pass",
            f"Column(s) with very long text values: {long_text_columns}." if long_text_columns
            else "No excessively long text fields.",
            {"columns": long_text_columns},
        )
    )

    duplicate_row_issues = [i for i in issues if i.issue_type == "duplicate_rows"]
    checks.append(
        PlatformCheck(
            "duplicate_rows", "warning" if duplicate_row_issues else "pass",
            f"{sum(i.affected_count for i in duplicate_row_issues)} duplicate row(s) found." if duplicate_row_issues
            else "No duplicate rows.",
        )
    )

    if profile.row_count > _EXCEL_ROW_LIMIT:
        checks.append(
            PlatformCheck(
                "data_volume", "fail",
                f"{profile.row_count:,} rows exceeds Excel's {_EXCEL_ROW_LIMIT:,}-row worksheet limit.",
                {"row_count": profile.row_count, "limit": _EXCEL_ROW_LIMIT},
            )
        )
        recommendations.append("Split the dataset across multiple sheets, or use a database/BI tool instead of a single worksheet.")
    else:
        checks.append(PlatformCheck("data_volume", "pass", f"{profile.row_count:,} rows is within Excel's worksheet limit."))

    field_roles = {col: "Long Text" for col in long_text_columns}
    field_roles.update({col: "Header Problem" for col in header_problems})

    return build_result(
        "Excel", checks, field_roles=field_roles,
        recommendations=recommendations,
        export_recommendations=["CSV", "XLSX"],
    )
