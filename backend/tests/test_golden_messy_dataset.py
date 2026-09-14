"""Golden regression dataset -- end-to-end acceptance test for this hardening pass.

The exact 55-row dataset described in the original bug report (rating column, INR
currency, emails, specific duplicate-row-index pairs) does not exist anywhere in this
repository (confirmed by repo-wide search before writing this fixture). This dataset
was built to exercise the same failure classes with real, verifiable data:
recoverable-but-non-ISO dates, currency-formatted amounts, invalid emails, out-of-range
ratings, an extreme outlier, a negative amount, an exact duplicate, and two near-
duplicate pairs -- driven through the real upload -> analyze -> clean -> validate API
chain, not a mocked pipeline.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

GOLDEN_CSV = Path(__file__).resolve().parent / "fixtures" / "golden_messy_dataset.csv"


def _run_pipeline():
    with open(GOLDEN_CSV, "rb") as f:
        upload_response = client.post("/api/upload", files=[("files", ("golden.csv", f, "text/csv"))])
    assert upload_response.status_code == 200
    run_id = upload_response.json()["run_id"]

    analyze_response = client.post("/api/analyze", json={"run_id": run_id})
    assert analyze_response.status_code == 200
    issues = analyze_response.json()["files"]["golden.csv"]["issues"]

    clean_response = client.post("/api/clean", json={"run_id": run_id})
    assert clean_response.status_code == 200
    clean_result = clean_response.json()["files"]["golden.csv"]

    return issues, clean_result


def test_golden_dataset_exists():
    assert GOLDEN_CSV.exists()


def test_recoverable_dates_are_never_destroyed_to_null():
    """The core acceptance criterion: every recoverable date format in the dataset
    (ISO, month-name, unambiguous DD/MM dash-form, column-evidence-resolved ambiguous)
    must survive cleaning as a real date value, never becoming null."""
    _, clean_result = _run_pipeline()
    import pandas as pd

    output_csv = Path(__file__).resolve().parents[2] / clean_result["output_csv"]
    cleaned = pd.read_csv(output_csv)

    # Rows 1,2,3,4,7,9,13,14 (1-indexed in the fixture) all have recoverable dates.
    recoverable_row_names = [
        "Suhas Kumar", "Priya Rao", "Arjun Mehta", "Kiran Shah",
        "Rohan Verma", "Vikram Singh", "Farah Khan",
    ]
    for name in recoverable_row_names:
        rows = cleaned[cleaned["name"] == name]
        assert not rows.empty, f"row for {name} missing entirely"
        assert rows["signup_date"].notna().all(), f"{name}'s recoverable date was destroyed to null"


def test_genuinely_invalid_dates_are_flagged_and_nulled():
    issues, clean_result = _run_pipeline()
    invalid_date_issues = [i for i in issues if i["issue_type"] == "invalid_date"]
    assert invalid_date_issues, "expected an invalid_date issue for 31/02/2026 and 99/99/2026"
    assert invalid_date_issues[0]["affected_count"] >= 2


def test_currency_values_normalized_and_missing_not_fabricated():
    issues, clean_result = _run_pipeline()
    import pandas as pd

    currency_issues = [i for i in issues if i["issue_type"] == "currency_value"]
    assert currency_issues, "expected currency_value issue for '4,500'/'2499 INR'/etc."

    output_csv = Path(__file__).resolve().parents[2] / clean_result["output_csv"]
    cleaned = pd.read_csv(output_csv)

    priya = cleaned[cleaned["name"] == "Priya Rao"].iloc[0]
    assert float(priya["amount"]) == 4500.0

    rohan = cleaned[cleaned["name"] == "Rohan Verma"].iloc[0]
    # "free" is not a recognized missing-value marker and not a parseable number --
    # the safest, most conservative behavior is to leave it exactly as-is rather than
    # inventing either a null or a numeric value for it.
    assert rohan["amount"] == "free", "'free' must never be converted to a fabricated numeric amount or null"


def test_invalid_emails_detected_not_repaired():
    issues, clean_result = _run_pipeline()
    import pandas as pd

    email_issues = [i for i in issues if i["issue_type"] == "invalid_email"]
    assert email_issues
    assert email_issues[0]["affected_count"] >= 4  # arjun/kiran/gautham/divya

    output_csv = Path(__file__).resolve().parents[2] / clean_result["output_csv"]
    cleaned = pd.read_csv(output_csv)
    kiran_email = cleaned[cleaned["name"] == "Kiran Shah"].iloc[0]["email"]
    assert kiran_email == "kiran@"  # preserved verbatim, never repaired/fabricated


def test_out_of_range_rating_flagged_not_modified():
    issues, clean_result = _run_pipeline()
    import pandas as pd

    rating_issues = [i for i in issues if i["issue_type"] == "impossible_value" and i["column"] == "rating"]
    assert rating_issues
    assert rating_issues[0]["affected_count"] >= 2  # 0 and 6

    output_csv = Path(__file__).resolve().parents[2] / clean_result["output_csv"]
    cleaned = pd.read_csv(output_csv)
    divya_rating = cleaned[cleaned["name"] == "Divya Nair"].iloc[0]["rating"]
    assert int(divya_rating) == 6  # never silently capped to 5


def test_outlier_flagged_not_deleted():
    issues, clean_result = _run_pipeline()
    import pandas as pd

    outlier_issues = [i for i in issues if i["issue_type"] == "outlier"]
    assert outlier_issues

    output_csv = Path(__file__).resolve().parents[2] / clean_result["output_csv"]
    cleaned = pd.read_csv(output_csv)
    vikram = cleaned[cleaned["name"] == "Vikram Singh"]
    assert not vikram.empty, "outlier row must never be silently deleted"
    assert float(vikram.iloc[0]["amount"]) == 9999999.0


def test_exact_duplicate_removed_near_duplicates_only_flagged():
    issues, clean_result = _run_pipeline()
    import pandas as pd

    near_dup_issues = [i for i in issues if i["issue_type"] == "near_duplicate"]
    assert near_dup_issues, "expected the two near-duplicate pairs to be flagged"

    output_csv = Path(__file__).resolve().parents[2] / clean_result["output_csv"]
    cleaned = pd.read_csv(output_csv)

    # Exact duplicate (row 1 and row 11, Suhas Kumar) collapses to one row.
    assert len(cleaned[cleaned["email"] == "suhas.kumar@gmail.com"]) == 2  # original + near-dup "Suhas Kumarr", not the exact dup

    # Near-duplicates (typo'd name, different phone) must both still be present.
    assert "Suhas Kumarr" in cleaned["name"].values
    assert "Farah Khan" in cleaned["name"].values
    assert len(cleaned[cleaned["name"] == "Farah Khan"]) == 2  # both near-dup rows survive


def test_rollback_gate_not_triggered_by_this_dataset():
    """This fixture's issues are all either safely fixable or correctly left as
    unresolved LOW-confidence flags -- cleaning it should publish successfully, not
    trigger the data-loss/validation rollback gate."""
    _, clean_result = _run_pipeline()
    assert clean_result["status"] == "cleaned"
