"""Dataset profiling (DATAQX.pdf S15).

Computes a baseline profile -- dataset-level and column-level statistics -- from an
already-loaded DataFrame. Read-only: never modifies the source data. Missing-value
placeholder detection ("N/A", "--", etc.), outlier classification, and category
standardization are later phases (S17/S26/S24) -- this phase only measures.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

NEAR_CONSTANT_THRESHOLD = 0.95
RARE_CATEGORY_THRESHOLD = 0.01
TOP_CATEGORIES_LIMIT = 5
EXAMPLE_VALUES_LIMIT = 5
ID_UNIQUENESS_THRESHOLD = 0.9

_CLEAN_NAME_RE = re.compile(r"[^0-9a-zA-Z]+")
_WHITESPACE_ISSUE_RE = re.compile(r"^\s|\s$|\s{2,}")
# Equivalent to the old per-character _has_unicode_issue() loop (unicodedata.category()
# starting with "C", excluding tab/newline, OR ord(ch) > 127) but as a single regex so
# pandas can evaluate it with .str.contains() instead of a per-cell Python function call
# -- DATAQX.pdf S59 (avoid unnecessary per-row Python loops; prefer vectorized operations).
# Real profiling on a 100k-row dataset showed the old .map(_has_unicode_issue) call was
# the single largest hotspot in the whole analyze pipeline (~1.2s of ~4.3s measured).
_UNICODE_ISSUE_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]|[^\x00-\x7f]")


def clean_column_name(name: str) -> str:
    """Normalize a raw column name to snake_case (DATAQX.pdf S20)."""
    normalized = _CLEAN_NAME_RE.sub("_", str(name).strip())
    normalized = normalized.strip("_").lower()
    return normalized or "column"


def infer_column_type(series: pd.Series, column_name: str) -> str:
    """Classify a column as integer/float/boolean/date/datetime/categorical/string/id."""
    non_null = series.dropna()
    if non_null.empty:
        return "string"

    if pd.api.types.is_bool_dtype(series):
        return "boolean"

    if pd.api.types.is_datetime64_any_dtype(series):
        has_time = (non_null.dt.time != datetime.min.time()).any() if hasattr(non_null, "dt") else False
        return "datetime" if has_time else "date"

    if pd.api.types.is_numeric_dtype(series):
        is_integer_like = pd.api.types.is_integer_dtype(series) or (
            pd.api.types.is_float_dtype(series) and (non_null % 1 == 0).all()
        )
        unique_ratio = non_null.nunique() / len(non_null)
        name_suggests_id = bool(re.search(r"(^|_)id$|^id(_|$)", column_name.lower()))
        if is_integer_like and (name_suggests_id and unique_ratio >= ID_UNIQUENESS_THRESHOLD):
            return "id"
        return "integer" if is_integer_like else "float"

    # Object/string column: try a date parse (only if it looks date-like, to avoid
    # accidentally parsing plain numeric-looking strings as dates).
    sample = non_null.astype(str).head(20)
    date_like_pattern = re.compile(r"\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/\d{2,4}")
    if sample.map(lambda v: bool(date_like_pattern.search(v))).mean() > 0.5:
        parsed = pd.to_datetime(non_null, errors="coerce")
        if parsed.notna().mean() > 0.5:
            return "date"

    unique_ratio = non_null.nunique() / len(non_null)
    name_suggests_id = bool(re.search(r"(^|_)id$|^id(_|$)", column_name.lower()))
    if name_suggests_id and unique_ratio >= ID_UNIQUENESS_THRESHOLD:
        return "id"

    if unique_ratio <= 0.5 and non_null.nunique() <= 50:
        return "categorical"

    return "string"


def _normalize_for_inconsistency(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower()


@dataclass
class ColumnProfile:
    original_name: str
    clean_name: str
    dtype: str
    inferred_type: str
    missing_count: int
    missing_percentage: float
    unique_count: int
    unique_percentage: float
    example_values: list
    min: object = None
    max: object = None
    mean: float | None = None
    median: float | None = None
    std: float | None = None
    mode: object = None
    zero_count: int | None = None
    negative_count: int | None = None
    categorical_extra: dict | None = None
    numeric_extra: dict | None = None
    date_extra: dict | None = None
    text_extra: dict | None = None


@dataclass
class DatasetProfile:
    row_count: int
    column_count: int
    file_size_bytes: int | None
    memory_usage_bytes: int
    duplicate_row_count: int
    empty_row_count: int
    empty_column_count: int
    constant_columns: list[str]
    near_constant_columns: list[str]
    dataset_hash: str
    columns: list[ColumnProfile] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _profile_numeric(series: pd.Series) -> dict:
    non_null = series.dropna()
    q1, q3 = non_null.quantile(0.25), non_null.quantile(0.75)
    iqr = q3 - q1
    lower_bound, upper_bound = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    outlier_count = int(((non_null < lower_bound) | (non_null > upper_bound)).sum())
    return {
        "q25": float(q1),
        "q50": float(non_null.quantile(0.5)),
        "q75": float(q3),
        "outlier_count": outlier_count,
    }


def _profile_categorical(series: pd.Series) -> dict:
    non_null = series.dropna().astype(str)
    total = len(non_null)
    counts = non_null.value_counts()

    top_categories = [
        {"value": val, "count": int(cnt)} for val, cnt in counts.head(TOP_CATEGORIES_LIMIT).items()
    ]
    rare_categories = [
        {"value": val, "count": int(cnt)}
        for val, cnt in counts.items()
        if cnt == 1 or (cnt / total) <= RARE_CATEGORY_THRESHOLD
    ]

    groups: dict[str, set] = {}
    for val in counts.index:
        key = _normalize_for_inconsistency(val)
        groups.setdefault(key, set()).add(val)
    potential_inconsistencies = [sorted(variants) for variants in groups.values() if len(variants) > 1]

    return {
        "top_categories": top_categories,
        "rare_categories": rare_categories,
        "potential_inconsistencies": potential_inconsistencies,
    }


def _parse_dates_safely(series: pd.Series) -> pd.Series:
    """Best-effort date parsing that never raises. A column mixing timezone-naive
    and timezone-aware ISO-8601 strings can make pandas fall back to `object` dtype
    instead of a proper datetime64 dtype (a real, reproducible case on the pinned
    pandas version, not merely theoretical) -- normalize to UTC in that case so the
    `.dt` accessor below stays usable. Any parse failure degrades to "everything
    invalid" rather than crashing the whole file's analysis over one bad column."""
    try:
        parsed = pd.to_datetime(series, errors="coerce")
    except Exception:
        return pd.Series([pd.NaT] * len(series), index=series.index)

    if len(parsed) and not pd.api.types.is_datetime64_any_dtype(parsed):
        try:
            parsed = pd.to_datetime(series, errors="coerce", utc=True)
        except Exception:
            return pd.Series([pd.NaT] * len(series), index=series.index)

    return parsed


