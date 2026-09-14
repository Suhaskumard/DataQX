"""Data Dictionary (DATAQX.pdf S42).

Built from the cleaned dataset's own profile plus this file's lineage and cleaning
log -- cleaning_actions/lineage_id are real, matched by column, never placeholder text.

Also carries one column per analytics platform (power_bi_role, tableau_role, ...),
sourced directly from each platform module's own `field_roles` output (see
`app.services.analytics_readiness`) -- never invented here.
"""

from __future__ import annotations

from app.services.cleaning import CleaningLogEntry
from app.services.lineage import LineageEntry
from app.services.profiling import DatasetProfile

# platform key (as used by app.services.platform_rules.PLATFORM_MODULES) -> the
# data-dictionary column name it fills in.
PLATFORM_ROLE_COLUMNS = {
    "power_bi": "power_bi_role",
    "tableau": "tableau_role",
    "alteryx": "alteryx_role",
    "excel": "excel_relevance",
    "looker": "looker_role",
    "looker_studio": "looker_studio_role",
    "qlik": "qlik_role",
    "sql": "sql_role",
    "python": "python_role",
    "r": "r_role",
}

DATA_DICTIONARY_COLUMNS = [
    "column_name",
    "original_name",
    "data_type",
    "description",
    "nullable",
    "unique_count",
    "missing_count",
    "missing_percentage",
    "min",
    "max",
    "mean",
    "median",
    "example_values",
    "cleaning_actions",
    "lineage_id",
    *PLATFORM_ROLE_COLUMNS.values(),
]


def _describe(inferred_type: str, missing_percentage: float) -> str:
    missing_note = f", {missing_percentage:.1f}% missing" if missing_percentage > 0 else ", no missing values"
    return f"{inferred_type.capitalize()} column{missing_note}."


def build_data_dictionary(
    profile: DatasetProfile,
    lineage_entries: list[LineageEntry],
    cleaning_log: list[CleaningLogEntry],
    platform_field_roles: dict[str, dict[str, str]] | None = None,
) -> list[dict]:
    """`platform_field_roles` is `{platform_key: {column: role_label}}`, i.e. each
    platform result's own `field_roles` from `AnalyticsReadinessResult.platforms`
    -- optional so callers that haven't computed readiness yet still get a valid
    dictionary with blank platform columns rather than an error."""
    platform_field_roles = platform_field_roles or {}
    lineage_by_column: dict[str, list[LineageEntry]] = {}
    for entry in lineage_entries:
        lineage_by_column.setdefault(entry.source_column, []).append(entry)

    cleaning_by_column: dict[str, list[CleaningLogEntry]] = {}
    for entry in cleaning_log:
        if entry.column is not None:
            cleaning_by_column.setdefault(entry.column, []).append(entry)

    rows = []
    for col in profile.columns:
        column_lineage = lineage_by_column.get(col.original_name, [])
        column_cleaning = cleaning_by_column.get(col.original_name, [])

        lineage_id = column_lineage[0].lineage_id if column_lineage else None
        cleaning_actions = ", ".join(sorted({c.action_taken for c in column_cleaning})) or None

        rows.append(
            {
                "column_name": col.clean_name,
                "original_name": col.original_name,
                "data_type": col.inferred_type,
                "description": _describe(col.inferred_type, col.missing_percentage),
                "nullable": col.missing_count > 0,
                "unique_count": col.unique_count,
                "missing_count": col.missing_count,
                "missing_percentage": col.missing_percentage,
                "min": col.min,
                "max": col.max,
                "mean": col.mean,
                "median": col.median,
                "example_values": "; ".join(col.example_values),
                "cleaning_actions": cleaning_actions,
                "lineage_id": lineage_id,
                **{
                    column_name: platform_field_roles.get(platform_key, {}).get(col.original_name)
                    for platform_key, column_name in PLATFORM_ROLE_COLUMNS.items()
                },
            }
        )
    return rows
