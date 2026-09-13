import json

from fastapi.testclient import TestClient

from app.core.config import get_settings
from main import app

client = TestClient(app)

SAME_CONTENT = b"customer_id,status,notes\n1,active,normal\n2,active,normal\n3,N/A,normal\n4,inactive,normal\n"

PROTECTING_PLAN = """# Project Plan

## Columns That Must Not Be Modified
- status
"""


def _upload(content: bytes, filename: str, project_plan_text: str | None = None) -> str:
    data = {}
    if project_plan_text is not None:
        data["project_plan_text"] = project_plan_text
    response = client.post(
        "/api/upload",
        files={"files": (filename, content, "text/csv")},
        data=data,
    )
    assert response.status_code == 200
    return response.json()["run_id"]


def test_same_dataset_different_project_plans_produce_different_cleaning():
    # Run A: no project plan -- normal cleaning behavior.
    run_id_a = _upload(SAME_CONTENT, "data.csv")
    client.post("/api/analyze", json={"run_id": run_id_a})
    clean_a = client.post("/api/clean", json={"run_id": run_id_a}).json()

    # Run B: project plan protects "status" -- the placeholder must survive cleaning.
    run_id_b = _upload(SAME_CONTENT, "data.csv", project_plan_text=PROTECTING_PLAN)
    client.post("/api/analyze", json={"run_id": run_id_b})
    clean_b = client.post("/api/clean", json={"run_id": run_id_b}).json()

    settings = get_settings()

    path_a = settings.repo_root / clean_a["files"]["data.csv"]["output_csv"]
    path_b = settings.repo_root / clean_b["files"]["data.csv"]["output_csv"]

    text_a = path_a.read_text(encoding="utf-8")
    text_b = path_b.read_text(encoding="utf-8")

    # Same input, different output: A cleaned the placeholder away, B protected it.
    assert "N/A" not in text_a
    assert "N/A" in text_b
    assert text_a != text_b

    assert clean_b["files"]["data.csv"]["skipped_low_confidence"] >= 0  # sanity: response shape intact


def test_missing_required_column_flagged_by_analyze():
    plan_text = """# Project Plan

## Required Columns
- customer_id
- email
"""
    run_id = _upload(b"customer_id,status\n1,active\n2,active\n", "data.csv", project_plan_text=plan_text)

    response = client.post("/api/analyze", json={"run_id": run_id})
    assert response.status_code == 200
    body = response.json()

    issue_types = {i["issue_type"] for i in body["files"]["data.csv"]["issues"]}
    assert "missing_required_column" in issue_types

    missing_issue = next(
        i for i in body["files"]["data.csv"]["issues"] if i["issue_type"] == "missing_required_column"
    )
    assert missing_issue["details"]["missing_columns"] == ["email"]
    assert missing_issue["confidence"]["confidence"] == "LOW"

    settings = get_settings()
    on_disk = json.loads((settings.runs_dir / run_id / "issues.json").read_text(encoding="utf-8"))
    disk_issue_types = {i["issue_type"] for i in on_disk["files"]["data.csv"]}
    assert "missing_required_column" in disk_issue_types


def test_no_project_plan_means_no_required_column_check():
    run_id = _upload(b"a,b\n1,2\n", "data.csv")  # no project_plan_text

    response = client.post("/api/analyze", json={"run_id": run_id})
    issue_types = {i["issue_type"] for i in response.json()["files"]["data.csv"]["issues"]}
    assert "missing_required_column" not in issue_types
