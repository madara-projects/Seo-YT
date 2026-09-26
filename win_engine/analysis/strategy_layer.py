from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from math import log10
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from win_engine.analysis.numbers import optional_number
from win_engine.analysis.source_cues import is_short_video
from win_engine.core.iso_duration import duration_seconds


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
        # A hidden subscriber count or a failed channel lookup is unknown, not
        # 0, which made every such channel "small".
        size_counter[_channel_size_bucket(optional_number(item.get("subscriber_count")))] += 1
        length_counter[_duration_bucket(item.get("duration"))] += 1
        packaging_counter[_packaging_style(str(item.get("title") or ""))] += 1

    dominant_channel_size = size_counter.most_common(1)[0][0]
    dominant_video_length = length_counter.most_common(1)[0][0]
    dominant_packaging_style = packaging_counter.most_common(1)[0][0]

    size_phrase = "channels of unknown size" if dominant_channel_size == "unknown" else f"{dominant_channel_size} channels"
    length_phrase = "videos of unknown length" if dominant_video_length == "unknown" else f"{dominant_video_length} videos"
    summary = (
        f"Most visible competitors in this topic are {size_phrase} using "
        f"{length_phrase} with a {dominant_packaging_style} packaging style."
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
    short_form: bool | None = None,
) -> dict[str, Any]:
    """Return honest, timezone-explicit upload guidance from the best available evidence.

    ``short_form`` is the caller's Short decision; without one the format decides.
    """

    zone_name, zone, timezone_source = _resolve_timezone(timezone_name, channel_analytics)
    local_now = _aware_now(now).astimezone(zone)
    if short_form is None:
        short_form = is_short_video("", {"video_format": video_format})
    best_day, start_hour, end_hour = _general_window(short_form, strategy)
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
        # Competitor publication timestamps are descriptive metadata, not
        # evidence of when this channel's viewers are active. Never turn them
        # into a personalized or allegedly stronger upload recommendation.

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
    if not personalized:
        today_recommendation = (
            f"Suggested starting window: {today_time} {zone_name}. "
            "There is insufficient channel evidence to rank today against other days."
        )
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
    public_window = _publication_window(youtube_results, zone)
    result["public_publication_observation"] = (
        {
            "day": public_window[0],
            "time": _format_hour_window(public_window[1], public_window[2]),
            "sample_size": public_window[3],
            "recommendation_evidence": False,
            "note": "Descriptive competitor publication pattern only; it is not used to recommend upload timing.",
        }
        if public_window and public_window[3] >= 5 else None
    )
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


def _general_window(short_form: bool, strategy: str) -> tuple[str, int, int]:
    text = str(strategy or "").casefold()
    if short_form:
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


def diverse_followups(hub: str, phrases: list[str], limit: int = 2) -> list[str]:
    """Follow-up topics that are different searches, not variants of the hub.

    "cold brew" -> "cold brew coffee" is the same video twice; "mason jar
    coffee" or "coffee brewing methods" is a real next video.
    """

    def overlap(phrase: str) -> float:
        return overlap_between(phrase, hub)

    candidates = [phrase for phrase in phrases if phrase.casefold() != hub.casefold()]
    distinct = [phrase for phrase in candidates if overlap(phrase) < 0.5]
    if len(distinct) < limit:
        distinct += [phrase for phrase in sorted(candidates, key=overlap)
                     if phrase not in distinct and overlap(phrase) < 0.8]
    chosen: list[str] = []
    for phrase in distinct:
        if all(overlap_between(phrase, other) < 0.6 for other in chosen):
            chosen.append(phrase)
        if len(chosen) >= limit:
            break
    return chosen


def overlap_between(left: str, right: str) -> float:
    a, b = set(left.casefold().split()), set(right.casefold().split())
    return len(a & b) / max(len(a | b), 1)


def build_content_graph_strategy(
    primary_topic: str,
    *,
    related_phrases: list[str] | None = None,
    short_form: bool = False,
) -> dict[str, Any]:
    """Suggest how this video can branch into a small content graph.

    Spokes come only from ``related_phrases``, the video's validated search
    phrases. Script n-gram keyword signals turned a quote into a series on
    "There Nothing" and "More Painful", and without phrases the old path
    invented "<topic> mistakes" and "<topic> tutorial" spokes.
    """

    phrases = [" ".join(str(item).split()) for item in (related_phrases or []) if str(item).strip()]
    # The strongest validated phrase names the hub; the creator's lead
    # sentence ("how to make cold brew coffee at home without any special
    # equipment", or a whole Tamil sentence) is not a series name.
    hub = (phrases[0] if phrases else primary_topic).strip()
    spokes = diverse_followups(hub, phrases)
    if short_form:
        series = [f"{hub}: this Short"] + [f"{spoke}: a companion Short on the same theme" for spoke in spokes]
        bridge = ("Group these Shorts into one series so a viewer who finishes one is shown the next."
                  if spokes else "Group this Short with others on the same theme so viewers move from one to the next.")
    else:
        series = [f"{hub}: this video"] + [f"{spoke}: a follow-up video" for spoke in spokes]
        bridge = (f"Link the follow-ups from this video's end screen and description to keep viewers around {hub}."
                  if spokes else f"Plan the next video on a closely related search to keep viewers around {hub}.")
    return {
        "hub_topic": hub,
        "supporting_topics": spokes,
        "series_plan": series,
        "bridge_strategy": bridge,
        "basis": "validated_search_phrases",
    }


def _channel_size_bucket(subscriber_count: float | None) -> str:
    if subscriber_count is None:
        return "unknown"
    if subscriber_count < 10000:
        return "small"
    if subscriber_count < 100000:
        return "mid-sized"
    return "large"


def _duration_bucket(duration: Any) -> str:
    seconds = duration_seconds(duration)
    if seconds is None:
        return "unknown"
    if seconds < 120:
        return "short-form"
    if seconds < 540:
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
