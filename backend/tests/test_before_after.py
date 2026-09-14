import pandas as pd

from app.services.before_after import SnapshotMetrics, build_before_after_summary, build_snapshot_metrics
from app.services.issue_detection import detect_issues
from app.services.profiling import profile_dataset


def test_build_before_after_summary_exact_values():
    before = SnapshotMetrics(
        row_count=100, column_count=5, missing_values=20, duplicate_rows=3, duplicate_ids=1,
        invalid_values=4, invalid_dates=2, outliers=1, quality_score=72.0, analytics_readiness=60.0,
    )
    after = SnapshotMetrics(
        row_count=98, column_count=5, missing_values=5, duplicate_rows=0, duplicate_ids=0,
        invalid_values=1, invalid_dates=0, outliers=1, quality_score=94.0, analytics_readiness=85.0,
    )

    summary = build_before_after_summary(before, after)

    assert summary["row_count"] == {"before": 100, "after": 98, "change": -2}
    assert summary["missing_values"] == {"before": 20, "after": 5, "change": -15}
    assert summary["duplicate_rows"] == {"before": 3, "after": 0, "change": -3}
    assert summary["quality_score"] == {"before": 72.0, "after": 94.0, "change": 22.0}
    assert summary["outliers"] == {"before": 1, "after": 1, "change": 0}


def test_build_snapshot_metrics_from_real_data():
    df = pd.DataFrame(
        {
            "customer_id": list(range(1, 20)) + [19],  # 1 duplicate id
            "status": ["active"] * 18 + ["N/A", "inactive"],
        }
    )
    profile = profile_dataset(df)
    issues = detect_issues(df, profile)

    snapshot = build_snapshot_metrics(df, profile, issues, quality_score=80.0, analytics_readiness=70.0)

    assert snapshot.row_count == 20
    assert snapshot.duplicate_ids == 1
    assert snapshot.missing_values == sum(c.missing_count for c in profile.columns)
    assert snapshot.quality_score == 80.0
    assert snapshot.analytics_readiness == 70.0
