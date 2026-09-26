"""Persist real channel-video snapshots and derive conservative learning signals."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from win_engine.analysis.text_tokens import unicode_words
from win_engine.feedback.migrations import connect_managed
from win_engine.feedback.evidence_policy import evidence_level, sample_is_eligible
from win_engine.feedback.history_store import HistoryStore, comparable_format, format_filter_values, known_filter


def save_video_snapshots(database_path: str, videos: list[dict[str, Any]], *, channel_id: str) -> None:
    """Store one sync of a channel's uploads; only the connected channel's are shown."""
    now = datetime.now(timezone.utc).isoformat()
    rows = [
        # A count YouTube did not report is stored as unknown, never as zero.
        (v.get("video_id"), channel_id, now, v.get("published_at"), v.get("title"), _optional_num(v.get("views")), _optional_num(v.get("estimatedMinutesWatched")), _optional_num(v.get("averageViewDuration")), _optional_num(v.get("averageViewPercentage")), _optional_num(v.get("likes")), _optional_num(v.get("comments")), _optional_num(v.get("shares")), _optional_num(v.get("subscribersGained")))
        for v in videos if v.get("video_id")
    ]
    if not rows:
        return
    with connect_managed(database_path) as connection:
        connection.executemany("INSERT INTO owned_video_snapshots (video_id,channel_id,captured_at,published_at,title,views,watch_minutes,average_view_duration,average_view_percentage,likes,comments,shares,subscribers_gained) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)


def learning_summary(
    database_path: str,
    *,
    format_filter: str | None = None,
    language_filter: str | None = None,
    snapshot_window: str = "24h",
) -> dict[str, Any]:
    with connect_managed(database_path) as connection:
        # The connected channel's uploads, not those of a channel connected before.
        rows = connection.execute("""SELECT s.video_id,s.title,s.views,s.average_view_duration,s.average_view_percentage,s.likes,s.comments,s.published_at FROM owned_video_snapshots s INNER JOIN (SELECT video_id,MAX(captured_at) captured_at FROM owned_video_snapshots GROUP BY video_id) latest ON latest.video_id=s.video_id AND latest.captured_at=s.captured_at WHERE s.channel_id=(SELECT channel_id FROM youtube_channel_connection WHERE id=1) ORDER BY s.views DESC""").fetchall()
    videos = [{"video_id": r[0], "title": r[1], "views": r[2], "average_view_duration": r[3], "average_view_percentage": r[4], "likes": r[5], "comments": r[6], "published_at": r[7]} for r in rows]
    store = HistoryStore(database_path)
    links = store.published_video_links_list()
    formats = format_filter_values(format_filter)
    language_filter = known_filter(language_filter)
    comparable_links: list[dict[str, Any]] = []
    linked: list[dict[str, Any]] = []
    for link in links:
        comparable = link.get("comparable_metadata") or {}
        effective_format = comparable_format(comparable.get("format") or link.get("format")) or "unknown"
        effective_language = comparable.get("language") or link.get("language")
        if formats is not None and effective_format not in formats:
            continue
        if language_filter and effective_language != language_filter:
            continue
        comparable_links.append(link)
        snapshot = store.completed_evidence_snapshot(str(link.get("youtube_video_id") or ""), snapshot_window)
        policy_link = dict(link)
        policy_link["format"] = effective_format
        policy_link["language"] = effective_language
        if not snapshot or not sample_is_eligible(policy_link, snapshot, expected_window=snapshot_window):
            continue
        metadata = link.get("youtube_metadata") if isinstance(link.get("youtube_metadata"), dict) else {}
        views = int(snapshot["views"])
        age_hours = float(snapshot.get("age_hours") or 0)
        linked.append({
            "video_id": link.get("youtube_video_id"),
            "published_at": link.get("published_at"),
            "title": str(metadata.get("title") or link.get("selected_title") or link.get("package_topic") or ""),
            "generated_title": str(link.get("package_topic") or ""),
            "title_used": _normalized(str(metadata.get("title") or link.get("selected_title") or "")) == _normalized(str(link.get("package_topic") or "")),
            "views": views,
            "views_per_day": round(views / max(age_hours / 24, 1), 2),
            "average_view_percentage": _optional_num(snapshot.get("avg_view_percentage")),
            # The window's own counts: lifetime metadata covers a different time
            # range, and a count the window did not report stays unknown.
            "likes": None if snapshot.get("likes") is None else int(snapshot["likes"]),
            "comments": None if snapshot.get("comments") is None else int(snapshot["comments"]),
            "age_hours": round(age_hours, 1),
            "snapshot_window": snapshot.get("snapshot_window"),
            "captured_at": snapshot.get("captured_at"),
            "actual_tags": [str(tag) for tag in (metadata.get("tags") or [])],
            "generated_tags": [str(tag) for tag in (link.get("selected_tags") or [])],
            "comparable_metadata": comparable,
        })
    eligible = linked
    eligible.sort(key=lambda item: (item["views_per_day"], item.get("average_view_percentage") or 0), reverse=True)
    sample = len(eligible)
    level = evidence_level(sample)
    if not level.learning_allowed:
        recommendation = (
            f"Collect verified completed {snapshot_window} snapshots until at least {level.minimum_samples} comparable linked videos are mature "
            f"(currently {sample}); do not change generation strategy from the early sample."
        )
        confidence = "collecting"
    else:
        best = eligible[0]
        recommendation = (
            f"{level.label}: '{best.get('title') or 'the leading comparable video'}' currently leads this "
            f"{snapshot_window} cohort by age-normalized views. Treat this as historical evidence, not a guarantee."
        )
        confidence = level.key
    return {
        "sample_size": sample,
        "connected_video_count": len(videos),
        "linked_video_count": len(comparable_links),
        "confidence": confidence,
        "evidence_level": level.key,
        "confidence_label": level.label,
        "learning_allowed": level.learning_allowed,
        "snapshot_window": snapshot_window,
        # Ranking a sample below the evidence threshold would present noise as a pattern.
        "best_videos": eligible[:3] if level.learning_allowed else [],
        "weakest_videos": list(reversed(eligible[-3:])) if level.learning_allowed else [],
        "linked_evidence": linked,
        "recommendation": recommendation,
    }


def _optional_num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalized(value: str) -> str:
    return " ".join(unicode_words(value))
