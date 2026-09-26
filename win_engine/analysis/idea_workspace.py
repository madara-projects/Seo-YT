"""Truthful Stage G1 idea research and generation helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from statistics import median
from typing import Any

from win_engine.analysis.numbers import optional_number


# keyword_research carries the tag candidates and the search-suggestion
# evidence; without it "Generate from idea" chose tags from model output alone.
RESEARCH_FIELDS = (
    "youtube_results", "top_opportunities", "keyword_signals", "entity_signals",
    "upload_timing", "thumbnail_intelligence", "research_queries",
    "research_decision", "research_warnings", "cache_policy",
    "keyword_research", "search_demand",
)
# A result is a possible outlier when it is a small-channel breakout, or when
# its outlier score is at least 2.5x the median of five or more measured
# results: the watchlist's rule, applied to the sample instead of a channel.
_OUTLIER_MULTIPLIER = 2.5
_MIN_OUTLIER_BASELINE = 5


def idea_script(idea: dict[str, Any], override: str = "") -> str:
    """Build generation input only from creator-authored idea fields."""

    if override.strip():
        return override.strip()
    parts = [str(idea.get("topic") or "").strip()]
    labelled = (
        ("Notes", idea.get("notes")),
        ("On-screen text", idea.get("on_screen_text")),
        ("Visual/background", idea.get("visual_or_background")),
        ("Emotion or intent", idea.get("emotion_or_intent")),
        ("Search angle", idea.get("search_angle")),
        ("Browse angle", idea.get("browse_angle")),
        ("Existing audience angle", idea.get("audience_angle")),
    )
    parts.extend(f"{label}: {str(value).strip()}" for label, value in labelled if str(value or "").strip())
    return "\n".join(parts)


def build_idea_evidence(
    research: dict[str, Any],
    personal_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a dated JSON-safe research snapshot without credentials or runtime objects."""

    captured_at = datetime.now(timezone.utc).isoformat()
    payload = {field: _json_safe(research.get(field)) for field in RESEARCH_FIELDS}
    results = payload.get("youtube_results") if isinstance(payload.get("youtube_results"), list) else []
    queries = payload.get("research_queries") if isinstance(payload.get("research_queries"), list) else []
    publication_dates = sorted(
        [str(item.get("published_at")) for item in results if isinstance(item, dict) and item.get("published_at")],
        reverse=True,
    )
    possible_outliers, unmeasured = _possible_outliers(results)
    if results:
        freshness = f" Most recent observed publication: {publication_dates[0]}." if publication_dates else " Publication dates were unavailable."
        unmeasured_note = f" Outlier stats were unavailable for {unmeasured} result(s)." if unmeasured else ""
        explanation = (
            f"Observed {len(results)} relevant public YouTube API result(s) across {len(queries)} approved research "
            f"query angle(s); {possible_outliers} carried a possible-outlier signal (a small-channel breakout, or at "
            f"least 2.5x the median outlier score of five or more measured results).{unmeasured_note}{freshness} "
            "These are dated public observations, not monthly search volume or predicted demand."
        )
    else:
        explanation = (
            "Approved research returned no public YouTube results at this capture time. "
            "Search volume, demand, trend percentage, and performance confidence are unavailable."
        )
    personal = personal_evidence if isinstance(personal_evidence, dict) else {}
    learning_allowed = bool(personal.get("learning_allowed"))
    personal_summary = {
        "status": "observed_history" if learning_allowed else "insufficient_evidence",
        "learning_allowed": learning_allowed,
        "sample_size": int(personal.get("sample_size") or 0),
        "confidence_label": personal.get("confidence_label") or "Collecting evidence",
        "snapshot_window": personal.get("snapshot_window") or "24h",
        "message": personal.get("recommendation") or "Not enough personal evidence.",
    }
    return {
        "captured_at": captured_at,
        "source": "approved_youtube_data_api_research",
        "opportunity_explanation": explanation,
        "signals": {
            "relevant_result_count": len(results),
            "research_query_count": len(queries),
            "possible_outlier_count": possible_outliers,
            "publication_dates": publication_dates,
        },
        "personal_evidence": personal_summary,
        **payload,
    }


def evidence_to_research(evidence: dict[str, Any]) -> dict[str, Any]:
    """Rehydrate only the existing generator's approved research fields."""

    list_fields = {"youtube_results", "top_opportunities", "keyword_signals", "entity_signals", "research_queries", "research_warnings"}
    dict_fields = {"upload_timing", "thumbnail_intelligence", "research_decision", "keyword_research", "search_demand"}
    result: dict[str, Any] = {}
    for field in RESEARCH_FIELDS:
        value = evidence.get(field)
        if field in list_fields:
            result[field] = value if isinstance(value, list) else []
        elif field in dict_fields:
            result[field] = value if isinstance(value, dict) else {}
        else:
            result[field] = value or "idea-research-snapshot"
    return result


def _possible_outliers(results: list[Any]) -> tuple[int, int]:
    """Count possible outliers among results with measured stats, and the unmeasured rest.

    A raw outlier score of 3 used to be the bar, and an ordinary 20k-view video
    on a 150k-subscriber channel scores about 18, so nearly every result counted.
    """

    measured: list[tuple[dict[str, Any], float]] = []
    unmeasured = 0
    for item in results:
        if not isinstance(item, dict):
            continue
        score = optional_number(item.get("outlier_score"))
        if score is None:
            unmeasured += 1
        else:
            measured.append((item, score))
    scores = [score for _, score in measured]
    baseline = median(scores) if len(scores) >= _MIN_OUTLIER_BASELINE else 0.0
    count = sum(
        1 for item, score in measured
        if item.get("small_channel_outlier") or (baseline > 0 and score >= baseline * _OUTLIER_MULTIPLIER)
    )
    return count, unmeasured


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value))
    except (TypeError, ValueError):
        if isinstance(value, dict):
            return {str(key): _json_safe(item) for key, item in value.items() if not key.lower().endswith("token")}
        if isinstance(value, (list, tuple)):
            return [_json_safe(item) for item in value]
        return None
