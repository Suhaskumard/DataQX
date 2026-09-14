"""Currency/numeric string normalization.

No component in the codebase previously stripped currency symbols or thousands
separators -- values like "₹4,500" or "2,499 INR" were left as opaque strings forever
(flagged only as `mixed_data_types`, LOW confidence, never touched). This module safely
converts unambiguous single-currency values to numeric while never inventing numbers
for genuinely non-numeric text ("not available", "free", "ten thousand"), and never
silently mixing values expressed in different currencies within one column.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_CURRENCY_SYMBOLS = {"₹": "INR", "$": "USD", "€": "EUR", "£": "GBP"}
_CURRENCY_CODES = {"INR", "USD", "EUR", "GBP", "RS", "RS."}

_NON_NUMERIC_PLACEHOLDERS = {
    "not available", "unavailable", "unknown", "n/a", "na", "null", "none",
    "-", "--", "",
}

# Strips a leading/trailing currency symbol or 3-letter code, commas, and whitespace,
# capturing the numeric remainder (with optional leading +/- or parentheses).
_CURRENCY_PATTERN = re.compile(
    r"^\s*(?P<prefix_sym>[₹$€£])?\s*"
    r"(?P<prefix_code>RS\.?|INR|USD|EUR|GBP)?\s*"
    r"(?P<paren_open>\()?\s*"
    r"(?P<sign>[+-])?\s*"
    r"(?P<number>[\d,]+(?:\.\d+)?)\s*"
    r"(?P<paren_close>\))?\s*"
    r"(?P<suffix_code>INR|USD|EUR|GBP)?\s*$",
    re.IGNORECASE,
)


@dataclass
class CurrencyParseResult:
    original_value: object
    normalized_value: float | None
    currency: str | None
    confidence: str  # "HIGH", "MISSING", "INVALID"
    reason: str


def _resolve_currency(prefix_sym: str | None, prefix_code: str | None, suffix_code: str | None) -> str | None:
    if prefix_sym:
        return _CURRENCY_SYMBOLS.get(prefix_sym)
    code = (prefix_code or suffix_code or "").upper().rstrip(".")
    if code == "RS":
        return "INR"
    return code or None


def parse_currency_cell(raw: object) -> CurrencyParseResult:
    if raw is None:
        return CurrencyParseResult(raw, None, None, "MISSING", "Empty value.")

    text = str(raw).strip()
    if text.lower() in _NON_NUMERIC_PLACEHOLDERS:
        return CurrencyParseResult(raw, None, None, "MISSING", f"Recognized missing-value marker: '{text}'.")

    match = _CURRENCY_PATTERN.match(text)
    if not match:
        return CurrencyParseResult(raw, None, None, "INVALID", f"'{text}' does not match any known numeric/currency pattern -- not converted.")

    number_str = match.group("number").replace(",", "")
    try:
        value = float(number_str)
    except ValueError:
        return CurrencyParseResult(raw, None, None, "INVALID", f"'{text}' could not be parsed as a number.")

    if match.group("sign") == "-" or match.group("paren_open"):
        value = -abs(value)

    currency = _resolve_currency(match.group("prefix_sym"), match.group("prefix_code"), match.group("suffix_code"))
    reason = f"Currency formatting removed; numeric value preserved ({currency or 'no currency marker'})."
    return CurrencyParseResult(raw, value, currency, "HIGH", reason)


def detect_column_currency_inconsistency(values: list[object]) -> list[str]:
    """Return the sorted set of distinct currencies found in a column when more than
    one is present. An empty list means the column is currency-consistent (or has no
    identifiable currency markers at all)."""
    currencies: set[str] = set()
    for raw in values:
        result = parse_currency_cell(raw)
        if result.currency:
            currencies.add(result.currency)
    return sorted(currencies) if len(currencies) > 1 else []
