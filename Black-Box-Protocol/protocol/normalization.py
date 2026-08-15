from __future__ import annotations

from typing import Any


def first_value(payload: Any, *paths: str) -> Any:
    """Return the first present dotted path without inventing provider semantics."""
    for path in paths:
        current = payload
        for part in path.split("."):
            if not isinstance(current, dict) or part not in current:
                break
            current = current[part]
        else:
            return current
    return None


def optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "blocked", "triggered", "unsupported"}:
            return True
        if lowered in {"false", "no", "allowed", "passed", "supported"}:
            return False
    return None


def optional_float(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        result = float(value)
        return result if 0.0 <= result <= 1.0 else None
    return None
