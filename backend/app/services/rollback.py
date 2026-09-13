"""Validation Gates & Rollback (DATAQX.pdf S36/S37).

Turns Phase 11's ValidationReport.overall_status into an actual publish/don't-publish
decision. A FAIL means the cleaned result must not be published as the final dataset
("DO NOT PUBLISH BAD OUTPUT"). In this stateless, raw-never-touched architecture,
"rollback" means the run simply never produces a published artifact -- there is
nothing else to revert, since the raw input was never modified to begin with.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from app.services.validation import ValidationReport, validate_dataset


@dataclass
class GateResult:
    published: bool
    validation_report: ValidationReport
    reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "published": self.published,
            "validation_report": self.validation_report.to_dict(),
            "reason": self.reason,
        }


def evaluate_gate(cleaned_df: pd.DataFrame) -> GateResult:
    report = validate_dataset(cleaned_df)

    if report.overall_status == "fail":
        failed_checks = [c for c in report.checks if c.status == "fail"]
        reason = "Validation failed: " + "; ".join(f"{c.check_name} - {c.message}" for c in failed_checks)
        return GateResult(published=False, validation_report=report, reason=reason)

    return GateResult(published=True, validation_report=report, reason=None)
