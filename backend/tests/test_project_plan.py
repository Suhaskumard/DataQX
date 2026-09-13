import pandas as pd

from app.services.project_plan import check_required_columns, load_project_plan, parse_project_plan

SAMPLE_PLAN = """# Project Plan

## Project Objective
Prepare sales data for the quarterly revenue dashboard.
Focus on the West region.

## Business Problem
Leadership needs accurate revenue numbers.

## Required Columns
- customer_id
- order_date
- revenue

## Columns That Must Not Be Modified
- customer_id
- legacy_code

## Expected Output
Cleaned CSV ready for Power BI.
"""

EMPTY_TEMPLATE = """# Project Plan

## Project Objective
_(What is this dataset being prepared for?)_

## Required Columns
-

## Columns That Must Not Be Modified
-
"""


def test_parse_project_plan_extracts_protected_and_required_columns():
    plan = parse_project_plan(SAMPLE_PLAN)

    assert plan.required_columns == ["customer_id", "order_date", "revenue"]
    assert plan.protected_columns == ["customer_id", "legacy_code"]


def test_parse_project_plan_extracts_objective():
    plan = parse_project_plan(SAMPLE_PLAN)
    assert plan.objective == "Prepare sales data for the quarterly revenue dashboard. Focus on the West region."


def test_parse_empty_template_yields_empty_lists():
    plan = parse_project_plan(EMPTY_TEMPLATE)
    assert plan.protected_columns == []
    assert plan.required_columns == []


def test_load_project_plan_returns_none_when_file_missing(tmp_path):
    assert load_project_plan(tmp_path) is None


def test_load_project_plan_reads_and_parses_file(tmp_path):
    (tmp_path / "project_plan.md").write_text(SAMPLE_PLAN, encoding="utf-8")
    plan = load_project_plan(tmp_path)
    assert plan is not None
    assert plan.required_columns == ["customer_id", "order_date", "revenue"]


def test_check_required_columns_flags_missing_column():
    df = pd.DataFrame({"customer_id": [1, 2], "order_date": ["2024-01-01", "2024-01-02"]})
    plan = parse_project_plan(SAMPLE_PLAN)  # requires customer_id, order_date, revenue

    issues = check_required_columns(df, plan)

    assert len(issues) == 1
    assert issues[0].issue_type == "missing_required_column"
    assert issues[0].details["missing_columns"] == ["revenue"]


def test_check_required_columns_no_issue_when_all_present():
    df = pd.DataFrame({"customer_id": [1], "order_date": ["2024-01-01"], "revenue": [100]})
    plan = parse_project_plan(SAMPLE_PLAN)

    issues = check_required_columns(df, plan)

    assert issues == []


def test_check_required_columns_no_issue_when_none_specified():
    df = pd.DataFrame({"a": [1]})
    plan = parse_project_plan(EMPTY_TEMPLATE)

    issues = check_required_columns(df, plan)

    assert issues == []
