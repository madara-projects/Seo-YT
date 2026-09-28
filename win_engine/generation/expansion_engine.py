from __future__ import annotations

from itertools import pairwise
from typing import Any

from win_engine.analysis.generation_quality import is_short_content
from win_engine.analysis.source_cues import timestamp_line, timestamp_seconds
from win_engine.analysis.strategy_layer import diverse_followups


def _timestamp_runs(text: str) -> list[list[dict[str, str]]]:
    """Consecutive timestamp lines, one run per block; blank lines do not end a run."""

    runs: list[list[dict[str, str]]] = [[]]
    for line in text.splitlines():
        if not line.strip():
            continue
        parsed = timestamp_line(line)
        if parsed is None:
            if runs[-1]:
                runs.append([])
            continue
        runs[-1].append({"timestamp": parsed[1], "title": parsed[2]})
    return [run for run in runs if run]


def valid_chapters(chapters: Any) -> bool:
    """Whether YouTube builds chapters from this list (support.google.com/youtube/answer/9884579).

    The first timestamp is 0:00, there are at least three, and each chapter
    starts at least ten seconds after the one before it.
    """

    if not isinstance(chapters, list) or len(chapters) < 3:
        return False
    if not all(isinstance(item, dict) and str(item.get("title") or "").strip() for item in chapters):
        return False
    seconds = [timestamp_seconds(item.get("timestamp")) for item in chapters]
    return (None not in seconds and seconds[0] == 0
            and all(later - earlier >= 10 for earlier, later in pairwise(seconds)))


def chapter_block(chapters: Any) -> str:
    """The description lines for the creator's chapters ("0:00 Intro"), or "" when YouTube would reject them."""

    if not valid_chapters(chapters):
        return ""
    return "\n".join(f"{item['timestamp']} {' '.join(str(item['title']).split())}" for item in chapters)


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
        if valid_chapters(run):
            return run
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
