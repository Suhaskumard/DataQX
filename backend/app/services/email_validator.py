"""Email structural validation.

No email validation existed anywhere in the codebase before this. Detects malformed
addresses; safe cleaning is limited to whitespace trimming and lowercasing -- an
invalid email is flagged, never given a fabricated domain or repaired guess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# local-part @ domain-label(.domain-label)+  -- deliberately conservative: no spaces,
# exactly one '@', at least one '.' in the domain, no empty local/domain parts.
_EMAIL_RE = re.compile(
    r"^(?P<local>[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+)"
    r"@"
    r"(?P<domain>[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)$"
)


@dataclass
class EmailValidationResult:
    original_value: object
    normalized_value: str | None
    is_valid: bool
    reason: str


def validate_email_cell(raw: object) -> EmailValidationResult:
    if raw is None:
        return EmailValidationResult(raw, None, False, "Empty value.")

    text = str(raw).strip()
    if not text:
        return EmailValidationResult(raw, None, False, "Empty value.")

    if " " in text or "\t" in text:
        return EmailValidationResult(raw, None, False, f"'{text}' contains whitespace.")

    if text.count("@") != 1:
        return EmailValidationResult(raw, None, False, f"'{text}' must contain exactly one '@' (found {text.count('@')}).")

    normalized = text.lower()
    match = _EMAIL_RE.match(normalized)
    if not match:
        local, _, domain = normalized.partition("@")
        if not local:
            reason = f"'{text}' is missing the local part before '@'."
        elif not domain:
            reason = f"'{text}' is missing a domain after '@'."
        elif "." not in domain:
            reason = f"'{text}' has a malformed domain (no top-level domain)."
        else:
            reason = f"'{text}' does not match a valid email pattern."
        return EmailValidationResult(raw, None, False, reason)

    return EmailValidationResult(raw, normalized, True, "Valid email; trimmed and lowercased.")
