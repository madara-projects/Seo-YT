"""Persist real channel-video snapshots and derive conservative learning signals."""

from __future__ import annotations

from datetime import date, datetime, time as day_time, timedelta, timezone
from typing import Any

from win_engine.analysis.text_tokens import unicode_words
from win_engine.feedback.migrations import connect_managed
from win_engine.feedback.evidence_policy import (
    evidence_level, pattern_signal, sample_is_eligible, verified_for_another_channel,
)
from win_engine.feedback.history_store import (
    ANALYTICS_ZONE, NO_CONNECTED_CHANNEL_REASON, HistoryStore, comparable_format, format_filter_values, known_filter,
    snapshot_covered_hours, views_per_covered_day,
)


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
    # Only the connected channel's linked videos are this creator's evidence
    # (evidence_policy.verified_ownership); one verified for another channel is
    # not even counted as linked here, and with no channel connected no verified
    # link is. An unverified link still counts as linked.
    channel_id = store.connected_channel_id()
    links = [
        link for link in store.published_video_links_list()
        if not verified_for_another_channel(link, connected_channel_id=channel_id)
    ]
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
        if not snapshot or not sample_is_eligible(
            policy_link, snapshot, expected_window=snapshot_window, connected_channel_id=channel_id
        ):
            continue
        views = int(snapshot["views"])
        age_hours = float(snapshot.get("age_hours") or 0)
        covered_hours = snapshot_covered_hours(snapshot, link.get("published_at"))
        per_day = views_per_covered_day(views, covered_hours)
        title, tags, attribution = _metadata_at_window_end(link, snapshot, covered_hours)
        linked.append({
            "video_id": link.get("youtube_video_id"),
            "format": effective_format,
            "language": effective_language,
            "published_at": link.get("published_at"),
            # The uploaded title and tags live when the window ended, never a
            # later edit; None when that is not known (title_attribution says why).
            "title": title,
            "title_attribution": attribution,
            "generated_title": str(link.get("package_topic") or ""),
            "title_used": None if title is None else _normalized(title) == _normalized(str(link.get("package_topic") or "")),
            "views": views,
            "covered_hours": covered_hours,
            "views_per_covered_day": per_day,
            # Older name for views_per_covered_day, kept for existing readers.
            "views_per_day": per_day,
            "average_view_percentage": _optional_num(snapshot.get("avg_view_percentage")),
            # The window's own counts: lifetime metadata covers a different time
            # range, and a count the window did not report stays unknown.
            "likes": None if snapshot.get("likes") is None else int(snapshot["likes"]),
            "comments": None if snapshot.get("comments") is None else int(snapshot["comments"]),
            "age_hours": round(age_hours, 1),
            "snapshot_window": snapshot.get("snapshot_window"),
            "captured_at": snapshot.get("captured_at"),
            "actual_tags": tags,
            "generated_tags": [str(tag) for tag in (link.get("selected_tags") or [])],
            "comparable_metadata": comparable,
        })
    # A window's raw total depends on how many hours it covered (24 to 48 for
    # "24h"), so videos are ranked by views per covered day; one whose coverage
    # is unknown stays in the counts but is not ranked or compared.
    linked.sort(key=lambda item: (item["views_per_covered_day"] or 0, item.get("average_view_percentage") or 0), reverse=True)
    eligible = [item for item in linked if item["views_per_covered_day"] is not None]
    sample = len(linked)
    level = evidence_level(len(eligible))
    # The leading videos reach the writer's prompt only when their lead is more
    # than noise in a cohort of one format and language; at five videos with
    # views 12% apart the top three were sent as a "pattern". Long-form formats
    # are one cohort, as the format filter groups them.
    long_form = format_filter_values("long_form") or frozenset()
    comparable = len({
        ("long_form" if item["format"] in long_form else item["format"], item["language"]) for item in eligible
    }) <= 1
    signal = pattern_signal(
        [float(item["views_per_covered_day"]) for item in eligible], comparable=comparable, measure="views per covered day",
    )
    pattern_found = level.learning_allowed and signal["status"] == "pattern"
    if channel_id is None:
        recommendation = NO_CONNECTED_CHANNEL_REASON
        confidence = "collecting"
    elif not level.learning_allowed:
        recommendation = (
            f"Collect verified completed {snapshot_window} snapshots until at least {level.minimum_samples} comparable linked videos are mature "
            f"(currently {len(eligible)}); do not change generation strategy from the early sample."
            + (
                f" {sample - len(eligible)} more {'has' if sample - len(eligible) == 1 else 'have'} no known window coverage and "
                f"{'is' if sample - len(eligible) == 1 else 'are'} not compared."
                if sample > len(eligible) else ""
            )
        )
        confidence = "collecting"
    elif pattern_found:
        best = eligible[0]
        recommendation = (
            f"{level.label}: '{best.get('title') or 'the leading comparable video'}' currently leads this "
            f"{snapshot_window} cohort by views per covered day, and {signal['reason']} "
            "Treat this as historical evidence, not a guarantee."
        )
        confidence = level.key
    else:
        recommendation = f"No linked-video pattern was applied: {signal['reason']}"
        confidence = level.key
    return {
        "sample_size": sample,
        # The videos ranked and compared: those whose window coverage is known.
        "compared_sample_size": len(eligible),
        "connected_video_count": len(videos),
        "linked_video_count": len(comparable_links),
        "confidence": confidence,
        "evidence_level": level.key,
        "confidence_label": level.label,
        "learning_allowed": level.learning_allowed,
        "snapshot_window": snapshot_window,
        "pattern_signal": signal,
        # Ranking a sample without a pattern would present noise as one.
        "best_videos": eligible[:3] if pattern_found else [],
        "weakest_videos": list(reversed(eligible[-3:])) if pattern_found else [],
        "linked_evidence": linked,
        "recommendation": recommendation,
    }


