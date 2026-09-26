"""Reading reported numbers without turning a missing one into zero."""

from __future__ import annotations

from typing import Any


def optional_number(value: Any) -> float | None:
    """A reported number, or None when it is missing or unreadable.

    A hidden subscriber count, a failed lookup or an unmeasured score is
    unknown, not zero.
    """

    try:
        return float(value)
    except (TypeError, ValueError):
        return None
