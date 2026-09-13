"""Cleaning Engine (DATAQX.pdf S8/S65 Phase 8).

Applies exactly the actions already promised by the Confidence Engine (Phase 7):
HIGH-confidence transformations are applied automatically, MEDIUM-confidence ones are
applied automatically with a logged reason, and LOW-confidence issues are never
touched. Never invents a new transformation beyond what classify_issue() already
described. The caller is responsible for keeping the raw source file untouched --
this function only ever operates on an in-memory copy of the DataFrame.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

from app.services.confidence import classify_issue
from app.services.issue_detection import Issue, _is_placeholder

EXAMPLE_LIMIT = 5

# Schema-changing operations first (so later per-value fixes see a stable frame),
# then per-value fixes. Anything not listed here is a no-op (defensive default).
_CLEANING_ORDER = {
    "empty_column": 0,
    "duplicate_rows": 1,
    "whitespace_formatting": 2,
    "missing_value_placeholder": 3,
    "category_inconsistency": 4,
    "invalid_date": 5,
}


@dataclass
class CleaningLogEntry:
    issue_type: str
    column: str | None
    confidence: str
    action_taken: str
    affected_count: int
    rule: str
    reason: str
    before_examples: list = field(default_factory=list)
    after_examples: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CleaningResult:
    cleaned_df: pd.DataFrame
    log: list[CleaningLogEntry] = field(default_factory=list)
    skipped_low_confidence: int = 0


def _clean_whitespace(df: pd.DataFrame, issue: Issue) -> tuple[pd.DataFrame, list, list]:
    column = issue.column
    before = df[column].dropna().head(EXAMPLE_LIMIT).tolist()
    df[column] = df[column].map(
        lambda v: " ".join(v.split()) if isinstance(v, str) else v
    )
    after = df[column].dropna().head(EXAMPLE_LIMIT).tolist()
    return df, before, after


def _clean_empty_column(df: pd.DataFrame, issue: Issue) -> tuple[pd.DataFrame, list, list]:
    column = issue.column
    df = df.drop(columns=[column])
    return df, [], []


def _clean_duplicate_rows(df: pd.DataFrame, issue: Issue) -> tuple[pd.DataFrame, list, list]:
    before_count = len(df)
    df = df.drop_duplicates(keep="first").reset_index(drop=True)
    after_count = len(df)
    return df, [f"{before_count} rows"], [f"{after_count} rows"]


def _clean_missing_placeholder(df: pd.DataFrame, issue: Issue) -> tuple[pd.DataFrame, list, list]:
    column = issue.column
    series = df[column]
    is_placeholder_mask = series.map(lambda v: isinstance(v, str) and _is_placeholder(v))
    before = series[is_placeholder_mask].head(EXAMPLE_LIMIT).tolist()
    df.loc[is_placeholder_mask, column] = pd.NA
    return df, before, ["NaN"] * len(before)


def _clean_category_inconsistency(df: pd.DataFrame, issue: Issue) -> tuple[pd.DataFrame, list, list]:
    column = issue.column
    groups = issue.details.get("groups", [])
    before_all, after_all = [], []
    counts = df[column].value_counts()

    for group in groups:
        variants_in_data = [v for v in group if v in counts.index]
        if not variants_in_data:
            continue
        canonical = max(variants_in_data, key=lambda v: counts[v])
        replacements = {v: canonical for v in variants_in_data if v != canonical}
        if replacements:
            before_all.extend(replacements.keys())
            after_all.extend([canonical] * len(replacements))
            df[column] = df[column].replace(replacements)

    return df, before_all[:EXAMPLE_LIMIT], after_all[:EXAMPLE_LIMIT]


def _clean_invalid_date(df: pd.DataFrame, issue: Issue) -> tuple[pd.DataFrame, list, list]:
    column = issue.column
    series = df[column]
    parsed = pd.to_datetime(series, errors="coerce")
    invalid_mask = parsed.isna() & series.notna()
    before = series[invalid_mask].head(EXAMPLE_LIMIT).tolist()
    df.loc[invalid_mask, column] = pd.NA
    return df, before, ["NaN"] * len(before)


_HANDLERS = {
    "whitespace_formatting": _clean_whitespace,
    "empty_column": _clean_empty_column,
    "duplicate_rows": _clean_duplicate_rows,
    "missing_value_placeholder": _clean_missing_placeholder,
    "category_inconsistency": _clean_category_inconsistency,
    "invalid_date": _clean_invalid_date,
}


def apply_cleaning(df: pd.DataFrame, issues: list[Issue]) -> CleaningResult:
    working = df.copy()
    log: list[CleaningLogEntry] = []
    skipped_low_confidence = 0

    actionable_issues = sorted(
        (issue for issue in issues if issue.issue_type in _CLEANING_ORDER),
        key=lambda issue: _CLEANING_ORDER[issue.issue_type],
    )
    non_actionable_issues = [issue for issue in issues if issue.issue_type not in _CLEANING_ORDER]

    for issue in non_actionable_issues:
        decision = classify_issue(issue)
        if decision.confidence == "LOW":
            skipped_low_confidence += 1

    for issue in actionable_issues:
        decision = classify_issue(issue)
        if decision.confidence == "LOW":
            skipped_low_confidence += 1
            continue

        handler = _HANDLERS[issue.issue_type]
        working, before, after = handler(working, issue)

        log.append(
            CleaningLogEntry(
                issue_type=issue.issue_type,
                column=issue.column,
                confidence=decision.confidence,
                action_taken=decision.action,
                affected_count=issue.affected_count,
                rule=decision.rule,
                reason=decision.reason,
                before_examples=[str(v) for v in before],
                after_examples=[str(v) for v in after],
            )
        )

    return CleaningResult(cleaned_df=working, log=log, skipped_low_confidence=skipped_low_confidence)
