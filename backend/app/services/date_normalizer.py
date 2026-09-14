"""Layered, non-destructive date normalization.

Replaces the previous single bare `pd.to_datetime(series, errors="coerce")` call that
turned any value pandas' default format inference couldn't guess into NaT -- destroying
recoverable dates such as "Jan 7 2026" or "08-01-2026". This module never nulls a value
merely because one parser failed; it only nulls a value that is genuinely impossible
(day/month out of range, Feb 29 on a non-leap year, unparseable text) and always keeps
the original value available to the caller for audit.

For genuinely ambiguous numeric dates (e.g. "05/01/2026" -- could be 5 Jan or 1 May),
the column-wide convention is inferred from OTHER values in the same column that are
unambiguous (a day/month component > 12 can only be a day) before falling back to
"preserve and flag" when no such evidence exists.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

# Values that mean "no date supplied", not "invalid date" -- must not be treated as
# parse failures.
_MISSING_MARKERS = {
    "", "na", "n/a", "null", "none", "unknown", "not available", "-", "--", "nan", "nat",
}

# Explicit, unambiguous month-name formats. Tried before any numeric-slash/dash
# interpretation since they carry no DD/MM vs MM/DD ambiguity at all.
_MONTH_NAME_FORMATS = [
    "%b %d %Y", "%B %d %Y", "%b %d, %Y", "%B %d, %Y",
    "%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%d-%B-%Y",
]

# Unambiguous ISO-style formats (year first).
_ISO_FORMATS = ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"]

_NUMERIC_TOKEN_RE = re.compile(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$")
_ISO_TOKEN_RE = re.compile(r"^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})$")

_MIN_YEAR, _MAX_YEAR = 1900, 2100


@dataclass
class DateParseResult:
    original_value: object
    normalized_value: str | None  # ISO "YYYY-MM-DD", or None if missing/invalid
    detected_format: str | None
    convention: str | None  # "DD/MM", "MM/DD", or None
    confidence: str  # "HIGH", "MEDIUM", "LOW", or "MISSING"/"INVALID"
    status: str  # "parsed", "missing", "ambiguous", "invalid"
    reason: str


def _normalize_year(year: int) -> int:
    if year < 100:
        return 2000 + year if year < 70 else 1900 + year
    return year


def _try_build_date(year: int, month: int, day: int) -> date | None:
    year = _normalize_year(year)
    if not (_MIN_YEAR <= year <= _MAX_YEAR):
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def infer_column_convention(values: list[str]) -> str | None:
    """Scan all ambiguous-shaped numeric date tokens in a column and infer whether the
    column-wide convention is DD/MM or MM/DD from any value where one component is
    unambiguously > 12 (and therefore must be the day). Returns None if there is no
    such evidence, or if the column contains contradictory evidence for both."""
    has_ddmm = False
    has_mmdd = False
    for raw in values:
        if raw is None:
            continue
        text = str(raw).strip()
        m = _NUMERIC_TOKEN_RE.match(text)
        if not m:
            continue
        a, b, _year = int(m.group(1)), int(m.group(2)), m.group(3)
        if a > 12 and b <= 12:
            has_ddmm = True
        elif b > 12 and a <= 12:
            has_mmdd = True
    if has_ddmm and has_mmdd:
        return None  # contradictory evidence -- do not guess
    if has_ddmm:
        return "DD/MM"
    if has_mmdd:
        return "MM/DD"
    return None


def parse_date_cell(raw: object, column_convention: str | None = None) -> DateParseResult:
    """Parse a single date cell without ever silently destroying recoverable data."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return DateParseResult(raw, None, None, None, "MISSING", "missing", "Empty value.")

    if isinstance(raw, (pd.Timestamp, datetime, date)):
        d = raw.date() if isinstance(raw, (pd.Timestamp, datetime)) else raw
        return DateParseResult(raw, d.isoformat(), "python_datetime", None, "HIGH", "parsed", "Already a datetime value.")

    text = str(raw).strip()
    if text.lower() in _MISSING_MARKERS:
        return DateParseResult(raw, None, None, None, "MISSING", "missing", f"Recognized missing-value marker: '{text}'.")

    # 1. Unambiguous ISO (year-first) formats.
    for fmt in _ISO_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt).date()
            return DateParseResult(raw, parsed.isoformat(), fmt, None, "HIGH", "parsed", "Unambiguous ISO year-first format.")
        except ValueError:
            pass

    iso_match = _ISO_TOKEN_RE.match(text)
    if iso_match:
        year, month, day = (int(g) for g in iso_match.groups())
        d = _try_build_date(year, month, day)
        if d:
            return DateParseResult(raw, d.isoformat(), "YYYY-M-D", None, "HIGH", "parsed", "Unambiguous ISO year-first format.")
        return DateParseResult(raw, None, None, None, "INVALID", "invalid", f"'{text}' looks like an ISO date but day/month is out of range.")

    # 2. Unambiguous month-name formats.
    for fmt in _MONTH_NAME_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt).date()
            return DateParseResult(raw, parsed.isoformat(), fmt, None, "HIGH", "parsed", "Unambiguous month-name format.")
        except ValueError:
            pass

    # 3. Numeric DD/MM/YYYY-shaped (slash, dash, or dot separated).
    m = _NUMERIC_TOKEN_RE.match(text)
    if m:
        a, b, year_str = int(m.group(1)), int(m.group(2)), int(m.group(3))

        if a > 12 and b > 12:
            return DateParseResult(raw, None, None, None, "INVALID", "invalid", f"'{text}': neither component can be a valid month (both > 12).")

        if a > 12:  # first component must be the day -> DD/MM
            d = _try_build_date(year_str, b, a)
            if d:
                return DateParseResult(raw, d.isoformat(), "DD/MM/YYYY", "DD/MM", "HIGH",
                                        "parsed", f"'{text}': first component ({a}) > 12, so it must be the day -- unambiguous DD/MM/YYYY.")
            return DateParseResult(raw, None, None, None, "INVALID", "invalid", f"'{text}' is not a valid calendar date under DD/MM/YYYY.")

        if b > 12:  # second component must be the day -> MM/DD
            d = _try_build_date(year_str, a, b)
            if d:
                return DateParseResult(raw, d.isoformat(), "MM/DD/YYYY", "MM/DD", "HIGH",
                                        "parsed", f"'{text}': second component ({b}) > 12, so it must be the day -- unambiguous MM/DD/YYYY.")
            return DateParseResult(raw, None, None, None, "INVALID", "invalid", f"'{text}' is not a valid calendar date under MM/DD/YYYY.")

        # Both components <= 12: genuinely ambiguous without column-wide evidence.
        if column_convention == "DD/MM":
            d = _try_build_date(year_str, b, a)
            if d:
                return DateParseResult(raw, d.isoformat(), "DD/MM/YYYY", "DD/MM", "MEDIUM",
                                        "parsed", f"Column convention inferred as DD/MM/YYYY from other unambiguous values in this column.")
        elif column_convention == "MM/DD":
            d = _try_build_date(year_str, a, b)
            if d:
                return DateParseResult(raw, d.isoformat(), "MM/DD/YYYY", "MM/DD", "MEDIUM",
                                        "parsed", f"Column convention inferred as MM/DD/YYYY from other unambiguous values in this column.")

        return DateParseResult(raw, None, None, None, "LOW", "ambiguous",
                                f"'{text}' could be DD/MM or MM/DD and no column-wide convention evidence exists -- preserved, not guessed.")

    # 4. Last-resort: full ISO datetime (with time/timezone) via pandas, which is
    # unambiguous by construction (contains 'T' or explicit separators pandas trusts).
    if "t" in text.lower() or re.search(r"\d{4}-\d{2}-\d{2}", text):
        try:
            parsed = pd.Timestamp(text)
            if not pd.isna(parsed):
                return DateParseResult(raw, parsed.date().isoformat(), "iso_datetime", None, "HIGH", "parsed", "Unambiguous ISO datetime.")
        except (ValueError, TypeError):
            pass

    return DateParseResult(raw, None, None, None, "INVALID", "invalid", f"'{text}' could not be recognized as any known date format.")


def normalize_date_column(series: pd.Series) -> list[DateParseResult]:
    """Parse an entire column, inferring a shared convention from unambiguous evidence
    in the column before resolving individually-ambiguous values."""
    values = series.tolist()
    convention = infer_column_convention([str(v) for v in values if v is not None])
    return [parse_date_cell(v, column_convention=convention) for v in values]
