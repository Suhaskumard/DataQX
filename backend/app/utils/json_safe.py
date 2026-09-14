"""JSON-safety helper.

Profiling statistics (mean/std/min/max/etc.) can legitimately be Infinity/-Infinity/
NaN for real (if unusual) data -- e.g. a column containing literal `inf` sentinels.
Python's stdlib `json.dumps` serializes these as the bare tokens `Infinity`,
`-Infinity`, `NaN` by default, which is not valid JSON: a strict parser (a browser's
`JSON.parse`, many typed HTTP clients) will fail on them. Applied once at the API
serialization boundary (where a dict is about to become a JSON string/file), not
inside the profiling/statistics computation itself, so internal callers and tests
that assert on the raw float values are unaffected.
"""

from __future__ import annotations

import math


def sanitize_for_json(value):
    """Recursively replace non-finite floats (NaN/Infinity/-Infinity) with None."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: sanitize_for_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize_for_json(v) for v in value]
    return value