def _profile_date(series: pd.Series) -> dict:
    non_null = series.dropna()
    parsed = _parse_dates_safely(non_null)
    invalid_count = int(parsed.isna().sum())
    valid = parsed.dropna()
    now = pd.Timestamp.now(tz=valid.dt.tz) if len(valid) and valid.dt.tz is not None else pd.Timestamp.now()
    future_count = int((valid > now).sum()) if len(valid) else 0
    return {
        "min": valid.min().isoformat() if len(valid) else None,
        "max": valid.max().isoformat() if len(valid) else None,
        "invalid_count": invalid_count,
        "future_count": future_count,
    }


def _profile_text(series: pd.Series) -> dict:
    non_null = series.dropna().astype(str)
    whitespace_issue_count = int(non_null.str.contains(_WHITESPACE_ISSUE_RE, regex=True).sum())
    empty_string_count = int((non_null.str.strip() == "").sum())

    normalized_groups: dict[str, set] = {}
    for val in non_null.unique():
        key = _normalize_for_inconsistency(val)
        normalized_groups.setdefault(key, set()).add(val)
    case_variation_count = sum(1 for variants in normalized_groups.values() if len(variants) > 1)

    unicode_issue_count = int(non_null.str.contains(_UNICODE_ISSUE_RE, regex=True).sum())

    return {
        "whitespace_issue_count": whitespace_issue_count,
        "empty_string_count": empty_string_count,
        "case_variation_count": case_variation_count,
        "unicode_issue_count": unicode_issue_count,
    }


