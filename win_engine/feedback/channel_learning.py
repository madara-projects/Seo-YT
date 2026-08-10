"""Persist real channel-video snapshots and derive conservative learning signals."""

from __future__ import annotations

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
    videos = [{"video_id": r[0], "title": r[1], "views": r[2], "average_view_duration": r[3], "average_view_percentage": r[4], "likes": r[5], "comments": r[6], "published_at": r[7]} for r in rows]
    sample = len(videos)
    if sample < 10:
        recommendation = f"Collect snapshots for {10 - sample} more published videos before treating patterns as evidence."
        confidence = "collecting"
    else:
        average_retention = sum(float(v["average_view_percentage"] or 0) for v in videos) / sample
        best = videos[0]
        recommendation = f"Use the strongest elements of '{best.get('title') or 'your top video'}'; it leads the current group by views. Compare future videos against this baseline, not channel-wide guesses."
        confidence = "evidence-based" if average_retention else "limited"
    return {"sample_size": sample, "confidence": confidence, "best_videos": videos[:3], "weakest_videos": list(reversed(videos[-3:])), "recommendation": recommendation}


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
