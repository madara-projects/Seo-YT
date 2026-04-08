from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, List


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _days_since(published_at: str | None) -> float:
    if not published_at:
        return 365.0

    normalized = published_at.replace("Z", "+00:00")
    try:
        published_dt = datetime.fromisoformat(normalized)
    except ValueError:
        return 365.0

    if published_dt.tzinfo is None:
        published_dt = published_dt.replace(tzinfo=timezone.utc)

    delta = datetime.now(timezone.utc) - published_dt
    return max(delta.total_seconds() / 86400, 1.0)


def _build_opportunity_reasons(
    views_per_day: float,
    views_per_subscriber: float,
    engagement_density: float,
    subscribers: int,
    days_live: float,
) -> list[str]:
    reasons: list[str] = []

    if views_per_day >= 1000:
        reasons.append("Strong daily view velocity suggests current audience pull.")
    elif views_per_day >= 250:
        reasons.append("Steady daily view velocity shows the topic is moving.")

    if views_per_subscriber >= 5:
        reasons.append("Views are far above channel size, which is a classic outlier signal.")
    elif views_per_subscriber >= 1:
        reasons.append("Views are keeping up well against the creator's subscriber base.")

    if engagement_density >= 1.5:
        reasons.append("Comments and likes are dense enough to hint at strong viewer response.")
    elif engagement_density >= 0.5:
        reasons.append("Engagement is healthy enough to support continued distribution.")

    if subscribers and subscribers <= 10000:
        reasons.append("This comes from a smaller channel, which makes breakout performance more meaningful.")

    if days_live <= 7:
        reasons.append("The video is recent, so the trend signal is still fresh.")
    elif days_live <= 30:
        reasons.append("The video is still recent enough to matter for near-term topic selection.")

    if not reasons:
        reasons.append("The topic has some traction, but the signal is not yet strong enough to call it a clear breakout.")

    return reasons[:4]


def _parse_duration_seconds(duration: str | None) -> int:
    if not duration:
        return 0

    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if not match:
        return 0

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return (hours * 3600) + (minutes * 60) + seconds


def _get_regional_weight(region: str, primary_language: str) -> float:
    """Apply regional and language-aware weighting to YouTube results.
    
    Favors local/regional results for regional markets, global results for global audiences.
    """
    lowered_region = region.lower()
    lowered_language = primary_language.lower()
    
    # Regional markets get boosted weights for local content
    if lowered_region in {"india", "tamil nadu", "sri lanka", "gulf"}:
        # Regional/local audiences
        if lowered_language in {"tamil", "tanglish"}:
            # Strong local language preference - boost local results significantly
            return 1.35
        else:
            # Regional but English language - moderate boost
            return 1.15
    
    # Diaspora and local audiences in global settings
    if lowered_language in {"tamil", "tanglish"} and lowered_region in {"global", "worldwide"}:
        # Tanglish/Tamil content has specific global appeal
        return 1.1
    
    # Default global/English content
    return 1.0



def score_outliers(youtube_results: List[dict[str, Any]], region: str = "global", primary_language: str = "english") -> List[dict[str, Any]]:
    """Score fetched videos for small-channel outlier potential with region-aware weighting."""

    scored: List[dict[str, Any]] = []
    
    # Apply regional weighting
    regional_weight = _get_regional_weight(region, primary_language)

    for result in youtube_results:
        views = _to_int(result.get("view_count"))
        likes = _to_int(result.get("like_count"))
        comments = _to_int(result.get("comment_count"))
        subscribers = _to_int(result.get("subscriber_count"))
        days_live = _days_since(result.get("published_at"))
        duration_seconds = _parse_duration_seconds(result.get("duration"))

        views_per_day = views / days_live
        views_per_subscriber = views / max(subscribers, 1)
        length_normalization = 1.2 if 60 <= duration_seconds <= 1200 else 0.95 if duration_seconds else 1.0
        retention_proxy = (
            ((comments / max(views, 1)) * 1000) + (likes / max(views, 1))
        ) * length_normalization
        engagement_density = retention_proxy
        recency_multiplier = 2.0 if days_live <= 7 else 1.5 if days_live <= 30 else 1.15
        repeatability_multiplier = 1.25 if subscribers and subscribers <= 10000 else 1.0

        outlier_score = (
            views_per_day
            * views_per_subscriber
            * max(engagement_density, 0.05)
            * recency_multiplier
            * repeatability_multiplier
            * regional_weight  # Apply regional weighting
        )

        scored.append(
            {
                **result,
                "views_per_day": round(views_per_day, 2),
                "views_per_subscriber": round(views_per_subscriber, 2),
                "engagement_density": round(engagement_density, 4),
                "retention_proxy": round(retention_proxy, 4),
                "length_normalization": round(length_normalization, 2),
                "outlier_score": round(outlier_score, 2),
                "regional_weight": round(regional_weight, 2),
                "small_channel_outlier": bool(subscribers and subscribers <= 10000 and views >= 100000),
                "opportunity_reasons": _build_opportunity_reasons(
                    views_per_day=views_per_day,
                    views_per_subscriber=views_per_subscriber,
                    engagement_density=engagement_density,
                    subscribers=subscribers,
                    days_live=days_live,
                ),
            }
        )

    return sorted(scored, key=lambda item: item["outlier_score"], reverse=True)