def _metadata_at_window_end(
    link: dict[str, Any], snapshot: dict[str, Any], covered_hours: float | None,
) -> tuple[str | None, list[str] | None, str]:
    """The uploaded title and tags live when the window ended, and how that is known.

    "observed": the latest record seen at or before the window's end, the
    snapshot's own uploaded metadata or a stored observation. Each refresh
    stores the video's newest metadata, so the current title is often an edit
    made after the window, which must not be credited with its views. The
    snapshot's metadata is written once the window completes, usually after its
    end, so in practice the observations decide; whichever qualifying record is
    latest is the closest to the window's end. A record's observed_at is when a
    change was seen, not made, so an edit made shortly before the window ended
    but first seen after it is credited to the title recorded before it.
    "assumed_unchanged": nothing was recorded by then (links from before
    observations were kept), but the uploaded title is still the one the creator
    confirmed at link time and nothing recorded since differs from it. Only the
    title is assumed: tags have no confirmed value to check them against, so a
    tag edit made after the window cannot be detected and the current tags may
    be that edit. Their tags are None (unknown); only observed tags are credited.
    "unknown": neither holds; the title and tags are None and the video's
    numbers still count.
    """
    current = link.get("youtube_metadata") if isinstance(link.get("youtube_metadata"), dict) else {}
    recorded = snapshot.get("uploaded_metadata") if isinstance(snapshot.get("uploaded_metadata"), dict) else None
    observations = [item for item in (current.get("observations") or []) if isinstance(item, dict)]
    records = [item for item in (recorded, *observations) if item]
    window_end = _window_end(link.get("published_at"), snapshot.get("source_end_date"), covered_hours)
    if window_end is not None:
        seen = [(when, item) for item in records if (when := _parse_time(item.get("observed_at"))) and when <= window_end]
        if seen:
            latest = max(seen, key=lambda pair: pair[0])[1]
            title = _known_title(latest.get("title"))
            if title is None:
                # A record that did not report the title leaves it unknown, not
                # the current one, and its tags are then not credited either.
                return None, None, "unknown"
            return title, _known_tags(latest.get("tags")), "observed"
    title, tags = _known_title(current.get("title")), _known_tags(current.get("tags"))
    # Every record left is from after the window, or of unknown time: one that
    # differs from the current title or tags proves an edit since, so the
    # current values may not be what the window's viewers saw.
    edited = any(
        ((recorded_title := _known_title(item.get("title"))) is not None and not _same_title(recorded_title, title))
        or ((recorded_tags := _known_tags(item.get("tags"))) is not None and recorded_tags != tags)
        for item in records
    )
    confirmed = _known_title(link.get("selected_title"))
    if title is not None and confirmed is not None and _same_title(title, confirmed) and not edited:
        # No record shows which tags were live by the window's end, so the
        # current ones (possibly a later edit) are not credited with its views.
        return title, None, "assumed_unchanged"
    return None, None, "unknown"


def _window_end(published_at: Any, source_end_date: Any, covered_hours: float | None) -> datetime | None:
    """The Pacific midnight that ends the window's last reported day."""
    try:
        last_day = date.fromisoformat(str(source_end_date or "").strip()[:10])
    except ValueError:
        published = _parse_time(published_at)
        return published + timedelta(hours=covered_hours) if published and covered_hours else None
    return datetime.combine(last_day + timedelta(days=1), day_time(), tzinfo=ANALYTICS_ZONE)


def _parse_time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _known_title(value: Any) -> str | None:
    # A null title is unknown, never an empty one.
    return (str(value).strip() or None) if value is not None else None


def _same_title(first: str | None, second: str | None) -> bool:
    # Every word counts here, single letters and digits too: "Top 5" edited to
    # "Top 7" is a different title, though _normalized drops one-letter words.
    return unicode_words(first or "", min_length=1) == unicode_words(second or "", min_length=1)


def _known_tags(value: Any) -> list[str] | None:
    return [str(tag) for tag in value] if isinstance(value, list) else None


def _optional_num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalized(value: str) -> str:
    return " ".join(unicode_words(value))
