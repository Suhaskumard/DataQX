import math

from app.utils.json_safe import sanitize_for_json


def test_sanitize_replaces_nan_and_infinity_with_none():
    data = {
        "mean": float("nan"),
        "max": float("inf"),
        "min": float("-inf"),
        "count": 5,
        "nested": {"std": float("nan"), "ok": 1.5},
        "list": [float("nan"), 2.0, float("inf")],
    }

    result = sanitize_for_json(data)

    assert result["mean"] is None
    assert result["max"] is None
    assert result["min"] is None
    assert result["count"] == 5
    assert result["nested"]["std"] is None
    assert result["nested"]["ok"] == 1.5
    assert result["list"] == [None, 2.0, None]


def test_sanitize_leaves_finite_values_and_other_types_untouched():
    data = {"a": 1, "b": "text", "c": None, "d": True, "e": 3.14}
    assert sanitize_for_json(data) == data


def test_sanitized_output_is_valid_json_via_json_dumps():
    import json

    data = {"mean": float("nan"), "std": float("inf")}
    dumped = json.dumps(sanitize_for_json(data))
    reloaded = json.loads(dumped)  # would raise if Infinity/NaN tokens leaked through
    assert reloaded == {"mean": None, "std": None}
    assert "NaN" not in dumped
    assert "Infinity" not in dumped
