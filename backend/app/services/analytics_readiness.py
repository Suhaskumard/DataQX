"""Universal Analytics Readiness Engine (DATAQX Phase 16).

Accepts the already-computed universal facts for one file (profile, issues,
optionally a cross-file relationship check) and evaluates every requested
platform module against them, returning one standardized result per platform
plus an overall score. This is the orchestrator described in the DataQX
platform-amendment plan: platform modules never re-detect anything, they only
interpret facts this module hands them.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

from app.services.issue_detection import Issue
from app.services.platform_rules import PLATFORM_MODULES, PLATFORMS_USING_RELATIONSHIPS
from app.services.platform_rules.common import PlatformCheck, PlatformResult
from app.services.profiling import DatasetProfile
from app.services.semantic_roles import classify_columns

ALL_PLATFORMS = list(PLATFORM_MODULES.keys())


@dataclass
class AnalyticsReadinessResult:
    overall_score: int
    platforms: dict[str, PlatformResult] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "overall_score": self.overall_score,
            "platforms": {name: result.to_dict() for name, result in self.platforms.items()},
        }


def evaluate_analytics_readiness(
    df: pd.DataFrame,
    profile: DatasetProfile,
    issues: list[Issue],
    relationship_check: PlatformCheck | None = None,
    selected_platforms: list[str] | None = None,
) -> AnalyticsReadinessResult:
    platforms_to_run = selected_platforms or ALL_PLATFORMS
    unknown = set(platforms_to_run) - set(PLATFORM_MODULES)
    if unknown:
        raise ValueError(f"Unknown platform(s): {sorted(unknown)}. Known platforms: {ALL_PLATFORMS}")

    roles = classify_columns(profile)

    results: dict[str, PlatformResult] = {}
    for name in platforms_to_run:
        module = PLATFORM_MODULES[name]
        check_for_platform = relationship_check if name in PLATFORMS_USING_RELATIONSHIPS else None
        results[name] = module.evaluate(df, profile, issues, roles, relationship_check=check_for_platform)

    overall_score = round(sum(r.score for r in results.values()) / len(results)) if results else 0
    return AnalyticsReadinessResult(overall_score=overall_score, platforms=results)
