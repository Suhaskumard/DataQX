"""Near-duplicate (Level 3) detection.

Only exact-row and exact-ID-value duplicate detection existed before this (both in
issue_detection.py, both O(n) via pandas' own `.duplicated()`). This adds a separate,
narrower check for records that are NOT exact duplicates but are suspiciously similar
(e.g. same person with a typo'd name or re-typed email). Never wired into the cleaning
engine's auto-apply path -- flagged for review only, per the "never blindly delete near
duplicates" requirement.

Uses blocking (group by a cheap normalized key) instead of comparing every row against
every other row, so this stays well clear of O(n^2) on realistic dataset sizes.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

_DIGITS_RE = re.compile(r"\D+")
_NAME_SIMILARITY_THRESHOLD = 0.82


@dataclass
class NearDuplicateMatch:
    row_indices: tuple[int, int]
    similarity: float
    matching_fields: list[str] = field(default_factory=list)
    conflicting_fields: list[str] = field(default_factory=list)
    confidence: str = "LOW"
    recommended_action: str = "Review manually; do not auto-merge or delete."


def _normalize_email(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


def _normalize_phone(value: object) -> str | None:
    if value is None:
        return None
    digits = _DIGITS_RE.sub("", str(value))
    return digits or None


def _block_key(row: dict, email_col: str | None, phone_col: str | None) -> str | None:
    email = _normalize_email(row.get(email_col)) if email_col else None
    phone = _normalize_phone(row.get(phone_col)) if phone_col else None
    if email:
        return f"email:{email[:3]}"
    if phone:
        return f"phone:{phone[-6:]}" if len(phone) >= 6 else f"phone:{phone}"
    return None


def find_near_duplicates(
    records: list[dict],
    name_col: str | None = None,
    email_col: str | None = None,
    phone_col: str | None = None,
) -> list[NearDuplicateMatch]:
    """Find likely-but-not-certain duplicate records via blocking + name similarity.

    `records` is a list of row dicts (already indexed by their original row position
    via a "_row_index" key, or list position is used if absent).
    """
    if not (name_col or email_col or phone_col):
        return []

    blocks: dict[str, list[int]] = {}
    for i, row in enumerate(records):
        key = _block_key(row, email_col, phone_col)
        if key is None:
            continue
        blocks.setdefault(key, []).append(i)

    matches: list[NearDuplicateMatch] = []
    for indices in blocks.values():
        if len(indices) < 2:
            continue
        for a_pos in range(len(indices)):
            for b_pos in range(a_pos + 1, len(indices)):
                i, j = indices[a_pos], indices[b_pos]
                row_a, row_b = records[i], records[j]

                matching_fields: list[str] = []
                conflicting_fields: list[str] = []
                similarity = 0.0

                if email_col:
                    ea, eb = _normalize_email(row_a.get(email_col)), _normalize_email(row_b.get(email_col))
                    if ea and eb:
                        (matching_fields if ea == eb else conflicting_fields).append(email_col)

                if phone_col:
                    pa, pb = _normalize_phone(row_a.get(phone_col)), _normalize_phone(row_b.get(phone_col))
                    if pa and pb:
                        (matching_fields if pa == pb else conflicting_fields).append(phone_col)

                if name_col:
                    na = str(row_a.get(name_col) or "").strip().lower()
                    nb = str(row_b.get(name_col) or "").strip().lower()
                    if na and nb:
                        similarity = difflib.SequenceMatcher(None, na, nb).ratio()
                        if similarity >= _NAME_SIMILARITY_THRESHOLD:
                            if na != nb:
                                matching_fields.append(f"{name_col}~")
                            else:
                                matching_fields.append(name_col)
                        elif na != nb:
                            conflicting_fields.append(name_col)

                if row_a == row_b:
                    continue  # exact duplicates are handled elsewhere

                if matching_fields:
                    matches.append(
                        NearDuplicateMatch(
                            row_indices=(i, j),
                            similarity=round(similarity, 3),
                            matching_fields=matching_fields,
                            conflicting_fields=conflicting_fields,
                        )
                    )

    return matches