def _profile_column(name: str, series: pd.Series) -> ColumnProfile:
    non_null = series.dropna()
    missing_count = int(series.isna().sum())
    total = len(series)
    unique_count = int(non_null.nunique())
    inferred_type = infer_column_type(series, name)

    example_values = non_null.drop_duplicates().head(EXAMPLE_VALUES_LIMIT).tolist()

    profile = ColumnProfile(
        original_name=name,
        clean_name=clean_column_name(name),
        dtype=str(series.dtype),
        inferred_type=inferred_type,
        missing_count=missing_count,
        missing_percentage=round((missing_count / total * 100) if total else 0.0, 4),
        unique_count=unique_count,
        unique_percentage=round((unique_count / len(non_null) * 100) if len(non_null) else 0.0, 4),
        example_values=[str(v) for v in example_values],
    )

    if inferred_type in ("integer", "float", "id") and pd.api.types.is_numeric_dtype(series):
        if len(non_null):
            profile.min = float(non_null.min())
            profile.max = float(non_null.max())
            profile.mean = float(non_null.mean())
            profile.median = float(non_null.median())
            profile.std = float(non_null.std()) if len(non_null) > 1 else 0.0
            mode_vals = non_null.mode()
            profile.mode = float(mode_vals.iloc[0]) if not mode_vals.empty else None
            profile.zero_count = int((non_null == 0).sum())
            profile.negative_count = int((non_null < 0).sum())
        if inferred_type in ("integer", "float"):
            profile.numeric_extra = _profile_numeric(series) if len(non_null) else None
    elif inferred_type == "categorical":
        profile.categorical_extra = _profile_categorical(series) if len(non_null) else None
    elif inferred_type in ("date", "datetime"):
        profile.date_extra = _profile_date(series) if len(non_null) else None
    elif inferred_type == "string":
        profile.text_extra = _profile_text(series) if len(non_null) else None

    return profile


def profile_dataset(df: pd.DataFrame, source_path: Path | None = None) -> DatasetProfile:
    row_count, column_count = df.shape

    if source_path is not None and source_path.exists():
        file_size_bytes = source_path.stat().st_size
        dataset_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    else:
        file_size_bytes = None
        dataset_hash = hashlib.sha256(
            pd.util.hash_pandas_object(df, index=True).values.tobytes()
        ).hexdigest()

    memory_usage_bytes = int(df.memory_usage(deep=True).sum())
    duplicate_row_count = int(df.duplicated().sum())
    empty_row_count = int(df.isna().all(axis=1).sum())
    empty_column_count = int(df.isna().all(axis=0).sum())

    constant_columns = []
    near_constant_columns = []
    for column in df.columns:
        series = df[column]
        non_null = series.dropna()
        if non_null.empty:
            continue
        top_share = non_null.value_counts(normalize=True).iloc[0]
        if series.nunique(dropna=False) <= 1:
            constant_columns.append(column)
        elif top_share >= NEAR_CONSTANT_THRESHOLD:
            near_constant_columns.append(column)

    columns = [_profile_column(str(col), df[col]) for col in df.columns]

    return DatasetProfile(
        row_count=row_count,
        column_count=column_count,
        file_size_bytes=file_size_bytes,
        memory_usage_bytes=memory_usage_bytes,
        duplicate_row_count=duplicate_row_count,
        empty_row_count=empty_row_count,
        empty_column_count=empty_column_count,
        constant_columns=constant_columns,
        near_constant_columns=near_constant_columns,
        dataset_hash=dataset_hash,
        columns=columns,
    )
