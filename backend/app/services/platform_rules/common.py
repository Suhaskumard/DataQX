"""Shared result shape every platform module returns (DATAQX Phase 16).

Every platform module (`powerbi.py`, `tableau.py`, ...) is an *interpretation*
of the same universal facts (`DatasetProfile`, `Issue` list, semantic
`ColumnRole`s, the cleaned `DataFrame`) -- it must never re-detect an issue the
universal engine already found, and it must never return a hand-picked score.
`compute_score()` is the one, shared, auditable scoring rule every module uses.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

_SCORE_START = 100
_FAIL_PENALTY = 15
_WARNING_PENALTY = 5


@dataclass
class PlatformCheck:
    check_name: str
    status: str  # pass | warning | fail | not_applicable
    message: str
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PlatformResult:
    platform: str
    score: int
    status: str  # READY | READY_WITH_WARNINGS | NEEDS_CLEANING | NOT_READY
    checks: list[PlatformCheck] = field(default_factory=list)
    field_roles: dict = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    export_recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "score": self.score,
            "status": self.status,
            "passed_checks": [c.to_dict() for c in self.checks if c.status == "pass"],
            "warnings": [c.to_dict() for c in self.checks if c.status == "warning"],
            "critical_issues": [c.to_dict() for c in self.checks if c.status == "fail"],
            "checks": [c.to_dict() for c in self.checks],
            "field_roles": self.field_roles,
            "recommendations": self.recommendations,
            "export_recommendations": self.export_recommendations,
        }


def compute_score(checks: list[PlatformCheck]) -> int:
    score = _SCORE_START
    for check in checks:
        if check.status == "fail":
            score -= _FAIL_PENALTY
        elif check.status == "warning":
            score -= _WARNING_PENALTY
    return max(0, min(100, score))


def status_from_checks(checks: list[PlatformCheck]) -> str:
    if any(c.status == "fail" for c in checks):
        has_multiple_fails = sum(1 for c in checks if c.status == "fail") > 1
        return "NOT_READY" if has_multiple_fails else "NEEDS_CLEANING"
    if any(c.status == "warning" for c in checks):
        return "READY_WITH_WARNINGS"
    return "READY"


def build_result(
    platform: str,
    checks: list[PlatformCheck],
    field_roles: dict | None = None,
    recommendations: list[str] | None = None,
    export_recommendations: list[str] | None = None,
) -> PlatformResult:
    return PlatformResult(
        platform=platform,
        score=compute_score(checks),
        status=status_from_checks(checks),
        checks=checks,
        field_roles=field_roles or {},
        recommendations=recommendations or [],
        export_recommendations=export_recommendations or [],
    )
