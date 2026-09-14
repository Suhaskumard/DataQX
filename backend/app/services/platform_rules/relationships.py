"""Cross-file relationship check (DATAQX Phase 16).

The only check in the readiness engine that needs *every* file in the run, not
just one -- detected once here and reused by whichever platform modules care
about relationships (Power BI, SQL, Qlik, Looker), instead of each module
re-scanning every file pair for foreign-key orphans on its own.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from app.services.platform_rules.common import PlatformCheck
from app.services.profiling import DatasetProfile

_FK_NAME_RE = re.compile(r"^(.+)_id$", re.IGNORECASE)


def _singularize(word: str) -> str:
    return word[:-1] if word.endswith("s") else word


def _filename_stem_singular(filename: str) -> str:
    return _singularize(Path(filename).stem.lower())


def assess_relationships(files: dict[str, tuple[pd.DataFrame, DatasetProfile]]) -> dict[str, PlatformCheck]:
    if len(files) < 2:
        return {
            name: PlatformCheck(
                "foreign_key_relationships", "not_applicable",
                "Only one file in this run; relationship checks require multiple related files.",
            )
            for name in files
        }

    # A column's referenced file is identified by naming convention (customer_id ->
    # customers.csv), not by whether it happens to be locally unique in its own file
    # -- a foreign key column can easily be unique within a small sample without
    # being anyone's primary key, so "inferred as id in this file" is not a reliable
    # signal for "this file's own key" and was found to produce false negatives.
    stems = {name: _filename_stem_singular(name) for name in files}

    results: dict[str, PlatformCheck] = {}
    for name, (df, _profile) in files.items():
        fk_findings = {}
        for column in df.columns:
            match = _FK_NAME_RE.match(str(column))
            if not match:
                continue
            prefix = match.group(1).lower()
            if prefix == stems[name]:
                continue  # this file's own natural primary key (e.g. orders.csv -> order_id)

            for other_name, other_stem in stems.items():
                if other_name == name or other_stem != prefix:
                    continue
                other_df, _ = files[other_name]
                if column not in other_df.columns:
                    continue
                referencing_values = set(df[column].dropna().unique())
                referenced_values = set(other_df[column].dropna().unique())
                orphans = referencing_values - referenced_values
                if orphans:
                    fk_findings[column] = {
                        "references": other_name,
                        "orphan_count": len(orphans),
                        "orphan_examples": sorted(str(v) for v in orphans)[:5],
                    }
                break

        if fk_findings:
            results[name] = PlatformCheck(
                "foreign_key_relationships", "warning",
                f"Orphan foreign key value(s) found: {list(fk_findings.keys())}.",
                {"findings": fk_findings},
            )
        else:
            results[name] = PlatformCheck(
                "foreign_key_relationships", "pass", "All matched foreign keys resolve correctly."
            )

    return results
