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
    # Full per-row detail (not capped) -- {"row_index": int|None, "original_value": ..., "new_value": ...}.
    # Used by Phase 9's audit_logging to build row-level or aggregated CSV rows.
    changes: list = field(default_factory=list)
    before_examples: list = field(default_factory=list)
    after_examples: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CleaningResult:
    cleaned_df: pd.DataFrame
    log: list[CleaningLogEntry] = field(default_factory=list)
    skipped_low_confidence: int = 0
    skipped_protected_columns: int = 0
    # Issues withheld solely because their column is protected -- kept separate from
    # `log` (which only ever covers issues that were actually applied) so audit_logging
    # can report the issue's real confidence/rule/reason instead of guessing LOW, per
    # DATAQX.pdf S33's requirement that audit rows never contain misleading information.
    protected_skips: list[dict] = field(default_factory=list)


def _clean_whitespace(df: pd.DataFrame, issue: Issue) -> tuple[pd.DataFrame, list]:
    column = issue.column
    series = df[column]
    changed_mask = series.map(
        lambda v: isinstance(v, str) and " ".join(v.split()) != v
    )
    changes = [
        {"row_index": int(idx), "original_value": series.loc[idx], "new_value": " ".join(series.loc[idx].split())}
        for idx in series[changed_mask].index
    ]
    df[column] = df[column].map(lambda v: " ".join(v.split()) if isinstance(v, str) else v)
    return df, changes


def _clean_empty_column(df: pd.DataFrame, issue: Issue) -> tuple[pd.DataFrame, list]:
    column = issue.column
    changes = [{"row_index": None, "original_value": column, "new_value": None}]
    df = df.drop(columns=[column])
    return df, changes


def _clean_duplicate_rows(df: pd.DataFrame, issue: Issue) -> tuple[pd.DataFrame, list]:
    duplicate_mask = df.duplicated(keep="first")
    changes = [
        {"row_index": int(idx), "original_value": "<duplicate row>", "new_value": None}
        for idx in df[duplicate_mask].index
    ]
    df = df.drop_duplicates(keep="first").reset_index(drop=True)
    return df, changes


def _clean_missing_placeholder(df: pd.DataFrame, issue: Issue) -> tuple[pd.DataFrame, list]:
    column = issue.column
    series = df[column]
    is_placeholder_mask = series.map(lambda v: isinstance(v, str) and _is_placeholder(v))
    changes = [
        {"row_index": int(idx), "original_value": series.loc[idx], "new_value": None}
        for idx in series[is_placeholder_mask].index
    ]
    df.loc[is_placeholder_mask, column] = pd.NA
    return df, changes


def _clean_category_inconsistency(df: pd.DataFrame, issue: Issue) -> tuple[pd.DataFrame, list]:
    column = issue.column
    groups = issue.details.get("groups", [])
    changes = []
    counts = df[column].value_counts()

    for group in groups:
        variants_in_data = [v for v in group if v in counts.index]
        if not variants_in_data:
            continue
        canonical = max(variants_in_data, key=lambda v: counts[v])
        replacements = {v: canonical for v in variants_in_data if v != canonical}
        if replacements:
            series = df[column]
            for idx in series[series.isin(replacements.keys())].index:
                changes.append(
                    {"row_index": int(idx), "original_value": series.loc[idx], "new_value": canonical}
                )
            df[column] = df[column].replace(replacements)

    return df, changes


def _clean_invalid_date(df: pd.DataFrame, issue: Issue) -> tuple[pd.DataFrame, list]:
    column = issue.column
    series = df[column]
    parsed = pd.to_datetime(series, errors="coerce")
    invalid_mask = parsed.isna() & series.notna()
    changes = [
        {"row_index": int(idx), "original_value": series.loc[idx], "new_value": None}
        for idx in series[invalid_mask].index
    ]
    df.loc[invalid_mask, column] = pd.NA
    return df, changes


_HANDLERS = {
    "whitespace_formatting": _clean_whitespace,
    "empty_column": _clean_empty_column,
    "duplicate_rows": _clean_duplicate_rows,
    "missing_value_placeholder": _clean_missing_placeholder,
    "category_inconsistency": _clean_category_inconsistency,
    "invalid_date": _clean_invalid_date,
}


