from __future__ import annotations

from typing import Any

from win_engine.analysis.generation_quality import is_short_content
from win_engine.analysis.strategy_layer import diverse_followups


def build_chapters(
    script: str,
    keyword_signals: list[dict[str, Any]],
    creator_brief: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    brief = creator_brief or {}
    if is_short_content(script, brief):
        return []
    duration = brief.get("duration_seconds")
    if duration is not None and float(duration) < 300:
        return []
    if len(script.split()) < 180:
        return []
    keywords = [str(item.get("keyword", "")).strip().title() for item in keyword_signals[:4] if item.get("keyword")]
    if len(keywords) < 2:
        return []
    defaults = keywords
    timestamps = ["00:00", "00:30", "02:00", "04:00"]
    return [
        {"timestamp": timestamp, "title": title}
        for timestamp, title in zip(timestamps, defaults, strict=False)
    ]


def _phrase(value: str) -> str:
    text = " ".join(str(value or "").split())
    return text[:1].upper() + text[1:]


def build_session_expansion(
    title: str,
    keyword_signals: list[dict[str, Any]],
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
    if not phrases:
        phrases = [_phrase(item.get("keyword", "")) for item in keyword_signals[:3] if item.get("keyword")]
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
    title: str,
    content_angle: str,
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
