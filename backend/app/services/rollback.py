"""Validation Gates & Rollback (DATAQX.pdf S36/S37).

Turns Phase 11's ValidationReport.overall_status into an actual publish/don't-publish
decision. A FAIL means the cleaned result must not be published as the final dataset
("DO NOT PUBLISH BAD OUTPUT"). In this stateless, raw-never-touched architecture,
"rollback" means the run simply never produces a published artifact -- there is
nothing else to revert, since the raw input was never modified to begin with.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.services.profiling import DatasetProfile
from app.services.validation import ValidationReport, validate_dataset


@dataclass
class GateResult:
    published: bool
    validation_report: ValidationReport
    reason: str | None = None
    data_loss_findings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "published": self.published,
            "validation_report": self.validation_report.to_dict(),
            "reason": self.reason,
            "data_loss_findings": self.data_loss_findings,
        }


_RATE_TOLERANCE = 1e-9


def detect_data_loss(before_profile: DatasetProfile, after_profile: DatasetProfile) -> list[str]:
    """Compare before/after profiles for unexplained destruction of recoverable data.

    Uses the *rate* of valid dates among present values, not raw counts, because the
    row count itself can legitimately shrink during cleaning (exact-duplicate removal
    is lossless -- it removes a row that is byte-identical to one still present). A
    drop in raw valid-date count from that alone must not be mistaken for data loss;
    a drop in the *rate* means a value that used to parse no longer does, which is
    exactly the failure class this exists to catch."""
    findings: list[str] = []

    after_columns = {c.original_name: c for c in after_profile.columns}
    for before_col in before_profile.columns:
        after_col = after_columns.get(before_col.original_name)
        if after_col is None or not before_col.date_extra or not after_col.date_extra:
            continue

        if before_profile.row_count <= 0:
            continue

        # "Bad" = missing OR invalid. Both sides are measured against the SAME
        # denominator (before_profile.row_count) rather than each side's own row
        # count, specifically so that exact-duplicate row removal -- which can only
        # ever REMOVE rows, never add a new missing/invalid value -- can't inflate the
        # rate purely by shrinking the denominator. Only an actual increase in the raw
        # count of missing/invalid values trips this check.
        before_bad = before_col.missing_count + before_col.date_extra.get("invalid_count", 0)
        after_bad = after_col.missing_count + after_col.date_extra.get("invalid_count", 0)
        before_rate = before_bad / before_profile.row_count
        after_rate = after_bad / before_profile.row_count

        if after_rate > before_rate + _RATE_TOLERANCE:
            findings.append(
                f"Column '{before_col.original_name}': missing/invalid date count rose from "
                f"{before_bad} to {after_bad} during cleaning -- recoverable dates must never be destroyed."
            )

    return findings


def evaluate_gate(
    cleaned_df: pd.DataFrame,
    before_profile: DatasetProfile | None = None,
    after_profile: DatasetProfile | None = None,
) -> GateResult:
    report = validate_dataset(cleaned_df)

    data_loss_findings: list[str] = []
    if before_profile is not None and after_profile is not None:
        data_loss_findings = detect_data_loss(before_profile, after_profile)

    if report.overall_status == "fail":
        failed_checks = [c for c in report.checks if c.status == "fail"]
        reason = "Validation failed: " + "; ".join(f"{c.check_name} - {c.message}" for c in failed_checks)
        return GateResult(published=False, validation_report=report, reason=reason, data_loss_findings=data_loss_findings)

    if data_loss_findings:
        reason = "Data-loss regression detected: " + "; ".join(data_loss_findings)
        return GateResult(published=False, validation_report=report, reason=reason, data_loss_findings=data_loss_findings)

    return GateResult(published=True, validation_report=report, reason=None, data_loss_findings=data_loss_findings)
