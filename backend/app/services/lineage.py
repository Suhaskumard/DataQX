"""Data Lineage (DATAQX.pdf S32).

Tracks RAW COLUMN -> TRANSFORMATION -> CLEAN COLUMN for every output column, built
directly from the Cleaning Engine's own log (Phase 8) -- not a new detection or
cleaning mechanism, just a column-level view of the same recorded work.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.services.cleaning import CleaningLogEntry


@dataclass
class LineageEntry:
    lineage_id: str
    source_dataset: str
    source_column: str
    output_column: str | None
    transformation: str
    rule: str | None
    reason: str | None
    confidence: str | None

    def to_dict(self) -> dict:
        return asdict(self)


def build_lineage(
    dataset_name: str,
    original_columns: list[str],
    cleaned_columns: list[str],
    cleaning_log: list[CleaningLogEntry],
) -> list[LineageEntry]:
    cleaned_set = set(cleaned_columns)
    # Column-level entries only -- row-level operations like duplicate_rows have
    # Issue.column == None and aren't a column-to-column transformation.
    entries_by_column: dict[str, list[CleaningLogEntry]] = {}
    for entry in cleaning_log:
        if entry.column is not None:
            entries_by_column.setdefault(entry.column, []).append(entry)

    lineage: list[LineageEntry] = []
    counter = 0

    for column in original_columns:
        column_entries = entries_by_column.get(column, [])

        if column not in cleaned_set:
            counter += 1
            drop_entry = next((e for e in column_entries if e.issue_type == "empty_column"), None)
            lineage.append(
                LineageEntry(
                    lineage_id=f"lineage_{counter:03d}",
                    source_dataset=dataset_name,
                    source_column=column,
                    output_column=None,
                    transformation="dropped_empty_column",
                    rule=drop_entry.rule if drop_entry else None,
                    reason=drop_entry.reason if drop_entry else None,
                    confidence=drop_entry.confidence if drop_entry else None,
                )
            )
            continue

        if not column_entries:
            counter += 1
            lineage.append(
                LineageEntry(
                    lineage_id=f"lineage_{counter:03d}",
                    source_dataset=dataset_name,
                    source_column=column,
                    output_column=column,
                    transformation="unchanged",
                    rule=None,
                    reason="No issues detected requiring transformation.",
                    confidence=None,
                )
            )
            continue

        for entry in column_entries:
            counter += 1
            lineage.append(
                LineageEntry(
                    lineage_id=f"lineage_{counter:03d}",
                    source_dataset=dataset_name,
                    source_column=column,
                    output_column=column,
                    transformation=entry.action_taken,
                    rule=entry.rule,
                    reason=entry.reason,
                    confidence=entry.confidence,
                )
            )

    return lineage
