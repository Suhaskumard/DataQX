"""Confidence Engine (DATAQX.pdf S31).

Classifies a proposed transformation for each detected issue as HIGH (safe to
auto-apply), MEDIUM (apply with strong evidence, log it), or LOW (never auto-modify,
flag for human review). This module only classifies -- it never modifies data
(that's Phase 8, the Cleaning Engine).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.services.issue_detection import Issue

ConfidenceLevel = str  # "HIGH" | "MEDIUM" | "LOW"


@dataclass
class ConfidenceDecision:
    confidence: ConfidenceLevel
    rule: str
    evidence: dict
    action: str
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


# One entry per issue_type Phase 6 can produce: (confidence, action, reason).
_CONFIDENCE_TABLE: dict[str, tuple[str, str, str]] = {
    # HIGH -- safe to automatically apply (DATAQX.pdf S31 HIGH examples).
    "whitespace_formatting": (
        "HIGH",
        "Trim leading/trailing whitespace and collapse multiple internal spaces.",
        "Whitespace normalization never changes the semantic meaning of a value.",
    ),
    "empty_column": (
        "HIGH",
        "Drop the column.",
        "Column contains no data in any row; dropping it loses no information.",
    ),
    "duplicate_rows": (
        "HIGH",
        "Remove duplicate row(s), keeping the first occurrence.",
        "Rows are 100% identical across every column; removing the extra copy is lossless.",
    ),
    # MEDIUM -- apply with strong evidence, log it.
    "missing_value_placeholder": (
        "MEDIUM",
        "Convert placeholder text to a proper missing value (NaN).",
        "Value matches a recognized missing-value placeholder token and co-occurs with genuine data in the same column.",
    ),
    "category_inconsistency": (
        "MEDIUM",
        "Standardize to a single canonical spelling/casing per group.",
        "Values differ only by case or whitespace and clearly represent the same category.",
    ),
    "invalid_date": (
        "MEDIUM",
        "Convert the unparseable value to missing (NaN).",
        "Value does not match any recognized date format; marking it missing is safe, guessing the intended date is not.",
    ),
    # LOW -- never auto-modify, flag for human review.
    "duplicate_id": (
        "LOW",
        "Flag for manual review.",
        "Cannot safely determine which duplicate record is authoritative without human input.",
    ),
    "mixed_data_types": (
        "LOW",
        "Flag for manual review.",
        "Non-numeric values in an otherwise numeric column may indicate a data entry error or a different meaning; guessing is unsafe.",
    ),
    "future_date": (
        "LOW",
        "Flag for manual review.",
        "A future date may be legitimate (e.g. a scheduled event); only a human can judge intent.",
    ),
    "ambiguous_date_format": (
        "LOW",
        "Flag for manual review.",
        "Some values could be read as DD/MM or MM/DD; guessing risks silently corrupting valid dates.",
    ),
    "impossible_value": (
        "LOW",
        "Flag for manual review.",
        "Values outside the plausible range may be legitimate depending on business context.",
    ),
    "negative_value": (
        "LOW",
        "Flag for manual review.",
        "Negative values may be legitimate (e.g. returns/refunds) depending on business context.",
    ),
    "outlier": (
        "LOW",
        "Flag for manual review.",
        "Statistical outliers are never auto-deleted; only a human can judge whether the value is legitimate, suspicious, or an error.",
    ),
    "constant_column": (
        "LOW",
        "Flag as a candidate to drop; do not remove automatically.",
        "Removing a column is a structural change that may not be desired even if it currently has only one value.",
    ),
    "high_cardinality": (
        "LOW",
        "No automatic action; flag for review.",
        "High cardinality alone doesn't indicate an error; informational only.",
    ),
    "missing_required_column": (
        "LOW",
        "Flag for manual review.",
        "This column is required by the project plan but is not present in the dataset; it cannot be auto-generated.",
    ),
}

_DEFAULT_ENTRY = (
    "LOW",
    "Flag for manual review.",
    "Unrecognized issue type; defaulting to manual review for safety.",
)


def classify_issue(issue: Issue) -> ConfidenceDecision:
    confidence, action, reason = _CONFIDENCE_TABLE.get(issue.issue_type, _DEFAULT_ENTRY)
    evidence = {
        "column": issue.column,
        "affected_count": issue.affected_count,
        **issue.details,
    }
    return ConfidenceDecision(
        confidence=confidence,
        rule=issue.issue_type,
        evidence=evidence,
        action=action,
        reason=reason,
    )
