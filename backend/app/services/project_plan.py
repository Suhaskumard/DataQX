"""Project Plan Integration (DATAQX.pdf S11/S12).

Parses a user-provided project_plan.md and makes cleaning project-aware: explicit
project requirements outrank generic cleaning rules (S12's own priority order).
Only the fields with a defined cleaning-time effect are given real behavior here --
protected columns (never modified) and required columns (flagged if missing). Other
S11 fields are parsed for future phases but have no effect yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from app.services.issue_detection import Issue

_PROTECTED_COLUMNS_HEADER = "columns that must not be modified"
_REQUIRED_COLUMNS_HEADER = "required columns"
_OBJECTIVE_HEADER = "project objective"


@dataclass
class ProjectPlan:
    objective: str | None = None
    protected_columns: list[str] = field(default_factory=list)
    required_columns: list[str] = field(default_factory=list)
    raw_text: str = ""


def parse_project_plan(text: str) -> ProjectPlan:
    protected_columns: list[str] = []
    required_columns: list[str] = []
    objective_lines: list[str] = []
    current_section: str | None = None

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            # Tolerate minor real-world header variations ("Required Columns:",
            # "Required Columns -") -- an exact-match-only comparison here silently
            # disabled an entire section with no warning whenever a user's heading
            # didn't match byte-for-byte, discarding data the user explicitly provided.
            current_section = stripped.lstrip("#").strip().rstrip(":-").strip().lower()
            continue
        if not stripped:
            continue

        if stripped.startswith("-"):
            item = stripped.lstrip("-").strip()
            if not item:
                continue
            if current_section == _PROTECTED_COLUMNS_HEADER:
                protected_columns.append(item)
            elif current_section == _REQUIRED_COLUMNS_HEADER:
                required_columns.append(item)
            elif current_section == _OBJECTIVE_HEADER:
                # A bulleted objective ("- Prepare data for dashboard") must still
                # count as objective text, not be silently dropped.
                objective_lines.append(item)
        elif current_section == _OBJECTIVE_HEADER:
            objective_lines.append(stripped)

    objective = " ".join(objective_lines) if objective_lines else None
    return ProjectPlan(
        objective=objective,
        protected_columns=protected_columns,
        required_columns=required_columns,
        raw_text=text,
    )


def load_project_plan(run_dir: Path) -> ProjectPlan | None:
    plan_path = run_dir / "project_plan.md"
    if not plan_path.exists():
        return None
    raw_bytes = plan_path.read_bytes()
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        # A plan pasted from Word/Excel is often saved as Windows-1252, not UTF-8
        # (smart quotes, em-dashes). Degrade gracefully instead of crashing the run.
        text = raw_bytes.decode("cp1252", errors="replace")
    return parse_project_plan(text)


def check_required_columns(df: pd.DataFrame, plan: ProjectPlan) -> list[Issue]:
    if not plan.required_columns:
        return []

    # Case/whitespace-insensitive: a plan requiring "Customer_ID" is satisfied by a
    # real column named "customer_id" -- matching cleaning.py's protected-column
    # normalization so the same plan is interpreted consistently everywhere.
    normalized_present = {str(c).strip().casefold() for c in df.columns}
    missing = [c for c in plan.required_columns if c.strip().casefold() not in normalized_present]
    if not missing:
        return []

    return [
        Issue(
            issue_type="missing_required_column",
            column=None,
            severity="high",
            affected_count=len(missing),
            description=f"Required column(s) from the project plan are missing from the dataset: {missing}.",
            details={"missing_columns": missing},
        )
    ]
