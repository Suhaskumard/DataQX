"""Phase 22 -- Security hardening tests.

Complements the path-traversal/extension/size coverage already in test_upload.py
with additional unsafe-input edge cases (absolute paths, null bytes, unicode,
extension spoofing) and checks on the security response headers and safe_join.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.utils.filesystem import safe_join
from main import app

client = TestClient(app)


def test_absolute_path_filename_is_contained(tmp_path: Path):
    content = b"a,b\n1,2\n"
    response = client.post(
        "/api/upload",
        files={"files": ("/etc/passwd.csv", content, "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    file_result = body["files"][0]
    assert file_result["status"] == "saved"

    settings = get_settings()
    saved_path = settings.input_dir / body["run_id"] / file_result["saved_name"]
    assert saved_path.parent == (settings.input_dir / body["run_id"])
    assert saved_path.exists()


def test_windows_style_absolute_path_filename_is_contained():
    content = b"a,b\n1,2\n"
    response = client.post(
        "/api/upload",
        files={"files": ("C:\\Windows\\System32\\evil.csv", content, "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    file_result = body["files"][0]
    assert file_result["status"] == "saved"

    settings = get_settings()
    saved_path = settings.input_dir / body["run_id"] / file_result["saved_name"]
    assert saved_path.parent == (settings.input_dir / body["run_id"])


def test_null_byte_in_filename_does_not_crash():
    content = b"a,b\n1,2\n"
    response = client.post(
        "/api/upload",
        files={"files": ("evil.csv\x00.exe", content, "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    file_result = body["files"][0]
    assert "\x00" not in file_result.get("saved_name", "")


def test_unicode_filename_is_sanitized_safely():
    content = b"a,b\n1,2\n"
    response = client.post(
        "/api/upload",
        files={"files": ("\u6570\u636e\U0001f600.csv", content, "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    file_result = body["files"][0]
    assert file_result["status"] == "saved"
    saved_name = file_result["saved_name"]
    assert saved_name.endswith(".csv")
    saved_name.encode("ascii")  # must not raise -- non-ASCII chars were stripped


def test_very_long_filename_does_not_crash():
    content = b"a,b\n1,2\n"
    long_name = ("a" * 500) + ".csv"
    response = client.post(
        "/api/upload",
        files={"files": (long_name, content, "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    file_result = body["files"][0]
    assert file_result["status"] in ("saved", "rejected")


def test_double_extension_spoof_rejected():
    content = b"not a real executable"
    response = client.post(
        "/api/upload",
        files={"files": ("invoice.csv.exe", content, "application/octet-stream")},
    )
    assert response.status_code == 200
    body = response.json()
    file_result = body["files"][0]
    assert file_result["status"] == "rejected"
    assert "Unsupported file type" in file_result["reason"]


def test_php_extension_rejected():
    content = b"<?php echo 'hi'; ?>"
    response = client.post(
        "/api/upload",
        files={"files": ("shell.php", content, "application/octet-stream")},
    )
    assert response.status_code == 200
    body = response.json()
    file_result = body["files"][0]
    assert file_result["status"] == "rejected"


def test_safe_join_rejects_absolute_path_argument(tmp_path: Path):
    with pytest.raises(ValueError):
        safe_join(tmp_path, "/etc/passwd")


def test_security_headers_present_on_response():
    response = client.get("/api/health")
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"


def test_unhandled_exception_returns_generic_500(monkeypatch):
    """Uses raise_server_exceptions=False: Starlette's ServerErrorMiddleware still
    re-raises the original exception to TestClient's default transport even after a
    registered handler already produced the response the real client would see."""

    def _raise():
        raise RuntimeError("boom: simulated unguarded failure")

    monkeypatch.setattr("app.api.upload.generate_run_id", _raise)

    settings = get_settings()
    error_log_path = settings.logs_dir / "errors.log"
    size_before = error_log_path.stat().st_size if error_log_path.exists() else 0

    no_raise_client = TestClient(app, raise_server_exceptions=False)
    response = no_raise_client.post(
        "/api/upload",
        files={"files": ("data.csv", b"a,b\n1,2\n", "text/csv")},
    )
    assert response.status_code == 500
    body = response.json()
    assert body == {"detail": "An unexpected error occurred."}
    assert "RuntimeError" not in response.text
    assert "Traceback" not in response.text

    assert error_log_path.exists()
    assert error_log_path.stat().st_size > size_before