def _normalize_column_name(name: str) -> str:
    """Casefold+strip so protected/required column matching survives case and
    whitespace differences between a project plan and real column names (a plan
    protecting "Customer_ID" must still protect the real column "customer_id")."""
    return name.strip().casefold()


def apply_cleaning(
    df: pd.DataFrame,
    issues: list[Issue],
    protected_columns: set[str] | None = None,
) -> CleaningResult:
    protected_columns = protected_columns or set()
    normalized_protected = {_normalize_column_name(c) for c in protected_columns}
    working = df.copy()
    log: list[CleaningLogEntry] = []
    skipped_low_confidence = 0
    skipped_protected_columns = 0
    protected_skips: list[dict] = []

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
        # Explicit project requirements outrank confidence (DATAQX.pdf S12 priority
        # order): a protected column is never modified, no matter how safe the fix.
        if issue.column is not None and _normalize_column_name(issue.column) in normalized_protected:
            skipped_protected_columns += 1
            decision = classify_issue(issue)
            protected_skips.append(
                {
                    "issue_type": issue.issue_type,
                    "column": issue.column,
                    "confidence": decision.confidence,
                    "rule": decision.rule,
                    "reason": f"Column is protected by the project plan; withheld despite {decision.confidence} confidence ({decision.reason})",
                    "action": "Skipped: column is protected by the project plan.",
                    "severity": issue.severity,
                }
            )
            continue

        decision = classify_issue(issue)
        if decision.confidence == "LOW":
            skipped_low_confidence += 1
            continue

        handler = _HANDLERS[issue.issue_type]
        working, changes = handler(working, issue)

        log.append(
            CleaningLogEntry(
                issue_type=issue.issue_type,
                column=issue.column,
                confidence=decision.confidence,
                action_taken=decision.action,
                affected_count=len(changes),
                rule=decision.rule,
                reason=decision.reason,
                changes=changes,
                before_examples=[str(c["original_value"]) for c in changes[:EXAMPLE_LIMIT]],
                after_examples=[str(c["new_value"]) for c in changes[:EXAMPLE_LIMIT]],
            )
        )

    # A newly-emergent duplicate can appear only after whitespace/placeholder/category
    # normalization collapses previously-distinct rows into identical ones (dedup itself
    # already ran first, at _CLEANING_ORDER priority 0, and only catches duplicates that
    # existed *before* normalization). Without this second pass, such rows survive
    # cleaning and validate_dataset's duplicate check fails the whole file, triggering a
    # rollback of data that was actually fully cleanable. Always re-checked (cheap: one
    # `.duplicated()` call) rather than gated on whether an original `duplicate_rows`
    # issue was detected, since the whole point is to catch duplicates that did NOT
    # exist -- and so were never detected -- before normalization ran.
    pre_rerun_row_count = len(working)
    rerun_mask = working.duplicated(keep="first")
    if rerun_mask.any():
        new_duplicate_changes = [
            {"row_index": int(idx), "original_value": "<duplicate row (post-normalization)>", "new_value": None}
            for idx in working[rerun_mask].index
        ]
        working = working.drop_duplicates(keep="first").reset_index(drop=True)
        log.append(
            CleaningLogEntry(
                issue_type="duplicate_rows",
                column=None,
                confidence="HIGH",
                action_taken="Removed duplicate row(s) that only became identical after normalization.",
                affected_count=len(new_duplicate_changes),
                rule="duplicate_rows_post_normalization",
                reason=(
                    f"{pre_rerun_row_count - len(working)} row(s) became exact duplicates after "
                    "whitespace/placeholder/category normalization and were removed."
                ),
                changes=new_duplicate_changes,
                before_examples=[str(c["original_value"]) for c in new_duplicate_changes[:EXAMPLE_LIMIT]],
                after_examples=[str(c["new_value"]) for c in new_duplicate_changes[:EXAMPLE_LIMIT]],
            )
        )

    return CleaningResult(
        cleaned_df=working,
        log=log,
        skipped_low_confidence=skipped_low_confidence,
        skipped_protected_columns=skipped_protected_columns,
        protected_skips=protected_skips,
    )
