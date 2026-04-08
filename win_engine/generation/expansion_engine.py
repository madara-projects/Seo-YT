from __future__ import annotations

from typing import Any


def build_chapters(script: str, keyword_signals: list[dict[str, Any]]) -> list[dict[str, str]]:
    keywords = [str(item.get("keyword", "")).strip().title() for item in keyword_signals[:4] if item.get("keyword")]
    defaults = keywords or ["Hook", "Strategy", "Breakdown", "Next Steps"]
    timestamps = ["00:00", "00:30", "02:00", "04:00"]
    return [
        {"timestamp": timestamp, "title": title}
        for timestamp, title in zip(timestamps, defaults, strict=False)
    ]


def build_session_expansion(title: str, keyword_signals: list[dict[str, Any]]) -> dict[str, Any]:
    keywords = [str(item.get("keyword", "")).strip().title() for item in keyword_signals[:3] if item.get("keyword")]
    next_video = f"Watch next: {keywords[0]} mistakes to avoid" if keywords else "Watch next: Advanced YouTube packaging mistakes"
    pinned_comment = (
        f"If this video helped, the next step is to apply the same system to {keywords[1]}."
        if len(keywords) > 1
        else "If this video helped, the next step is to apply the same system to your next upload."
    )
    playlist = "YouTube Growth System"

    return {
        "next_video_hook": next_video,
        "pinned_comment_funnel": pinned_comment,
        "playlist_positioning": playlist,
    }


def build_binge_bridge(title: str, content_angle: str) -> str:
    return (
        f"Now that we covered {title}, the next video should deepen the {content_angle.lower()} angle "
        "with a tighter case study or a stronger packaging teardown."
    )
