"""Platform-specific analytics-readiness rule modules (DATAQX Phase 16).

Each module exposes one function, `evaluate(df, profile, issues, roles,
relationship_check=None) -> PlatformResult`, interpreting the same universal
facts (`DatasetProfile`, `Issue` list, `ColumnRole` list, the cleaned
DataFrame) into a platform-specific readiness result. No module re-detects an
issue the universal engine already found; adding a new platform means adding
one small module here and registering it in `PLATFORM_MODULES` below --
nothing else in DataQX needs to change.
"""

from __future__ import annotations

from app.services.platform_rules import (
    alteryx,
    excel,
    looker,
    lookerstudio,
    powerbi,
    python_,
    qlik,
    r_,
    sql,
    tableau,
)

PLATFORM_MODULES = {
    "power_bi": powerbi,
    "tableau": tableau,
    "alteryx": alteryx,
    "excel": excel,
    "looker": looker,
    "looker_studio": lookerstudio,
    "qlik": qlik,
    "sql": sql,
    "python": python_,
    "r": r_,
}

# Platforms whose checks meaningfully use the cross-file relationship check.
PLATFORMS_USING_RELATIONSHIPS = {"power_bi", "sql", "qlik", "looker"}
