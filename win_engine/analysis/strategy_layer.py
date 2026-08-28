from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from math import log10
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


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


def build_upload_timing(
    youtube_results: list[dict[str, Any]],
    region: str = "global",
    *,
    channel_analytics: dict[str, Any] | None = None,
    historical_videos: list[dict[str, Any]] | None = None,
    video_format: str = "",
    strategy: str = "balanced",
    timezone_name: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return honest, timezone-explicit upload guidance from the best available evidence."""

    zone_name, zone, timezone_source = _resolve_timezone(timezone_name, channel_analytics)
    local_now = _aware_now(now).astimezone(zone)
    best_day, start_hour, end_hour = _general_window(video_format, strategy)
    confidence = "LOW"
    basis = "general_recommendation"
    sample_size = 0
    personalized = False
    explanation = (
        "Personalized upload timing is not yet established. This is a general starting window, not "
        f"a prediction of reach. It uses the selected {video_format or 'video'} format and "
        f"{strategy or 'balanced'} strategy. Replace it with reliable YouTube Studio audience activity when available."
    )

    audience_window = _reliable_audience_window(channel_analytics)
    if audience_window:
        best_day, start_hour, end_hour, sample_size = audience_window
        confidence = "HIGH" if sample_size >= 28 else "MEDIUM"
        basis = "personal_audience_activity"
        personalized = True
        explanation = (
            f"Based on {sample_size} reliable connected-channel audience activity observations. This is "
            "personalized scheduling evidence, but it does not guarantee performance."
        )
    else:
        historical_window = _historical_window(historical_videos or [], zone)
        if historical_window:
            best_day, start_hour, end_hour, sample_size = historical_window
            confidence = "MEDIUM" if sample_size >= 10 else "LOW"
            basis = "historical_channel_data"
            personalized = True
            explanation = (
                f"Based on publication times and current performance for {sample_size} owned channel videos. "
                "This is an observed association, not evidence that timing caused performance."
            )
        else:
            public_window = _publication_window(youtube_results, zone)
            if public_window:
                best_day, start_hour, end_hour, sample_size = public_window
                confidence = "MEDIUM" if sample_size >= 10 else "LOW"
                basis = "public_research_pattern"
                explanation = (
                    f"Observed {sample_size} relevant public-video publication timestamps. This is a "
                    "non-personal competitor pattern and does not show that publishing then caused performance."
                )

    if timezone_source == "fallback_utc":
        explanation += " Channel or application timezone could not be resolved, so this result uses an explicit UTC fallback."

    recommended_time = _format_hour_window(start_hour, end_hour)
    today_time = recommended_time
    today_timezone = zone_name
    if local_now.strftime("%A") == best_day:
        passed = local_now.hour >= end_hour
        today_recommendation = (
            f"Today matches the strongest {basis.replace('_', ' ')} day, but this window has passed. "
            f"Use the next {best_day} window instead."
            if passed else
            "Today matches the strongest available day. Use the recommended window if it fits your publishing workflow."
        )
    else:
        next_date = _next_weekday(local_now, best_day)
        today_recommendation = (
            f"Today is a weaker-evidence day. If you must publish today, use {today_time} {zone_name}; "
            f"the next stronger window is {next_date.strftime('%A, %d %b')} at {recommended_time} {zone_name}."
        )

    utc_window = _window_in_utc(local_now, best_day, start_hour, end_hour, zone)
    result = {
        "recommended_day": best_day,
        "recommended_time": recommended_time,
        "timezone": zone_name,
        "confidence": confidence,
        "basis": basis,
        "today_recommendation": today_recommendation,
        "today_time": today_time,
        "today_timezone": today_timezone,
        "explanation": explanation,
        "sample_size": sample_size,
        "personalized": personalized,
        "timezone_source": timezone_source,
        "calculated_for_date": local_now.date().isoformat(),
        # Backward-compatible display fields used by existing history exports.
        "recommended_time_utc": utc_window,
        "recommended_time_ist": f"{recommended_time} {zone_name}",
        "target_region": region.upper() if region else "GLOBAL",
        "reasoning": explanation,
    }
    return result


def _resolve_timezone(name: str | None, analytics: dict[str, Any] | None) -> tuple[str, ZoneInfo, str]:
    analytics_name = str((analytics or {}).get("timezone") or "").strip()
    candidates = ((analytics_name, "connected_channel"), (str(name or "").strip(), "application_setting"))
    for candidate, source in candidates:
        if not candidate:
            continue
        try:
            return candidate, ZoneInfo(candidate), source
        except ZoneInfoNotFoundError:
            continue
    return "UTC", ZoneInfo("UTC"), "fallback_utc"


def _aware_now(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    return current.replace(tzinfo=timezone.utc) if current.tzinfo is None else current


def _parse_datetime(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except (TypeError, ValueError):
        return None


def _reliable_audience_window(analytics: dict[str, Any] | None) -> tuple[str, int, int, int] | None:
    activity = (analytics or {}).get("audience_activity")
    if not isinstance(activity, dict) or activity.get("reliable") is not True:
        return None
    sample_size = int(activity.get("sample_size") or 0)
    rows = activity.get("windows") or activity.get("rows") or []
    if sample_size < 7 or not isinstance(rows, list):
        return None
    valid = [row for row in rows if isinstance(row, dict) and str(row.get("day") or "").title() in _DAY_NAMES]
    if not valid:
        return None
    best = max(valid, key=lambda row: float(row.get("activity") or row.get("score") or 0))
    try:
        start = max(0, min(23, int(best.get("start_hour") or 0)))
        end = max(start + 1, min(24, int(best.get("end_hour") or start + 2)))
    except (TypeError, ValueError):
        return None
    return str(best["day"]).title(), start, end, sample_size


def _historical_window(videos: list[dict[str, Any]], zone: ZoneInfo) -> tuple[str, int, int, int] | None:
    rows: list[tuple[datetime, float]] = []
    for item in videos:
        parsed = _parse_datetime(item.get("published_at"))
        views = item.get("views")
        retention = item.get("average_view_percentage")
        if parsed is None or (views is None and retention is None):
            continue
        weight = 1.0 + log10(max(0, int(views or 0)) + 1) + max(0.0, float(retention or 0)) / 100.0
        rows.append((parsed.astimezone(zone), weight))
    if len(rows) < 5:
        return None
    return _weighted_window(rows, len(rows))


def _publication_window(items: list[dict[str, Any]], zone: ZoneInfo) -> tuple[str, int, int, int] | None:
    rows = [parsed.astimezone(zone) for parsed in (_parse_datetime(item.get("published_at")) for item in items) if parsed]
    if not rows:
        return None
    return _weighted_window([(row, 1.0) for row in rows], len(rows))


def _weighted_window(rows: list[tuple[datetime, float]], sample_size: int) -> tuple[str, int, int, int]:
    window_scores: Counter[tuple[str, int]] = Counter()
    for parsed, weight in rows:
        window_scores[(parsed.strftime("%A"), parsed.hour)] += weight
    (best_day, best_hour), _ = window_scores.most_common(1)[0]
    return best_day, max(0, best_hour - 1), min(24, best_hour + 2), sample_size


def _general_window(video_format: str, strategy: str) -> tuple[str, int, int]:
    text = f"{video_format} {strategy}".casefold()
    if any(token in text for token in ("short", "quote")):
        return "Thursday", 18, 20
    if "browse" in text:
        return "Friday", 18, 20
    if "search" in text:
        return "Tuesday", 17, 19
    return "Wednesday", 17, 19


def _format_hour(hour: int) -> str:
    bounded = hour % 24
    return f"{bounded % 12 or 12}:00 {'PM' if bounded >= 12 else 'AM'}"


def _format_hour_window(start: int, end: int) -> str:
    return f"{_format_hour(start)} - {_format_hour(end)}"


_DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _next_weekday(now: datetime, day_name: str) -> datetime:
    target = _DAY_NAMES.index(day_name)
    days_ahead = (target - now.weekday()) % 7 or 7
    return now + timedelta(days=days_ahead)


def _window_in_utc(now: datetime, day: str, start: int, end: int, zone: ZoneInfo) -> str:
    date = _next_weekday(now, day).date() if now.strftime("%A") != day else now.date()
    start_local = datetime(date.year, date.month, date.day, start, tzinfo=zone).astimezone(timezone.utc)
    end_date = date + timedelta(days=1) if end >= 24 else date
    end_local = datetime(end_date.year, end_date.month, end_date.day, end % 24, tzinfo=zone).astimezone(timezone.utc)
    return f"{start_local:%H:%M} - {end_local:%H:%M} UTC"


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
