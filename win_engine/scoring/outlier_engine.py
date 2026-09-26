from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List

from win_engine.core.iso_duration import duration_seconds


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _days_since(published_at: Any) -> float | None:
    if not published_at:
        return None

    normalized = str(published_at).replace("Z", "+00:00")
    try:
        published_dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if published_dt.tzinfo is None:
        published_dt = published_dt.replace(tzinfo=timezone.utc)

    delta = datetime.now(timezone.utc) - published_dt
    return max(delta.total_seconds() / 86400, 1.0)


def _rounded(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


def _build_opportunity_reasons(
    views_per_day: float | None,
    views_per_subscriber: float | None,
    engagement_density: float | None,
    subscribers: int | None,
    days_live: float | None,
    missing: list[str],
) -> list[str]:
    reasons: list[str] = []

    if missing:
        reasons.append(f"Outlier score unavailable: no usable {' or '.join(missing)} for this video.")

    if views_per_day is not None:
        if views_per_day >= 1000:
            reasons.append("Strong daily view velocity suggests current audience pull.")
        elif views_per_day >= 250:
            reasons.append("Steady daily view velocity shows the topic is moving.")

    if views_per_subscriber is not None:
        if views_per_subscriber >= 5:
            reasons.append("Views are far above channel size, which is a classic outlier signal.")
        elif views_per_subscriber >= 1:
            reasons.append("Views are keeping up well against the creator's subscriber base.")

    if engagement_density is not None:
        if engagement_density >= 1.5:
            reasons.append("Comments and likes are dense enough to hint at strong viewer response.")
        elif engagement_density >= 0.5:
            reasons.append("Engagement is healthy enough to support continued distribution.")

    if subscribers and subscribers <= 10000:
        reasons.append("This comes from a smaller channel, which makes breakout performance more meaningful.")

    if days_live is not None:
        if days_live <= 7:
            reasons.append("The video is recent, so the trend signal is still fresh.")
        elif days_live <= 30:
            reasons.append("The video is still recent enough to matter for near-term topic selection.")

    if not reasons:
        reasons.append("The topic has some traction, but the signal is not yet strong enough to call it a clear breakout.")

    return reasons[:4]


def score_outliers(youtube_results: List[dict[str, Any]]) -> List[dict[str, Any]]:
    """Score fetched videos for small-channel outlier potential.

    A row without a view count, subscriber count or publish date gets no score
    and sorts after every scored row. Filling those gaps with zeros made a
    hidden subscriber count look like a million-fold outlier.
    """

    scored: List[dict[str, Any]] = []

    for result in youtube_results:
        views = _optional_int(result.get("view_count"))
        likes = _optional_int(result.get("like_count"))
        comments = _optional_int(result.get("comment_count"))
        subscribers = _optional_int(result.get("subscriber_count"))
        days_live = _days_since(result.get("published_at"))
        length = duration_seconds(result.get("duration"))

        views_per_day = views / days_live if views is not None and days_live is not None else None
        # Zero subscribers gives no ratio at all, rather than one against a single subscriber.
        views_per_subscriber = views / subscribers if views is not None and subscribers else None
        length_normalization = 1.2 if length is not None and 60 <= length <= 1200 else 0.95 if length else 1.0
        # Comments per thousand views plus likes per view. A hidden count adds
        # nothing; with both hidden there is no engagement figure.
        engagement_density = (
            (((comments or 0) / views) * 1000 + (likes or 0) / views) * length_normalization
            if views and (likes is not None or comments is not None) else None
        )
        missing = [
            label for label, absent in (
                ("view count", views is None), ("subscriber count", not subscribers), ("publish date", days_live is None),
            ) if absent
        ]

        outlier_score = None
        if not missing:
            recency_multiplier = 2.0 if days_live <= 7 else 1.5 if days_live <= 30 else 1.15
            repeatability_multiplier = 1.25 if subscribers <= 10000 else 1.0
            outlier_score = (
                views_per_day
                * views_per_subscriber
                * max(engagement_density or 0.0, 0.05)
                * recency_multiplier
                * repeatability_multiplier
            )

        scored.append(
            {
                **result,
                "views_per_day": _rounded(views_per_day, 2),
                "views_per_subscriber": _rounded(views_per_subscriber, 2),
                "engagement_density": _rounded(engagement_density, 4),
                # Older name for engagement_density, kept for existing readers; it
                # never measured retention.
                "retention_proxy": _rounded(engagement_density, 4),
                "length_normalization": round(length_normalization, 2),
                "outlier_score": _rounded(outlier_score, 2),
                # Kept at 1.0 for existing readers. A constant weight on every row
                # changed no ranking; the region now reaches YouTube as regionCode.
                "regional_weight": 1.0,
                "small_channel_outlier": bool(subscribers and views is not None and subscribers <= 10000 and views >= 100000),
                "opportunity_reasons": _build_opportunity_reasons(
                    views_per_day=views_per_day,
                    views_per_subscriber=views_per_subscriber,
                    engagement_density=engagement_density,
                    subscribers=subscribers,
                    days_live=days_live,
                    missing=missing,
                ),
            }
        )

    # Unscored rows keep their search order behind every scored row.
    return sorted(scored, key=lambda item: (item["outlier_score"] is not None, item["outlier_score"] or 0), reverse=True)
