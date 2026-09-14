"""Universal semantic-role classification (DATAQX Phase 16).

Column -> role inference used to be embedded inside the Power BI-specific
readiness module, but the inference itself (is this column a key, a measure, a
dimension, a date dimension?) has nothing to do with Power BI -- it is a fact
about the data, derived once from `DatasetProfile`, and every platform module
under `app.services.platform_rules` reuses it instead of re-deriving its own
notion of "what kind of column is this."
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.services.profiling import DatasetProfile


@dataclass
class ColumnRole:
    column: str
    role: str  # primary_key | foreign_key_candidate | measure | dimension_attribute | date_dimension

    def to_dict(self) -> dict:
        return asdict(self)


def classify_columns(profile: DatasetProfile) -> list[ColumnRole]:
    roles = []
    for col in profile.columns:
        if col.inferred_type == "id":
            roles.append(ColumnRole(col.original_name, "primary_key"))
        elif col.inferred_type in ("date", "datetime"):
            roles.append(ColumnRole(col.original_name, "date_dimension"))
        elif col.inferred_type in ("integer", "float"):
            roles.append(ColumnRole(col.original_name, "measure"))
        elif col.inferred_type in ("categorical", "string", "boolean"):
            roles.append(ColumnRole(col.original_name, "dimension_attribute"))
    return roles


def classify_table_role(roles: list[ColumnRole]) -> str:
    measure_count = sum(1 for c in roles if c.role == "measure")
    attribute_count = sum(1 for c in roles if c.role in ("dimension_attribute", "primary_key"))
    if measure_count == 0 and attribute_count == 0:
        return "unclassified"
    return "fact" if measure_count > attribute_count else "dimension"


def columns_with_role(roles: list[ColumnRole], role: str) -> list[str]:
    return [c.column for c in roles if c.role == role]
