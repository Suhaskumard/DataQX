"""Qlik Sense / Qlik Cloud readiness (DATAQX Phase 16). Readiness assessment
only -- never claims official Qlik certification."""

from __future__ import annotations

import pandas as pd

from app.services.issue_detection import Issue
from app.services.platform_rules.common import PlatformCheck, PlatformResult, build_result
from app.services.profiling import DatasetProfile
from app.services.semantic_roles import ColumnRole, columns_with_role

_SYNTHETIC_KEY_CARDINALITY_THRESHOLD = 90.0


def evaluate(
    df: pd.DataFrame,
    profile: DatasetProfile,
    issues: list[Issue],
    roles: list[ColumnRole],
    relationship_check: PlatformCheck | None = None,
) -> PlatformResult:
    checks: list[PlatformCheck] = []
    recommendations: list[str] = []

    duplicate_id_issues = [i for i in issues if i.issue_type == "duplicate_id"]
    if duplicate_id_issues:
        checks.append(
            PlatformCheck(
                "key_consistency", "fail",
                f"Duplicate key value(s) in: {[i.column for i in duplicate_id_issues]}.",
                {"columns": [i.column for i in duplicate_id_issues]},
            )
        )
        recommendations.append("Deduplicate key fields before Qlik builds its associative data model on them.")
    else:
        checks.append(PlatformCheck("key_consistency", "pass", "All key columns are unique."))

    key_columns = columns_with_role(roles, "primary_key")
    fk_candidates = [c for c in df.columns if str(c).lower().endswith("_id") and c not in key_columns]
    checks.append(
        PlatformCheck(
            "field_naming", "pass" if not fk_candidates or key_columns else "warning",
            f"Key candidate field(s): {key_columns}; potential link field(s): {fk_candidates}.",
            {"key_columns": key_columns, "link_fields": fk_candidates},
        )
    )

    if relationship_check is not None:
        checks.append(relationship_check)

    high_cardinality_key_like = [
        c.original_name for c in profile.columns
        if c.original_name in fk_candidates and c.unique_percentage >= _SYNTHETIC_KEY_CARDINALITY_THRESHOLD
    ]
    if len(fk_candidates) >= 2 and high_cardinality_key_like:
        checks.append(
            PlatformCheck(
                "synthetic_key_risk", "warning",
                f"Multiple near-unique link field(s) {high_cardinality_key_like} increase the risk of Qlik "
                "auto-generating a synthetic key across tables.",
                {"columns": high_cardinality_key_like},
            )
        )
        recommendations.append("Rename or explicitly qualify link fields to avoid an unintended synthetic key.")
    else:
        checks.append(PlatformCheck("synthetic_key_risk", "pass", "No obvious synthetic-key risk detected."))

    # A genuine circular-relationship check needs the full multi-file join graph,
    # which this single-file evaluation does not have -- report honestly rather
    # than fabricate a result the data available here cannot support.
    checks.append(
        PlatformCheck(
            "circular_relationship_risk", "not_applicable",
            "Circular-relationship analysis requires evaluating all related files' join graph together.",
        )
    )

    duplicate_field_names = [c for c in set(df.columns) if list(df.columns).count(c) > 1]
    checks.append(
        PlatformCheck(
            "duplicate_fields", "fail" if duplicate_field_names else "pass",
            f"Duplicate field name(s): {duplicate_field_names}." if duplicate_field_names
            else "No duplicate field names.",
            {"columns": duplicate_field_names},
        )
    )

    field_roles = {col: "Key Candidate" for col in key_columns}
    return build_result(
        "Qlik", checks, field_roles=field_roles,
        recommendations=recommendations,
        export_recommendations=["CSV", "QVD-compatible CSV/XLSX"],
    )
