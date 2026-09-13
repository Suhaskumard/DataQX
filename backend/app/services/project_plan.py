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
            current_section = stripped.lstrip("#").strip().lower()
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
    return parse_project_plan(plan_path.read_text(encoding="utf-8"))


def check_required_columns(df: pd.DataFrame, plan: ProjectPlan) -> list[Issue]:
    if not plan.required_columns:
        return []

    missing = [c for c in plan.required_columns if c not in df.columns]
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
