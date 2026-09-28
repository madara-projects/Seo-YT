"""Observations on a video's audience-retention curve, related to its package.

The curve is YouTube Analytics' audienceWatchRatio per elapsedVideoTimeRatio:
the share of viewers still watching at each point of the video (it can pass 1
where people rewatch). relativeRetentionPerformance compares that with videos
of similar length on YouTube, 0.5 being typical. These are observations of
where viewers left, never proof of why.
"""

from __future__ import annotations

import re
from typing import Any

# The opening that the package's hook has to carry.
HOOK_RATIO = 0.15
NOTE = (
    "Observations of when viewers left, not proof of why: the title, thumbnail, opening or topic "
    "can each shape the curve, and this tool cannot separate them."
)
_TIMESTAMP = re.compile(r"^(?:(\d{1,2}):)?(\d{1,2}):(\d{2})$")


def curve_observations(
    points: list[dict[str, Any]],
    *,
    duration_seconds: float | None,
    chapters: list[dict[str, Any]] | None,
    short: bool,
) -> dict[str, Any]:
    """Where the curve drops most, relative to the hook and to a long video's chapters."""
    curve = sorted(
        (point for point in points if _number(point.get("elapsed_ratio")) is not None
         and _number(point.get("audience_watch_ratio")) is not None),
        key=lambda point: float(point["elapsed_ratio"]),
    )
    duration = float(duration_seconds) if duration_seconds and duration_seconds > 0 else None
    chapter_rows = [] if short or not duration or len(curve) < 2 else _chapters(curve, chapters or [], duration)
    if len(curve) < 2:
        return {"hook": None, "biggest_drop": None, "chapters": [], "observations": [], "note": NOTE}

    earlier, later = max(
        zip(curve, curve[1:]),
        key=lambda pair: float(pair[0]["audience_watch_ratio"]) - float(pair[1]["audience_watch_ratio"]),
    )
    at_ratio = float(later["elapsed_ratio"])
    at_seconds = round(at_ratio * duration) if duration else None
    chapter = next(
        (item for item in chapter_rows if at_seconds is not None and item["start_seconds"] <= at_seconds < item["end_seconds"]),
        None,
    )
    drop = {
        "from_ratio": float(earlier["elapsed_ratio"]),
        "at_ratio": at_ratio,
        "at_seconds": at_seconds,
        "drop_points": round((float(earlier["audience_watch_ratio"]) - float(later["audience_watch_ratio"])) * 100, 1),
        "in_hook": at_ratio <= HOOK_RATIO,
        "chapter": chapter["title"] if chapter else None,
    }

    hook_points = [point for point in curve if float(point["elapsed_ratio"]) <= HOOK_RATIO]
    relative = [_number(point.get("relative_retention_performance")) for point in hook_points]
    relative = [value for value in relative if value is not None]
    hook = {
        "end_ratio": HOOK_RATIO,
        "still_watching_percent": round(float(hook_points[-1]["audience_watch_ratio"]) * 100, 1) if hook_points else None,
        "relative_retention_performance": round(sum(relative) / len(relative), 2) if relative else None,
    }

    where = f"{round(at_ratio * 100)}% of the way in" + (f", around {_clock(at_seconds)}" if at_seconds is not None else "")
    observations = [
        f"The biggest single drop ({drop['drop_points']:.1f} points of the audience) comes {where}, "
        + ("within the hook (the first 15%)." if drop["in_hook"] else "after the hook (the first 15%).")
    ]
    if hook["still_watching_percent"] is not None:
        observations.append(f"{hook['still_watching_percent']:.0f}% of the audience is still watching at the end of the hook.")
    if hook["relative_retention_performance"] is not None:
        comparison = "above" if hook["relative_retention_performance"] > 0.5 else "below" if hook["relative_retention_performance"] < 0.5 else "about"
        observations.append(
            f"During the hook, retention is {comparison} typical for YouTube videos of similar length "
            f"(YouTube's relative score {hook['relative_retention_performance']:.2f}, where 0.50 is typical)."
        )
    if chapter:
        observations.append(
            f'The biggest drop falls in chapter "{chapter["title"]}" '
            f'({_clock(chapter["start_seconds"])}–{_clock(chapter["end_seconds"])}).'
        )
    if chapter_rows:
        steepest = max(chapter_rows, key=lambda item: item["viewers_lost_points"])
        observations.append(
            f'Chapter "{steepest["title"]}" ({_clock(steepest["start_seconds"])}) loses the most audience: '
            f'{steepest["viewers_lost_points"]:.1f} points.'
        )
    return {"hook": hook, "biggest_drop": drop, "chapters": chapter_rows, "observations": observations, "note": NOTE}


def _chapters(curve: list[dict[str, Any]], chapters: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
    """Each chapter's span and the audience it loses, from the package's chapter timestamps."""
    starts = []
    for item in chapters:
        seconds = _seconds(str((item or {}).get("timestamp") or ""))
        if seconds is not None and seconds < duration:
            starts.append((seconds, str(item.get("title") or "").strip() or "Untitled chapter"))
    starts.sort()
    rows = []
    for index, (start, title) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else round(duration)
        if end <= start:
            continue
        first = _watch_at(curve, start / duration, after=True)
        last = _watch_at(curve, end / duration, after=False)
        rows.append({
            "title": title,
            "start_seconds": start,
            "end_seconds": end,
            "viewers_lost_points": round((first - last) * 100, 1) if first is not None and last is not None else 0.0,
        })
    return rows


def _watch_at(curve: list[dict[str, Any]], ratio: float, *, after: bool) -> float | None:
    """The audience at the first point at or after `ratio` (a chapter's start) or the last one at or before it (its end)."""
    if after:
        point = next((item for item in curve if float(item["elapsed_ratio"]) >= ratio - 1e-9), None)
    else:
        point = next((item for item in reversed(curve) if float(item["elapsed_ratio"]) <= ratio + 1e-9), None)
    return float(point["audience_watch_ratio"]) if point else None


def _seconds(timestamp: str) -> int | None:
    match = _TIMESTAMP.match(timestamp.strip())
    if not match:
        return None
    hours, minutes, seconds = (int(value or 0) for value in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def _clock(seconds: int | float | None) -> str:
    total = int(round(seconds or 0))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None
