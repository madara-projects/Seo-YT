from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any


def build_channel_intelligence(youtube_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize repeated patterns across the channels in the current result set."""

    if not youtube_results:
        return {
            "dominant_channel_size": "unknown",
            "dominant_video_length": "unknown",
            "dominant_packaging_style": "unknown",
            "summary": "Not enough YouTube results yet to infer channel-level patterns.",
        }

    size_counter: Counter[str] = Counter()
    length_counter: Counter[str] = Counter()
    packaging_counter: Counter[str] = Counter()

    for item in youtube_results:
        size_counter[_channel_size_bucket(int(item.get("subscriber_count") or 0))] += 1
        length_counter[_duration_bucket(str(item.get("duration") or ""))] += 1
        packaging_counter[_packaging_style(str(item.get("title") or ""))] += 1

    dominant_channel_size = size_counter.most_common(1)[0][0]
    dominant_video_length = length_counter.most_common(1)[0][0]
    dominant_packaging_style = packaging_counter.most_common(1)[0][0]

    summary = (
        f"Most visible competitors in this topic are {dominant_channel_size} channels using "
        f"{dominant_video_length} videos with a {dominant_packaging_style} packaging style."
    )

    return {
        "dominant_channel_size": dominant_channel_size,
        "dominant_video_length": dominant_video_length,
        "dominant_packaging_style": dominant_packaging_style,
        "summary": summary,
    }


def build_upload_timing(youtube_results: list[dict[str, Any]], region: str = "global") -> dict[str, Any]:
    """Describe competitor publish-time patterns without claiming causal performance evidence."""
    if not youtube_results:
        return {
            "recommended_day": "Use channel audience data",
            "recommended_time_utc": "Not enough evidence",
            "recommended_time_ist": "Not enough evidence",
            "target_region": region.upper() if region else "GLOBAL",
            "confidence": "LOW",
            "sample_size": 0,
            "reasoning": (
                "No usable publication timestamps were found. Check YouTube Studio's audience activity "
                "data after the channel has enough viewers."
            ),
        }

    days: Counter[str] = Counter()
    hours: Counter[int] = Counter()
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    usable_timestamps = 0
    for item in youtube_results:
        pub = str(item.get("published_at") or "")
        if pub and len(pub) >= 19:
            try:
                dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                dt_ist = dt.astimezone(timezone(timedelta(minutes=330)))
                days[day_names[dt_ist.weekday()]] += 1
                hours[dt.hour] += 1
                usable_timestamps += 1
            except Exception:
                pass

    if not usable_timestamps:
        return {
            "recommended_day": "Use channel audience data",
            "recommended_time_utc": "Not enough evidence",
            "recommended_time_ist": "Not enough evidence",
            "target_region": region.upper() if region else "GLOBAL",
            "confidence": "LOW",
            "sample_size": 0,
            "reasoning": "The research results did not contain valid publication timestamps.",
        }

    best_day = days.most_common(1)[0][0]
    best_hour = hours.most_common(1)[0][0]

    start_h = max(0, best_hour - 1)
    end_h = min(23, best_hour + 2)

    ist_start_min = (start_h * 60 + 330) % 1440
    ist_end_min = (end_h * 60 + 330) % 1440
    ist_start_str = f"{(ist_start_min//60)%12 or 12}:{ist_start_min%60:02d} {'PM' if (ist_start_min//60)>=12 else 'AM'}"
    ist_end_str = f"{(ist_end_min//60)%12 or 12}:{ist_end_min%60:02d} {'PM' if (ist_end_min//60)>=12 else 'AM'}"
    ist_time_range = f"{ist_start_str} - {ist_end_str} IST (Indian Time)"

    return {
        "recommended_day": best_day,
        "recommended_time_utc": f"{start_h:02d}:00 - {end_h:02d}:00 UTC",
        "recommended_time_ist": ist_time_range,
        "target_region": region.upper() if region else "GLOBAL",
        "confidence": "MEDIUM" if usable_timestamps >= 10 else "LOW",
        "sample_size": usable_timestamps,
        "reasoning": (
            f"Observed {usable_timestamps} relevant-video publication timestamps; the most common "
            f"pattern was {best_day}, around {ist_time_range}. This shows when competitors published, "
            "not that this timing caused their performance. Prefer your YouTube Studio audience data "
            "when available."
        ),
    }


def build_content_graph_strategy(
    primary_topic: str,
    secondary_topic: str,
    angle: str,
    keyword_signals: list[dict[str, Any]],
) -> dict[str, Any]:
    """Suggest how this video can branch into a small content graph."""

    next_topics = [
        _humanize_keyword(str(item.get("keyword", "")))
        for item in keyword_signals
        if str(item.get("keyword", "")).strip()
    ]
    next_topics = [topic for topic in next_topics if topic and topic.lower() not in {primary_topic.lower(), secondary_topic.lower()}]

    spoke_one = next_topics[0] if len(next_topics) > 0 else f"{primary_topic} mistakes"
    spoke_two = next_topics[1] if len(next_topics) > 1 else f"{secondary_topic} tutorial"

    return {
        "hub_topic": primary_topic,
        "supporting_topics": [secondary_topic, spoke_one, spoke_two],
        "series_plan": [
            f"{primary_topic}: core {angle.lower()} breakdown",
            f"{spoke_one}: follow-up proof or case study",
            f"{spoke_two}: tactical tutorial or checklist",
        ],
        "bridge_strategy": (
            f"Use this video as the hub, then branch into {spoke_one} and {spoke_two} to keep viewers "
            f"inside a tighter topic cluster around {primary_topic}."
        ),
    }


def _channel_size_bucket(subscriber_count: int) -> str:
    if subscriber_count < 10000:
        return "small"
    if subscriber_count < 100000:
        return "mid-sized"
    return "large"


def _duration_bucket(duration: str) -> str:
    if "PT" not in duration:
        return "unknown"
    if "M" not in duration and "H" not in duration:
        return "short-form"

    minutes = 0
    if "H" in duration:
        hour_part = duration.split("PT", 1)[1].split("H", 1)[0]
        minutes += int(hour_part or 0) * 60
        remainder = duration.split("H", 1)[1]
    else:
        remainder = duration.split("PT", 1)[1]

    if "M" in remainder:
        minutes_part = remainder.split("M", 1)[0]
        minutes += int(minutes_part or 0)

    if minutes <= 1:
        return "short-form"
    if minutes <= 8:
        return "mid-length"
    return "long-form"


def _packaging_style(title: str) -> str:
    lower = title.lower()
    if any(token in lower for token in ["i tried", "i tested", "for 30 days", "for 7 days"]):
        return "experiment"
    if any(token in lower for token in ["how to", "guide", "tutorial"]):
        return "search-led"
    if any(token in lower for token in ["why", "shocking", "secret", "mistake"]):
        return "curiosity-led"
    return "hybrid"


def _humanize_keyword(value: str) -> str:
    return " ".join(part.capitalize() for part in value.replace("_", " ").split())
