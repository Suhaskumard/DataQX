"""Audit Logging (DATAQX.pdf S33).

Builds file-based audit/cleaning log rows -- no database. `audit_log.csv` covers every
issue encountered (applied or flagged for review); `cleaning_log.csv` covers only the
subset that was actually applied. Per S33's own caution, a large number of affected
rows is aggregated into a single summary row rather than emitted individually.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from app.services.cleaning import CleaningLogEntry
from app.services.issue_detection import Issue

AUDIT_COLUMNS = [
    "timestamp",
    "run_id",
    "dataset",
    "column",
    "row_reference",
    "issue_type",
    "original_value",
    "new_value",
    "action",
    "rule",
    "reason",
    "confidence",
    "severity",
    "status",
]

# Below this many affected rows, log one row per change; at/above it, aggregate into
# a single summary row so a large dataset never generates millions of log rows.
ROW_DETAIL_LIMIT = 50


def _rows_for_applied_entry(run_id: str, dataset_name: str, issue: Issue, entry: CleaningLogEntry, timestamp: str) -> list[dict]:
    changes = entry.changes
    base = {
        "timestamp": timestamp,
        "run_id": run_id,
        "dataset": dataset_name,
        "column": entry.column,
        "issue_type": entry.issue_type,
        "action": entry.action_taken,
        "rule": entry.rule,
        "reason": entry.reason,
        "confidence": entry.confidence,
        "severity": issue.severity,
        "status": "applied",
    }

    if not changes:
        return [{**base, "row_reference": None, "original_value": None, "new_value": None}]

    if len(changes) < ROW_DETAIL_LIMIT:
        return [
            {
                **base,
                "row_reference": change["row_index"],
                "original_value": change["original_value"],
                "new_value": change["new_value"],
            }
            for change in changes
        ]

    first = changes[0]
    return [
        {
            **base,
            "row_reference": f"{len(changes)} rows (aggregated)",
            "original_value": first["original_value"],
            "new_value": first["new_value"],
        }
    ]


def _row_for_skipped_issue(run_id: str, dataset_name: str, issue: Issue, timestamp: str) -> dict:
    return {
        "timestamp": timestamp,
        "run_id": run_id,
        "dataset": dataset_name,
        "column": issue.column,
        "row_reference": None,
        "issue_type": issue.issue_type,
        "original_value": None,
        "new_value": None,
        "action": "Flag for manual review.",
        "rule": issue.issue_type,
        "reason": issue.description,
        "confidence": "LOW",
        "severity": issue.severity,
        "status": "flagged_for_review",
    }


def build_log_rows(
    run_id: str,
    dataset_name: str,
    issues: list[Issue],
    cleaning_log: list[CleaningLogEntry],
) -> tuple[list[dict], list[dict]]:
    """Return (audit_rows, cleaning_rows) for one file's analysis+cleaning results."""
    timestamp = datetime.now(timezone.utc).isoformat()

    # Match applied cleaning entries back to their originating issue by (issue_type, column).
    applied_by_key = {(entry.issue_type, entry.column): entry for entry in cleaning_log}

    audit_rows: list[dict] = []
    cleaning_rows: list[dict] = []

    for issue in issues:
        key = (issue.issue_type, issue.column)
        entry = applied_by_key.get(key)
        if entry is not None:
            rows = _rows_for_applied_entry(run_id, dataset_name, issue, entry, timestamp)
            audit_rows.extend(rows)
            cleaning_rows.extend(rows)
        else:
            audit_rows.append(_row_for_skipped_issue(run_id, dataset_name, issue, timestamp))

    return audit_rows, cleaning_rows


def append_rows_to_csv(path: Path, rows: list[dict], columns: list[str] = AUDIT_COLUMNS) -> None:
    """Append rows to a CSV file, writing the header only if the file doesn't exist yet.

    A no-op if `rows` is empty -- never creates or touches the file for nothing to log.
    """
    if not rows:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists() and path.stat().st_size > 0

    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        if not file_exists:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)
