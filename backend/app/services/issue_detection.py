"""Issue detection (DATAQX.pdf S16).

Detects and reports data quality issues found by profiling -- it never modifies data
(cleaning is Phase 8) and never assigns a confidence score for auto-fixing (that's
Phase 7's Confidence Engine). `severity` here describes how bad an issue looks, not
whether it's safe to fix automatically.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

import pandas as pd

from app.services.profiling import DatasetProfile

PLACEHOLDER_TOKENS = {
    "na", "n/a", "n.a.", "null", "none", "-", "--", "?", "unknown",
    "not available", "blank", "empty",
}

_NUMERIC_LIKE_RE = re.compile(r"^-?\d+(\.\d+)?$")
# Only genuine slash-separated DD/MM/YYYY-shaped tokens are candidates for DD/MM vs
# MM/DD ambiguity. Dash-separated dates are excluded: a 4-digit first component
# ("2023-06-15") is unambiguously ISO Y-M-D, and treating the day as an "ambiguous
# first component" there is a false positive, not a real formatting inconsistency.
_AMBIGUOUS_DATE_TOKEN_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")


@dataclass
class Issue:
    issue_type: str
    column: str | None
    severity: str  # critical | high | medium | low
    affected_count: int
    description: str
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _is_placeholder(value: str) -> bool:
    return value.strip().lower() in PLACEHOLDER_TOKENS or value.strip() == ""


def _detect_missing_placeholders(df: pd.DataFrame) -> list[Issue]:
    issues = []
    for column in df.columns:
        series = df[column]
        if series.dtype != object:
            continue
        non_null = series.dropna().astype(str)
        if non_null.empty:
            continue

        is_placeholder_mask = non_null.map(_is_placeholder)
        placeholder_count = int(is_placeholder_mask.sum())
        non_placeholder_count = len(non_null) - placeholder_count

        # Contextual evidence: only flag when placeholders are mixed in with genuine
        # other values -- a column that's entirely placeholders is left alone (could
        # be legitimate, e.g. a status column that's genuinely always "Unknown").
        if placeholder_count > 0 and non_placeholder_count > 0:
            examples = sorted(set(non_null[is_placeholder_mask].tolist()))[:5]
            issues.append(
                Issue(
                    issue_type="missing_value_placeholder",
                    column=column,
                    severity="medium",
                    affected_count=placeholder_count,
                    description=f"Column '{column}' contains {placeholder_count} value(s) that look like missing-value placeholders mixed with real data.",
                    details={"examples": examples},
                )
            )
    return issues


def _detect_duplicates(df: pd.DataFrame, profile: DatasetProfile) -> list[Issue]:
    issues = []
    if profile.duplicate_row_count > 0:
        issues.append(
            Issue(
                issue_type="duplicate_rows",
                column=None,
                severity="high",
                affected_count=profile.duplicate_row_count,
                description=f"{profile.duplicate_row_count} exact duplicate row(s) found.",
            )
        )

    for col_profile in profile.columns:
        if col_profile.inferred_type != "id":
            continue
        column = col_profile.original_name
        series = df[column].dropna()
        dup_count = int(series.duplicated().sum())
        if dup_count > 0:
            issues.append(
                Issue(
                    issue_type="duplicate_id",
                    column=column,
                    severity="critical",
                    affected_count=dup_count,
                    description=f"ID column '{column}' has {dup_count} duplicate value(s); IDs must be unique.",
                )
            )
    return issues


def _detect_mixed_types(df: pd.DataFrame, profile: DatasetProfile) -> list[Issue]:
    issues = []
    for col_profile in profile.columns:
        if col_profile.inferred_type not in ("string", "categorical"):
            continue
        column = col_profile.original_name
        series = df[column]
        if series.dtype != object:
            continue
        non_null = series.dropna().astype(str)
        if non_null.empty:
            continue

        numeric_like = non_null.map(lambda v: bool(_NUMERIC_LIKE_RE.match(v.strip())))
        numeric_ratio = numeric_like.mean()
        non_numeric_count = int((~numeric_like).sum())

        if 0.7 <= numeric_ratio < 1.0 and non_numeric_count > 0:
            bad_examples = sorted(set(non_null[~numeric_like].tolist()))[:5]
            issues.append(
                Issue(
                    issue_type="mixed_data_types",
                    column=column,
                    severity="medium",
                    affected_count=non_numeric_count,
                    description=f"Column '{column}' looks mostly numeric but has {non_numeric_count} non-numeric value(s).",
                    details={"examples": bad_examples},
                )
            )
    return issues


def _detect_category_inconsistencies(profile: DatasetProfile) -> list[Issue]:
    issues = []
    for col_profile in profile.columns:
        extra = col_profile.categorical_extra
        if not extra:
            continue
        groups = extra.get("potential_inconsistencies") or []
        if groups:
            total_affected = sum(len(g) for g in groups)
            issues.append(
                Issue(
                    issue_type="category_inconsistency",
                    column=col_profile.original_name,
                    severity="low",
                    affected_count=total_affected,
                    description=f"Column '{col_profile.original_name}' has {len(groups)} group(s) of inconsistent category spellings/casing.",
                    details={"groups": groups},
                )
            )
    return issues


def _detect_date_issues(df: pd.DataFrame, profile: DatasetProfile) -> list[Issue]:
    issues = []
    for col_profile in profile.columns:
        extra = col_profile.date_extra
        if not extra:
            continue
        column = col_profile.original_name

        if extra.get("invalid_count"):
            issues.append(
                Issue(
                    issue_type="invalid_date",
                    column=column,
                    severity="high",
                    affected_count=extra["invalid_count"],
                    description=f"Column '{column}' has {extra['invalid_count']} value(s) that could not be parsed as a date.",
                )
            )
        if extra.get("future_count"):
            issues.append(
                Issue(
                    issue_type="future_date",
                    column=column,
                    severity="medium",
                    affected_count=extra["future_count"],
                    description=f"Column '{column}' has {extra['future_count']} date(s) in the future.",
                )
            )

        # Ambiguous format: some slash-dates clearly aren't DD/MM (or MM/DD) because
        # the day-or-month position exceeds 12, others are ambiguous because both the
        # day and month positions are <= 12 (could be read either way).
        non_null = df[column].dropna().astype(str)
        has_unambiguous_slash_date = False
        has_ambiguous = False
        for val in non_null:
            m = _AMBIGUOUS_DATE_TOKEN_RE.match(val.strip())
            if not m:
                continue
            day_or_month_a, day_or_month_b, _year = m.groups()
            a, b = int(day_or_month_a), int(day_or_month_b)
            if a > 12 or b > 12:
                has_unambiguous_slash_date = True
            else:
                has_ambiguous = True

        if has_unambiguous_slash_date and has_ambiguous:
            issues.append(
                Issue(
                    issue_type="ambiguous_date_format",
                    column=column,
                    severity="high",
                    affected_count=0,
                    description=f"Column '{column}' mixes date formats (some values are unambiguous DD/MM or MM/DD, others could be read either way). Do not guess -- flagged for review.",
                )
            )
    return issues


_IMPOSSIBLE_VALUE_RULES = [
    (re.compile(r"age", re.IGNORECASE), 0, 120),
    (re.compile(r"percent|pct", re.IGNORECASE), 0, 100),
    (re.compile(r"rating", re.IGNORECASE), 0, 5),
]


def _detect_impossible_values(df: pd.DataFrame) -> list[Issue]:
    issues = []
    for column in df.columns:
        series = df[column]
        if not pd.api.types.is_numeric_dtype(series):
            continue
        non_null = series.dropna()
        if non_null.empty:
            continue

        for pattern, low, high in _IMPOSSIBLE_VALUE_RULES:
            if pattern.search(str(column)):
                out_of_range = non_null[(non_null < low) | (non_null > high)]
                if len(out_of_range) > 0:
                    issues.append(
                        Issue(
                            issue_type="impossible_value",
                            column=column,
                            severity="high",
                            affected_count=int(len(out_of_range)),
                            description=f"Column '{column}' has {len(out_of_range)} value(s) outside the plausible range [{low}, {high}].",
                            details={"examples": out_of_range.head(5).tolist()},
                        )
                    )
                break

        if re.search(r"quantity|count", str(column), re.IGNORECASE):
            negative = non_null[non_null < 0]
            if len(negative) > 0:
                issues.append(
                    Issue(
                        issue_type="negative_value",
                        column=column,
                        severity="medium",
                        affected_count=int(len(negative)),
                        description=f"Column '{column}' has {len(negative)} negative value(s); consider whether this is valid for this domain.",
                        details={"examples": negative.head(5).tolist()},
                    )
                )
    return issues


def _detect_outliers(profile: DatasetProfile) -> list[Issue]:
    issues = []
    for col_profile in profile.columns:
        extra = col_profile.numeric_extra
        if not extra or not extra.get("outlier_count"):
            continue
        q25, q75 = extra["q25"], extra["q75"]
        iqr = q75 - q25
        lower_fence, upper_fence = q25 - 1.5 * iqr, q75 + 1.5 * iqr
        extreme_lower, extreme_upper = q25 - 3 * iqr, q75 + 3 * iqr

        min_val, max_val = col_profile.min, col_profile.max
        classification = "suspicious"
        if (min_val is not None and min_val < extreme_lower) or (
            max_val is not None and max_val > extreme_upper
        ):
            classification = "potential_error"

        issues.append(
            Issue(
                issue_type="outlier",
                column=col_profile.original_name,
                severity="medium" if classification == "suspicious" else "high",
                affected_count=extra["outlier_count"],
                description=f"Column '{col_profile.original_name}' has {extra['outlier_count']} statistical outlier(s), classified as '{classification}'.",
                details={
                    "classification": classification,
                    "lower_fence": lower_fence,
                    "upper_fence": upper_fence,
                },
            )
        )
    return issues


def _detect_schema_issues(profile: DatasetProfile) -> list[Issue]:
    issues = []
    for column in profile.constant_columns:
        issues.append(
            Issue(
                issue_type="constant_column",
                column=column,
                severity="low",
                affected_count=profile.row_count,
                description=f"Column '{column}' has the same value in every row.",
            )
        )

    empty_columns = [c.original_name for c in profile.columns if c.missing_count == profile.row_count]
    for column in empty_columns:
        issues.append(
            Issue(
                issue_type="empty_column",
                column=column,
                severity="medium",
                affected_count=profile.row_count,
                description=f"Column '{column}' is entirely empty.",
            )
        )

    for col_profile in profile.columns:
        if col_profile.inferred_type == "id":
            continue
        if col_profile.inferred_type in ("string",) and col_profile.unique_percentage > 95 and profile.row_count > 10:
            issues.append(
                Issue(
                    issue_type="high_cardinality",
                    column=col_profile.original_name,
                    severity="low",
                    affected_count=col_profile.unique_count,
                    description=f"Column '{col_profile.original_name}' has very high cardinality ({col_profile.unique_percentage:.1f}% unique); may not be useful for grouping/analysis.",
                )
            )
    return issues


def detect_issues(df: pd.DataFrame, profile: DatasetProfile) -> list[Issue]:
    issues: list[Issue] = []
    issues += _detect_missing_placeholders(df)
    issues += _detect_duplicates(df, profile)
    issues += _detect_mixed_types(df, profile)
    issues += _detect_category_inconsistencies(profile)
    issues += _detect_date_issues(df, profile)
    issues += _detect_impossible_values(df)
    issues += _detect_outliers(profile)
    issues += _detect_schema_issues(profile)
    return issues
