"""ISO-8601 durations as YouTube reports them (PT4M13S, P1DT2H)."""

from __future__ import annotations

import re

_DURATION = re.compile(
    r"P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?"
)


def duration_seconds(value: object) -> int | None:
    """Seconds in a YouTube duration, or None when it is missing or zero.

    Live and upcoming broadcasts report P0D, which says nothing about length.
    """

    match = _DURATION.fullmatch(str(value or "").strip().upper())
    if not match:
        return None
    parts = {name: int(raw or 0) for name, raw in match.groupdict().items()}
    total = parts["days"] * 86400 + parts["hours"] * 3600 + parts["minutes"] * 60 + parts["seconds"]
    return total or None
