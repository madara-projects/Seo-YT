"""Persist real channel-video snapshots and derive conservative learning signals."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any


def save_video_snapshots(database_path: str, videos: list[dict[str, Any]]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    rows = [
        (v.get("video_id"), now, v.get("published_at"), v.get("title"), _num(v.get("views")), _optional_num(v.get("estimatedMinutesWatched")), _optional_num(v.get("averageViewDuration")), _optional_num(v.get("averageViewPercentage")), _num(v.get("likes")), _num(v.get("comments")), _optional_num(v.get("shares")), _optional_num(v.get("subscribersGained")))
        for v in videos if v.get("video_id")
    ]
    if not rows:
        return
    with sqlite3.connect(database_path) as connection:
        connection.executemany("INSERT INTO owned_video_snapshots (video_id,captured_at,published_at,title,views,watch_minutes,average_view_duration,average_view_percentage,likes,comments,shares,subscribers_gained) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)


def learning_summary(database_path: str) -> dict[str, Any]:
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute("""SELECT s.video_id,s.title,s.views,s.average_view_duration,s.average_view_percentage,s.likes,s.comments,s.published_at FROM owned_video_snapshots s INNER JOIN (SELECT video_id,MAX(captured_at) captured_at FROM owned_video_snapshots GROUP BY video_id) latest ON latest.video_id=s.video_id AND latest.captured_at=s.captured_at ORDER BY s.views DESC""").fetchall()
        linked_rows = connection.execute(
            """SELECT p.youtube_video_id, p.published_at, p.selected_title, a.title,
                      p.youtube_metadata_json, s.age_hours, s.views, s.avg_view_percentage,
                      s.likes, s.comments, s.snapshot_window, s.captured_at,
                      p.selected_tags_json
               FROM published_video_links p
               LEFT JOIN analysis_runs a ON a.id = p.analysis_run_id
               LEFT JOIN video_performance_snapshots s ON s.id = (
                   SELECT x.id FROM video_performance_snapshots x
                   WHERE x.youtube_video_id = p.youtube_video_id
                   ORDER BY x.captured_at DESC LIMIT 1
               )"""
        ).fetchall()
    videos = [{"video_id": r[0], "title": r[1], "views": r[2], "average_view_duration": r[3], "average_view_percentage": r[4], "likes": r[5], "comments": r[6], "published_at": r[7]} for r in rows]
    linked: list[dict[str, Any]] = []
    for row in linked_rows:
        try:
            metadata = json.loads(row[4]) if row[4] else {}
        except (TypeError, ValueError):
            metadata = {}
        age_hours = float(row[5] or 0)
        views = int(row[6] or metadata.get("view_count") or 0)
        linked.append({
            "video_id": row[0],
            "published_at": row[1],
            "title": str(metadata.get("title") or row[2] or row[3] or ""),
            "generated_title": str(row[3] or ""),
            "title_used": _normalized(str(metadata.get("title") or row[2] or "")) == _normalized(str(row[3] or "")),
            "views": views,
            "views_per_day": round(views / max(age_hours / 24, 1), 2),
            "average_view_percentage": _optional_num(row[7]),
            "likes": int(row[8] or metadata.get("like_count") or 0),
            "comments": int(row[9] or metadata.get("comment_count") or 0),
            "age_hours": round(age_hours, 1),
            "snapshot_window": row[10],
            "captured_at": row[11],
            "actual_tags": [str(tag) for tag in (metadata.get("tags") or [])],
            "generated_tags": _json_list(row[12]),
        })
    eligible = [item for item in linked if item["age_hours"] >= 24 and item.get("captured_at")]
    eligible.sort(key=lambda item: (item["views_per_day"], item.get("average_view_percentage") or 0), reverse=True)
    sample = len(eligible)
    if sample < 3:
        recommendation = (
            f"Collect 24-hour snapshots until at least 3 linked videos are mature "
            f"(currently {sample}); do not change generation strategy from the early sample."
        )
        confidence = "collecting"
    else:
        best = eligible[0]
        recommendation = (
            f"Use '{best.get('title') or 'the strongest linked video'}' as a directional pattern; "
            "it currently leads comparable linked uploads by age-normalized views. Keep testing before claiming causation."
        )
        confidence = "evidence-based" if sample >= 5 else "directional"
    return {
        "sample_size": sample,
        "connected_video_count": len(videos),
        "linked_video_count": len(linked),
        "confidence": confidence,
        "best_videos": eligible[:3],
        "weakest_videos": list(reversed(eligible[-3:])),
        "linked_evidence": linked,
        "recommendation": recommendation,
    }


def _num(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _optional_num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalized(value: str) -> str:
    import re
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return [str(item) for item in parsed] if isinstance(parsed, list) else []
    except (TypeError, ValueError):
        return []
