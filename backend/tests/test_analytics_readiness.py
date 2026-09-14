import pandas as pd

from app.services.analytics_readiness import ALL_PLATFORMS, evaluate_analytics_readiness
from app.services.issue_detection import detect_issues
from app.services.platform_rules.relationships import assess_relationships
from app.services.profiling import profile_dataset


def _clean_df():
    return pd.DataFrame(
        {
            "customer_id": range(1, 21),
            "name": [f"Person {i}" for i in range(20)],
            "category": ["gold", "silver"] * 10,
            "signup_date": [f"2024-01-{(i % 28) + 1:02d}" for i in range(20)],
            "revenue": [100 + i for i in range(20)],
        }
    )


def _corrupted_df():
    df = _clean_df()
    df["revenue"] = df["revenue"].astype(object)
    df.loc[0, "customer_id"] = df.loc[1, "customer_id"]  # duplicate id
    df.loc[2, "category"] = "Gold"  # casing inconsistency
    df.loc[3, "revenue"] = "not_a_number"  # mixed type
    df.loc[4, "signup_date"] = "31/02/2024"  # invalid date
    return df


def test_default_evaluates_all_platforms():
    df = _clean_df()
    profile = profile_dataset(df)
    issues = detect_issues(df, profile)

    result = evaluate_analytics_readiness(df, profile, issues)

    assert set(result.platforms.keys()) == set(ALL_PLATFORMS)
    assert len(result.platforms) == 10


def test_selected_platforms_subset_only_evaluates_those():
    df = _clean_df()
    profile = profile_dataset(df)
    issues = detect_issues(df, profile)

    result = evaluate_analytics_readiness(df, profile, issues, selected_platforms=["power_bi", "sql"])

    assert set(result.platforms.keys()) == {"power_bi", "sql"}


def test_unknown_platform_raises():
    df = _clean_df()
    profile = profile_dataset(df)
    issues = detect_issues(df, profile)

    try:
        evaluate_analytics_readiness(df, profile, issues, selected_platforms=["not_a_real_platform"])
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "not_a_real_platform" in str(exc)


def test_corrupted_dataset_scores_lower_than_clean_dataset_for_every_platform():
    clean_df = _clean_df()
    clean_profile = profile_dataset(clean_df)
    clean_issues = detect_issues(clean_df, clean_profile)
    clean_result = evaluate_analytics_readiness(clean_df, clean_profile, clean_issues)

    corrupted_df = _corrupted_df()
    corrupted_profile = profile_dataset(corrupted_df)
    corrupted_issues = detect_issues(corrupted_df, corrupted_profile)
    corrupted_result = evaluate_analytics_readiness(corrupted_df, corrupted_profile, corrupted_issues)

    assert corrupted_result.overall_score < clean_result.overall_score
    for name in ALL_PLATFORMS:
        assert corrupted_result.platforms[name].score <= clean_result.platforms[name].score


def test_relationship_check_only_passed_to_platforms_that_use_it():
    customers = pd.DataFrame({"customer_id": range(1, 21)})
    orders = pd.DataFrame({"order_id": range(1, 6), "customer_id": [1, 2, 3, 4, 999]})
    files = {
        "customers.csv": (customers, profile_dataset(customers)),
        "orders.csv": (orders, profile_dataset(orders)),
    }
    relationship_results = assess_relationships(files)

    orders_profile = files["orders.csv"][1]
    orders_issues = detect_issues(orders, orders_profile)
    result = evaluate_analytics_readiness(
        orders, orders_profile, orders_issues, relationship_check=relationship_results["orders.csv"]
    )

    assert any(c.check_name == "foreign_key_relationships" for c in result.platforms["power_bi"].checks)
    assert any(c.check_name == "foreign_key_relationships" for c in result.platforms["sql"].checks)
    # Excel doesn't interpret cross-file relationships -- it must not receive the check.
    assert not any(c.check_name == "foreign_key_relationships" for c in result.platforms["excel"].checks)
