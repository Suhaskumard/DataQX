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


def test_header_with_trailing_colon_still_matches():
    plan_text = """# Project Plan

## Required Columns:
- customer_id

## Columns That Must Not Be Modified:
- legacy_code
"""
    plan = parse_project_plan(plan_text)
    assert plan.required_columns == ["customer_id"]
    assert plan.protected_columns == ["legacy_code"]


def test_bulleted_objective_is_not_silently_dropped():
    plan_text = """# Project Plan

## Project Objective
- Prepare data for dashboard
- Focus on Q1
"""
    plan = parse_project_plan(plan_text)
    assert plan.objective == "Prepare data for dashboard Focus on Q1"


def test_load_project_plan_falls_back_to_cp1252_on_non_utf8_file(tmp_path):
    # A plan pasted from Word often contains a right single quotation mark (U+2019),
    # which in cp1252 encodes as byte 0x92 -- invalid as UTF-8.
    plan_text = "# Project Plan\n\n## Project Objective\nClient’s Q1 dashboard prep.\n"
    (tmp_path / "project_plan.md").write_bytes(plan_text.encode("cp1252"))

    plan = load_project_plan(tmp_path)

    assert plan is not None
    assert "Q1 dashboard prep" in plan.objective


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


def test_check_required_columns_matches_case_and_whitespace_insensitively():
    # SAMPLE_PLAN requires customer_id, order_date, revenue (lowercase, exact) --
    # a dataframe with differently-cased real columns must still satisfy the plan.
    df = pd.DataFrame({"Customer_ID": [1], "Order_Date": ["2024-01-01"], "REVENUE": [100]})
    plan = parse_project_plan(SAMPLE_PLAN)

    issues = check_required_columns(df, plan)

    assert issues == []


def test_check_required_columns_no_issue_when_none_specified():
    df = pd.DataFrame({"a": [1]})
    plan = parse_project_plan(EMPTY_TEMPLATE)

    issues = check_required_columns(df, plan)

    assert issues == []
