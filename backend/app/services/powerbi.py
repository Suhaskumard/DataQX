"""Power BI Validation (DATAQX.pdf S38/S39).

Checks types, dates, keys, relationships, dimensions, high-cardinality, and measures,
producing a transparent, auditable readiness score -- every point deducted traces
back to a real, computed check result, never a fabricated number (S63).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd

from app.services.issue_detection import Issue
from app.services.profiling import DatasetProfile

_CURRENCY_NAME_RE = re.compile(r"price|amount|revenue|cost|total|subtotal|tax", re.IGNORECASE)
_PERCENT_NAME_RE = re.compile(r"percent|pct|rate", re.IGNORECASE)
_FK_NAME_RE = re.compile(r"^(.+)_id$", re.IGNORECASE)

_SCORE_START = 100
_FAIL_PENALTY = 15
_WARNING_PENALTY = 5


@dataclass
class PowerBICheck:
    check_name: str
    status: str  # pass | warning | fail | not_applicable
    message: str
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ColumnRole:
    column: str
    role: str  # primary_key | foreign_key_candidate | measure | dimension_attribute | date_dimension

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PowerBIReadinessReport:
    score: int
    table_role: str  # fact | dimension | unclassified
    columns: list[ColumnRole] = field(default_factory=list)
    checks: list[PowerBICheck] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "table_role": self.table_role,
            "columns": [c.to_dict() for c in self.columns],
            "checks": [c.to_dict() for c in self.checks],
        }


def compute_score(checks: list[PowerBICheck]) -> int:
    score = _SCORE_START
    for check in checks:
        if check.status == "fail":
            score -= _FAIL_PENALTY
        elif check.status == "warning":
            score -= _WARNING_PENALTY
    return max(0, min(100, score))


def _classify_columns(profile: DatasetProfile) -> list[ColumnRole]:
    roles = []
    for col in profile.columns:
        if col.inferred_type == "id":
            roles.append(ColumnRole(col.original_name, "primary_key"))
        elif col.inferred_type in ("date", "datetime"):
            roles.append(ColumnRole(col.original_name, "date_dimension"))
        elif col.inferred_type in ("integer", "float"):
            roles.append(ColumnRole(col.original_name, "measure"))
        elif col.inferred_type in ("categorical", "string", "boolean"):
            roles.append(ColumnRole(col.original_name, "dimension_attribute"))
    return roles


def _classify_table_role(columns: list[ColumnRole]) -> str:
    measure_count = sum(1 for c in columns if c.role == "measure")
    attribute_count = sum(1 for c in columns if c.role in ("dimension_attribute", "primary_key"))
    if measure_count == 0 and attribute_count == 0:
        return "unclassified"
    return "fact" if measure_count > attribute_count else "dimension"


def assess_single_file_readiness(
    df: pd.DataFrame, profile: DatasetProfile, issues: list[Issue]
) -> PowerBIReadinessReport:
    checks: list[PowerBICheck] = []
    columns = _classify_columns(profile)

    mixed_type_issues = [i for i in issues if i.issue_type == "mixed_data_types"]
    if mixed_type_issues:
        checks.append(
            PowerBICheck(
                "mixed_data_types", "warning",
                f"{len(mixed_type_issues)} column(s) have mixed data types.",
                {"columns": [i.column for i in mixed_type_issues]},
            )
        )
    else:
        checks.append(PowerBICheck("mixed_data_types", "pass", "No mixed-type columns detected."))

    date_invalid_total = sum(
        c.date_extra.get("invalid_count", 0) for c in profile.columns if c.date_extra
    )
    if date_invalid_total:
        checks.append(
            PowerBICheck(
                "date_validity", "warning",
                f"{date_invalid_total} invalid date value(s) found across date columns.",
                {"invalid_count": date_invalid_total},
            )
        )
    else:
        checks.append(PowerBICheck("date_validity", "pass", "All date values are valid."))

    duplicate_key_columns = {}
    for col in profile.columns:
        if col.inferred_type != "id":
            continue
        dup_count = int(df[col.original_name].dropna().duplicated().sum())
        if dup_count > 0:
            duplicate_key_columns[col.original_name] = dup_count
    if duplicate_key_columns:
        checks.append(
            PowerBICheck(
                "duplicate_keys", "fail",
                f"Duplicate key value(s) found: {duplicate_key_columns}.",
                {"violations": duplicate_key_columns},
            )
        )
    else:
        checks.append(PowerBICheck("duplicate_keys", "pass", "All key columns are unique."))

    high_cardinality_issues = [i for i in issues if i.issue_type == "high_cardinality"]
    if high_cardinality_issues:
        checks.append(
            PowerBICheck(
                "high_cardinality_fields", "warning",
                f"{len(high_cardinality_issues)} high-cardinality field(s) may not group well.",
                {"columns": [i.column for i in high_cardinality_issues]},
            )
        )
    else:
        checks.append(PowerBICheck("high_cardinality_fields", "pass", "No problematic high-cardinality fields."))

    date_dimension_columns = [c.column for c in columns if c.role == "date_dimension"]
    if date_dimension_columns:
        checks.append(
            PowerBICheck(
                "date_dimension_present", "pass",
                f"Date dimension column(s) found: {date_dimension_columns}.",
                {"columns": date_dimension_columns},
            )
        )
    else:
        checks.append(
            PowerBICheck(
                "date_dimension_present", "warning",
                "No date/datetime column found; time-based analysis won't be possible.",
            )
        )

    measure_columns = [c.column for c in columns if c.role == "measure"]
    checks.append(
        PowerBICheck(
            "measures_identified",
            "pass" if measure_columns else "warning",
            f"{len(measure_columns)} candidate measure column(s) identified."
            if measure_columns else "No numeric measure columns found.",
            {"columns": measure_columns},
        )
    )

    attribute_columns = [c.column for c in columns if c.role == "dimension_attribute"]
    checks.append(
        PowerBICheck(
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
        PowerBICheck(
            "currency_percentage_representation", "pass",
            f"Currency-like column(s): {currency_like}; percentage-like column(s): {percent_like}.",
            {"currency_like": currency_like, "percent_like": percent_like},
        )
    )

    table_role = _classify_table_role(columns)
    score = compute_score(checks)
    return PowerBIReadinessReport(score=score, table_role=table_role, columns=columns, checks=checks)


def _singularize(word: str) -> str:
    return word[:-1] if word.endswith("s") else word


def _filename_stem_singular(filename: str) -> str:
    return _singularize(Path(filename).stem.lower())


def assess_relationships(files: dict[str, tuple[pd.DataFrame, DatasetProfile]]) -> dict[str, PowerBICheck]:
    if len(files) < 2:
        return {
            name: PowerBICheck(
                "foreign_key_relationships", "not_applicable",
                "Only one file in this run; relationship checks require multiple related files.",
            )
            for name in files
        }

    # A column's referenced file is identified by naming convention (customer_id ->
    # customers.csv), not by whether it happens to be locally unique in its own file
    # -- a foreign key column can easily be unique within a small sample without
    # being anyone's primary key, so "inferred as id in this file" is not a reliable
    # signal for "this file's own key" and was found to produce false negatives.
    stems = {name: _filename_stem_singular(name) for name in files}

    results: dict[str, PowerBICheck] = {}
    for name, (df, _profile) in files.items():
        fk_findings = {}
        for column in df.columns:
            match = _FK_NAME_RE.match(str(column))
            if not match:
                continue
            prefix = match.group(1).lower()
            if prefix == stems[name]:
                continue  # this file's own natural primary key (e.g. orders.csv -> order_id)

            for other_name, other_stem in stems.items():
                if other_name == name or other_stem != prefix:
                    continue
                other_df, _ = files[other_name]
                if column not in other_df.columns:
                    continue
                referencing_values = set(df[column].dropna().unique())
                referenced_values = set(other_df[column].dropna().unique())
                orphans = referencing_values - referenced_values
                if orphans:
                    fk_findings[column] = {
                        "references": other_name,
                        "orphan_count": len(orphans),
                        "orphan_examples": sorted(str(v) for v in orphans)[:5],
                    }
                break

        if fk_findings:
            results[name] = PowerBICheck(
                "foreign_key_relationships", "warning",
                f"Orphan foreign key value(s) found: {list(fk_findings.keys())}.",
                {"findings": fk_findings},
            )
        else:
            results[name] = PowerBICheck(
                "foreign_key_relationships", "pass", "All matched foreign keys resolve correctly."
            )

    return results
