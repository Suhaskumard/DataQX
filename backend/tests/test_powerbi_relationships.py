import pandas as pd

from app.services.powerbi import assess_relationships
from app.services.profiling import profile_dataset


def test_single_file_run_is_not_applicable():
    df = pd.DataFrame({"id": range(1, 21)})
    profile = profile_dataset(df)

    results = assess_relationships({"data.csv": (df, profile)})

    assert results["data.csv"].status == "not_applicable"


def test_two_files_with_orphan_foreign_key_warns():
    customers = pd.DataFrame({"customer_id": range(1, 21)})
    orders = pd.DataFrame({"order_id": range(1, 6), "customer_id": [1, 2, 3, 4, 999]})  # 999 is orphan

    files = {
        "customers.csv": (customers, profile_dataset(customers)),
        "orders.csv": (orders, profile_dataset(orders)),
    }

    results = assess_relationships(files)

    assert results["orders.csv"].status == "warning"
    finding = results["orders.csv"].details["findings"]["customer_id"]
    assert finding["references"] == "customers.csv"
    assert finding["orphan_count"] == 1
    assert "999" in finding["orphan_examples"]


def test_two_files_with_all_keys_resolving_passes():
    customers = pd.DataFrame({"customer_id": range(1, 21)})
    orders = pd.DataFrame({"order_id": range(1, 6), "customer_id": [1, 2, 3, 4, 5]})

    files = {
        "customers.csv": (customers, profile_dataset(customers)),
        "orders.csv": (orders, profile_dataset(orders)),
    }

    results = assess_relationships(files)

    assert results["orders.csv"].status == "pass"
    assert results["customers.csv"].status == "pass"
