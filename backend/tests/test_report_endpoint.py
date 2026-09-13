import io
import json

from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.core.config import get_settings
from main import app

client = TestClient(app)


def _upload(content: bytes, filename: str) -> str:
    response = client.post("/api/upload", files={"files": (filename, content, "text/csv")})
    assert response.status_code == 200
    return response.json()["run_id"]


def test_report_endpoint_returns_real_pdf_matching_run_artifacts():
    content = b"customer_id,status,age\n1,active,25\n2,active,30\n3,N/A,-5\n4,inactive,40\n"
    run_id = _upload(content, "broken.csv")

    client.post("/api/analyze", json={"run_id": run_id})
    client.post("/api/clean", json={"run_id": run_id})
    client.post("/api/validate", json={"run_id": run_id})

    response = client.get(f"/api/report/{run_id}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:4] == b"%PDF"

    settings = get_settings()
    report_path = settings.runs_dir / run_id / "DataQX_Report.pdf"
    assert report_path.exists()
    assert report_path.read_bytes() == response.content

    reader = PdfReader(io.BytesIO(response.content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert "broken.csv" in text
    assert run_id in text

    quality = json.loads((settings.runs_dir / run_id / "quality_report.json").read_text(encoding="utf-8"))
    after_score = quality["files"]["broken.csv"]["after"]["overall_score"]
    assert f"{after_score}/100" in text

    issues = json.loads((settings.runs_dir / run_id / "issues.json").read_text(encoding="utf-8"))
    assert any(i["issue_type"] == "impossible_value" for i in issues["files"]["broken.csv"])
    assert "impossible_value" in text


def test_report_endpoint_404_for_run_never_analyzed():
    run_id = _upload(b"a,b\n1,2\n", "data.csv")
    response = client.get(f"/api/report/{run_id}")
    assert response.status_code == 404


def test_report_endpoint_404_for_nonexistent_run():
    response = client.get("/api/report/run_does_not_exist")
    assert response.status_code == 404
