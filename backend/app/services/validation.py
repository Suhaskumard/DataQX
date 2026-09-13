"""Validation Engine (DATAQX.pdf S36).

Runs a battery of checks against a (cleaned) DataFrame and reports PASS/WARNING/FAIL
per check plus an aggregated overall status. This phase only *reports* -- acting on a
FAIL (blocking publish, rollback) is Phase 12's Validation Gates & Rollback.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from app.services.profiling import profile_dataset

_STATUS_RANK = {"pass": 0, "warning": 1, "fail": 2}

_IMPOSSIBLE_VALUE_RULES = [
    (re.compile(r"age", re.IGNORECASE), 0, 120),
    (re.compile(r"percent|pct", re.IGNORECASE), 0, 100),
    (re.compile(r"rating", re.IGNORECASE), 0, 5),
]

_TOLERANCE = 1e-6


@dataclass
class ValidationCheckResult:
    check_name: str
    status: str  # pass | warning | fail
    message: str
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ValidationReport:
    overall_status: str
    checks: list[ValidationCheckResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _check_row_integrity(df: pd.DataFrame) -> ValidationCheckResult:
    if len(df) == 0:
        return ValidationCheckResult("row_integrity", "fail", "Dataset has zero rows.")
    return ValidationCheckResult("row_integrity", "pass", f"{len(df)} row(s) present.")


def _check_column_integrity(df: pd.DataFrame) -> ValidationCheckResult:
    if len(df.columns) == 0:
        return ValidationCheckResult("column_integrity", "fail", "Dataset has zero columns.")
    duplicate_names = df.columns[df.columns.duplicated()].tolist()
    if duplicate_names:
        return ValidationCheckResult(
            "column_integrity", "fail",
            f"Duplicate column name(s): {sorted(set(duplicate_names))}.",
            {"duplicate_columns": sorted(set(duplicate_names))},
        )
    return ValidationCheckResult("column_integrity", "pass", f"{len(df.columns)} column(s), all uniquely named.")


def _check_missingness(df: pd.DataFrame) -> ValidationCheckResult:
    if len(df) == 0 or len(df.columns) == 0:
        return ValidationCheckResult("missingness", "pass", "No data to check.")

    missing_pct = (df.isna().sum() / len(df) * 100)
    fully_empty = missing_pct[missing_pct >= 100].index.tolist()
    if fully_empty:
        return ValidationCheckResult(
            "missingness", "fail",
            f"Column(s) entirely missing after cleaning: {fully_empty}.",
            {"fully_empty_columns": fully_empty},
        )

    high_missing = missing_pct[missing_pct > 50].to_dict()
    if high_missing:
        return ValidationCheckResult(
            "missingness", "warning",
            f"Column(s) with over 50% missing values: {list(high_missing.keys())}.",
            {"high_missing_columns": high_missing},
        )
    return ValidationCheckResult("missingness", "pass", "No column exceeds 50% missing.")


def _check_duplicates(df: pd.DataFrame) -> ValidationCheckResult:
    dup_count = int(df.duplicated().sum())
    if dup_count > 0:
        return ValidationCheckResult(
            "duplicates", "fail",
            f"{dup_count} exact duplicate row(s) remain after cleaning.",
            {"duplicate_count": dup_count},
        )
    return ValidationCheckResult("duplicates", "pass", "No exact duplicate rows.")


def _check_id_uniqueness(df: pd.DataFrame, profile) -> ValidationCheckResult:
    id_columns = [c.original_name for c in profile.columns if c.inferred_type == "id"]
    violations = {}
    for column in id_columns:
        dup_count = int(df[column].dropna().duplicated().sum())
        if dup_count > 0:
            violations[column] = dup_count

    if violations:
        return ValidationCheckResult(
            "id_uniqueness", "fail",
            f"Duplicate values found in ID column(s): {violations}.",
            {"violations": violations},
        )
    if id_columns:
        return ValidationCheckResult("id_uniqueness", "pass", f"ID column(s) {id_columns} are all unique.")
    return ValidationCheckResult("id_uniqueness", "pass", "No ID columns to check.")


def _find_column(df: pd.DataFrame, *patterns: str) -> str | None:
    for column in df.columns:
        lowered = str(column).lower()
        if any(re.search(p, lowered) for p in patterns):
            return column
    return None


def _check_business_rules(df: pd.DataFrame) -> ValidationCheckResult:
    violations = {}

    start_col = _find_column(df, r"start_?date")
    end_col = _find_column(df, r"end_?date")
    if start_col and end_col:
        start = pd.to_datetime(df[start_col], errors="coerce")
        end = pd.to_datetime(df[end_col], errors="coerce")
        both_valid = start.notna() & end.notna()
        bad = int((both_valid & (end < start)).sum())
        if bad:
            violations["end_date_before_start_date"] = bad

    subtotal_col = _find_column(df, r"subtotal")
    tax_col = _find_column(df, r"^tax$|_tax$")
    total_col = _find_column(df, r"^total$|_total$")
    if subtotal_col and tax_col and total_col:
        expected = df[subtotal_col] + df[tax_col]
        mismatch = (expected - df[total_col]).abs() > _TOLERANCE
        bad = int(mismatch.sum())
        if bad:
            violations["total_not_equal_subtotal_plus_tax"] = bad

    qty_col = _find_column(df, r"quantity")
    price_col = _find_column(df, r"unit_?price|^price$")
    revenue_col = _find_column(df, r"revenue|^amount$")
    if qty_col and price_col and revenue_col:
        expected = df[qty_col] * df[price_col]
        mismatch = (expected - df[revenue_col]).abs() > _TOLERANCE
        bad = int(mismatch.sum())
        if bad:
            violations["revenue_not_equal_quantity_times_price"] = bad

    if not violations:
        return ValidationCheckResult("business_rules", "pass", "No applicable business rule violations found.")

    total_violations = sum(violations.values())
    row_count = max(len(df), 1)
    status = "fail" if (total_violations / row_count) > 0.5 else "warning"
    return ValidationCheckResult(
        "business_rules", status,
        f"Business rule violation(s) found: {violations}.",
        {"violations": violations},
    )


def _check_invalid_values(df: pd.DataFrame) -> ValidationCheckResult:
    findings = {}
    for column in df.columns:
        series = df[column]
        if not pd.api.types.is_numeric_dtype(series):
            continue
        non_null = series.dropna()
        if non_null.empty:
            continue
        for pattern, low, high in _IMPOSSIBLE_VALUE_RULES:
            if pattern.search(str(column)):
                out_of_range = int(((non_null < low) | (non_null > high)).sum())
                if out_of_range:
                    findings[column] = out_of_range
                break

    if findings:
        return ValidationCheckResult(
            "invalid_values", "warning",
            f"Column(s) with values outside plausible range remain: {findings}.",
            {"findings": findings},
        )
    return ValidationCheckResult("invalid_values", "pass", "No remaining out-of-range values detected.")


def _check_outlier_behavior(profile) -> ValidationCheckResult:
    findings = {}
    for col_profile in profile.columns:
        extra = col_profile.numeric_extra
        if extra and extra.get("outlier_count"):
            findings[col_profile.original_name] = extra["outlier_count"]

    if findings:
        return ValidationCheckResult(
            "outlier_behavior", "warning",
            f"Statistical outlier(s) remain in: {findings}.",
            {"findings": findings},
        )
    return ValidationCheckResult("outlier_behavior", "pass", "No statistical outliers detected.")


def _check_schema_integrity(df: pd.DataFrame) -> ValidationCheckResult:
    if len(df.columns) < 2:
        return ValidationCheckResult(
            "schema_integrity", "warning",
            f"Dataset has only {len(df.columns)} column(s); schema may be too thin for meaningful analysis.",
        )
    return ValidationCheckResult("schema_integrity", "pass", f"{len(df.columns)} column(s) present.")


def validate_dataset(df: pd.DataFrame) -> ValidationReport:
    checks = [
        _check_row_integrity(df),
        _check_column_integrity(df),
    ]

    # Checks that need a profile require at least valid rows/columns to compute one.
    if len(df) > 0 and len(df.columns) > 0 and not df.columns.duplicated().any():
        profile = profile_dataset(df)
        checks.append(_check_missingness(df))
        checks.append(_check_duplicates(df))
        checks.append(_check_id_uniqueness(df, profile))
        checks.append(_check_business_rules(df))
        checks.append(_check_invalid_values(df))
        checks.append(_check_outlier_behavior(profile))
        checks.append(_check_schema_integrity(df))

    overall_status = "pass"
    for check in checks:
        if _STATUS_RANK[check.status] > _STATUS_RANK[overall_status]:
            overall_status = check.status

    return ValidationReport(overall_status=overall_status, checks=checks)
