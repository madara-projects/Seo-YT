from __future__ import annotations

import re
from itertools import pairwise
from typing import Any

from win_engine.analysis.generation_quality import is_short_content
from win_engine.analysis.strategy_layer import diverse_followups

# A stripped line that opens with a timestamp: "0:00 Intro", "01:30 - Mixing",
# "1:02:15 Taste test". Matched on the stripped line with a greedy title: a lazy
# title before optional trailing space backtracked quadratically on long lines.
_CHAPTER_LINE_RE = re.compile(r"[\[(]?((?:\d{1,2}:)?\d{1,2}:\d{2})[\])]?\s*[-–—:|.]?\s*(\S.*)")


def _timestamp_seconds(value: str) -> int | None:
    """Seconds from the start, or None when minutes or seconds reach 60 ("0:75")."""

    *hours, minutes, seconds = (int(part) for part in value.split(":"))
    if minutes >= 60 or seconds >= 60:
        return None
    return (hours[0] if hours else 0) * 3600 + minutes * 60 + seconds


def _timestamp_runs(text: str) -> list[list[tuple[int, dict[str, str]]]]:
    """Consecutive timestamp lines, one run per block; blank lines do not end a run."""

    runs: list[list[tuple[int, dict[str, str]]]] = [[]]
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = _CHAPTER_LINE_RE.fullmatch(stripped)
        seconds = _timestamp_seconds(match.group(1)) if match else None
        if seconds is None:
            if runs[-1]:
                runs.append([])
            continue
        runs[-1].append((seconds, {"timestamp": match.group(1), "title": match.group(2)}))
    return [run for run in runs if run]


def build_chapters(
    script: str,
    creator_brief: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    """The chapter list the creator wrote, or none.

    Times cannot be known before the cut exists. This used to pair fixed times
    (00:00, 00:30, 02:00, 04:00) with keyword signals, which pasted into
    YouTube as wrong chapters.
    """

    brief = creator_brief or {}
    if is_short_content(script, brief):
        return []
    # YouTube only builds chapters from a list that starts at 0:00, has three
    # or more entries and moves forward by at least ten seconds each time. The
    # list is one block of timestamp lines: a narration line elsewhere ("7:45
    # the flight took off late") neither joins it nor, out of order, voids it.
    for run in _timestamp_runs(str(brief.get("content") or script or "")):
        seconds = [value for value, _ in run]
        if len(run) >= 3 and seconds[0] == 0 and all(later - earlier >= 10 for earlier, later in pairwise(seconds)):
            return [chapter for _, chapter in run]
    return []


def _phrase(value: str) -> str:
    text = " ".join(str(value or "").split())
    return text[:1].upper() + text[1:]


def build_session_expansion(
    *,
    related_phrases: list[str] | None = None,
    short_form: bool = False,
) -> dict[str, Any]:
    """Suggest where a viewer goes next, from the video's validated search phrases.

    The raw keyword signals are script n-grams ("There Nothing"), and the old
    templates added "mistakes to avoid" and a fixed "YouTube Growth System"
    playlist to every video, including emotional quote Shorts.
    """

    phrases = [_phrase(item) for item in (related_phrases or []) if str(item).strip()]
    hub = phrases[0] if phrases else ""
    # "Watch next" must be a different search, not a variant of this one.
    phrases = [hub, *diverse_followups(hub, phrases)] if hub else phrases
    if short_form:
        return {
            "next_video_hook": f"Follow with another Short on {hub.lower()}." if hub else "Follow with another Short on the same theme.",
            "pinned_comment_funnel": "Pin a comment that links the next Short in the same series.",
            "playlist_positioning": f"A Shorts series on {hub.lower()}" if hub else "A Shorts series on this theme",
        }
    return {
        "next_video_hook": f"Watch next: {phrases[1] if len(phrases) > 1 else hub}" if hub else "Watch next: the closest related video on your channel",
        "pinned_comment_funnel": (
            f"Pin a comment that points viewers to your video on {phrases[1].lower()}." if len(phrases) > 1
            else "Pin a comment that points viewers to your most closely related video."
        ),
        "playlist_positioning": f"A playlist on {hub.lower()}" if hub else "A playlist on this subject",
    }


def build_binge_bridge(
    *,
    related_phrases: list[str] | None = None,
    short_form: bool = False,
) -> str:
    phrases = [str(item).strip() for item in (related_phrases or []) if str(item).strip()]
    if short_form:
        return (
            "End on the complete line and keep a clean loop; follow with another Short on "
            f"{phrases[0] if phrases else 'the same theme'} so viewers who finish this one see the next."
        )
    if phrases:
        return (
            f"Close by naming what the next video covers ({phrases[1] if len(phrases) > 1 else phrases[0]}) "
            "so viewers have a concrete reason to keep watching."
        )
    return "Close by naming what the next video covers so viewers have a concrete reason to keep watching."
