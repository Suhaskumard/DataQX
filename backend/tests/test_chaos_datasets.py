"""Phase 25 -- Combinatorial chaos testing.

Each dataset below deliberately combines multiple simultaneous defects (rather than
testing one issue type in isolation, as the rest of the suite does) and is run
through the real upload -> analyze -> clean -> validate chain. The only universal
assertion is "no unhandled crash, and the response shape stays sane" -- these are
adversarial inputs designed to probe combinations no single-issue test would surface,
not to pin exact detected-issue counts (which would make the suite brittle for no
real benefit).
"""

from __future__ import annotations

import csv
import io
import random
import string

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _run_full_chain(filename: str, content: bytes):
    upload_response = client.post("/api/upload", files={"files": (filename, content, "text/csv")})
    assert upload_response.status_code == 200
    run_id = upload_response.json()["run_id"]

    file_result = upload_response.json()["files"][0]
    if file_result["status"] != "saved":
        return run_id, None, None, None  # rejected at upload -- nothing further to chain

    analyze_response = client.post("/api/analyze", json={"run_id": run_id})
    assert analyze_response.status_code in (200, 404)
    if analyze_response.status_code != 200:
        return run_id, analyze_response, None, None

    clean_response = client.post("/api/clean", json={"run_id": run_id})
    assert clean_response.status_code == 200

    validate_response = client.post("/api/validate", json={"run_id": run_id})
    assert validate_response.status_code == 200

    return run_id, analyze_response, clean_response, validate_response


# --- Dataset A: large, multi-defect ---------------------------------------------


def test_dataset_a_large_multi_defect_survives_full_pipeline():
    random.seed(1)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "name", "category", "amount", "signup_date"])
    categories = ["North", "South", "east", "EAST", "West", "unknown"]
    for i in range(1, 10_001):
        name = f"Customer {i}" if i % 13 != 0 else f"  Customer {i}  "
        amount = random.choice([10, 20, "N/A", -999999, "1,000"])
        date = "2024-01-15" if i % 7 != 0 else "31/02/2024"
        writer.writerow([i if i % 500 != 0 else i - 1, name, random.choice(categories), amount, date])
    content = buf.getvalue().encode("utf-8")

    _run_full_chain("dataset_a.csv", content)


# --- Dataset B: every column partially corrupted --------------------------------


def test_dataset_b_all_columns_corrupted_survives_full_pipeline():
    rows = [["a", "b", "c", "d"]]
    for i in range(200):
        rows.append(
            [
                "" if i % 5 == 0 else str(i),
                "N/A" if i % 4 == 0 else f"val_{i}",
                "abc" if i % 6 == 0 else str(i * 1.5),
                "31/02/2024" if i % 8 == 0 else "2024-01-01",
            ]
        )
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    _run_full_chain("dataset_b.csv", buf.getvalue().encode("utf-8"))


# --- Dataset C: extremely high cardinality --------------------------------------


def test_dataset_c_extreme_high_cardinality_survives_full_pipeline():
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "unique_token"])
    for i in range(5000):
        token = "".join(random.choices(string.ascii_letters + string.digits, k=32))
        writer.writerow([i, token])
    _run_full_chain("dataset_c.csv", buf.getvalue().encode("utf-8"))


# --- Dataset D: mostly empty -----------------------------------------------------


def test_dataset_d_mostly_empty_survives_full_pipeline():
    rows = [["id", "a", "b", "c"]] + [[str(i), "", "", ""] for i in range(50)]
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    _run_full_chain("dataset_d.csv", buf.getvalue().encode("utf-8"))


# --- Dataset E: one row ----------------------------------------------------------


def test_dataset_e_single_row_survives_full_pipeline():
    content = b"id,name,amount\n1,Alice,100\n"
    _run_full_chain("dataset_e.csv", content)


# --- Dataset F: extremely wide ----------------------------------------------------


def test_dataset_f_extremely_wide_survives_full_pipeline():
    n_cols = 300
    header = [f"col_{i}" for i in range(n_cols)]
    rows = [header] + [[str(i * j) for j in range(n_cols)] for i in range(20)]
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    _run_full_chain("dataset_f.csv", buf.getvalue().encode("utf-8"))


# --- Dataset G: very long text fields ---------------------------------------------


def test_dataset_g_long_text_fields_survives_full_pipeline():
    long_text = "lorem ipsum " * 2000  # ~24k characters, no internal newlines
    rows = [["id", "notes"]] + [[str(i), long_text] for i in range(10)]
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    _run_full_chain("dataset_g.csv", buf.getvalue().encode("utf-8"))


# --- Dataset H: Unicode / multilingual ---------------------------------------------


def test_dataset_h_unicode_multilingual_survives_full_pipeline():
    rows = [
        ["id", "name", "notes"],
        [1, "éèê François", "café naïve"],
        [2, "中文名字", "测试数据"],
        [3, "محمد", "اختبار"],
        [4, "\U0001f600 emoji name", "notes with \U0001f4ca emoji"],
        [5, "Россия", "тест"],
    ]
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    _run_full_chain("dataset_h.csv", buf.getvalue().encode("utf-8"))


# --- Dataset I: multi-file with orphan foreign keys ---------------------------------


def test_dataset_i_multi_file_with_orphans_survives_full_pipeline():
    customers_content = b"customer_id,name\n1,Alice\n2,Bob\n3,Carol\n"
    orders_content = b"order_id,customer_id\n101,1\n102,999\n103,2\n"

    upload_response = client.post(
        "/api/upload",
        files=[
            ("files", ("customers.csv", customers_content, "text/csv")),
            ("files", ("orders.csv", orders_content, "text/csv")),
        ],
    )
    assert upload_response.status_code == 200
    run_id = upload_response.json()["run_id"]

    assert client.post("/api/analyze", json={"run_id": run_id}).status_code == 200
    assert client.post("/api/clean", json={"run_id": run_id}).status_code == 200
    assert client.post("/api/validate", json={"run_id": run_id}).status_code == 200

    readiness = client.get(f"/api/analytics-readiness/{run_id}").json()
    powerbi_checks = readiness["files"]["orders.csv"]["platforms"]["power_bi"]["checks"]
    fk_check = next(c for c in powerbi_checks if c["check_name"] == "foreign_key_relationships")
    assert fk_check["status"] == "warning"


# --- Dataset J: adversarial malformed ---------------------------------------------


def test_dataset_j_adversarial_malformed_never_crashes_the_api():
    adversarial_payloads = [
        b"\x00\x01\x02\x03 not a real csv at all \xff\xfe",
        b"a,b,c\n1,2\n3,4,5,6\n,,,\n",  # inconsistent column counts + all-empty row
        ("a,b\n" + "x" * 100_000 + ",1\n").encode(),  # one absurdly long field
        b",,,\n,,,\n",  # empty headers
        b"a,a,a\n1,2,3\n",  # duplicate column names
    ]
    for i, payload in enumerate(adversarial_payloads):
        run_id, analyze_resp, clean_resp, validate_resp = _run_full_chain(f"adversarial_{i}.csv", payload)
        # The only universal contract: never an unhandled 500 anywhere in the chain.
        for resp in (analyze_resp, clean_resp, validate_resp):
            if resp is not None:
                assert resp.status_code != 500
