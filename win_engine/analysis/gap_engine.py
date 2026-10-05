from __future__ import annotations

import math
from collections import Counter
from typing import Any

from win_engine.ai_enhancement import find_content_similarity
from win_engine.analysis.dynamic_thresholds import get_dynamic_kill_switch
# The extractor's own word filter, so a phrase is found in a title the way the
# extractor counted it there.
from win_engine.analysis.keyword_extractor import _tokenize as extractor_words
from win_engine.analysis.numbers import optional_number
from win_engine.analysis.source_cues import is_short_duration
from win_engine.analysis.text_tokens import unicode_words
from win_engine.core.iso_duration import duration_seconds


def analyze_opportunity_gaps(
    keyword_signals: list[dict[str, Any]],
    entity_signals: list[dict[str, Any]],
    youtube_results: list[dict[str, Any]],
    top_opportunities: list[dict[str, Any]],
    language_context: dict[str, Any] | None = None,
    target_title: str = "",
) -> dict[str, Any]:
    """Build gap analysis and opportunity heuristics."""

    language_context = language_context or {}
    keyword_gaps = _keyword_gaps(keyword_signals, youtube_results)
    competition = _competition_meter(youtube_results, language_context)
    idea_kill_switch = get_dynamic_kill_switch(
        top_opportunities=top_opportunities,
        competition=competition,
        keyword_gaps=keyword_gaps,
    )

    # Uniqueness = how different the chosen title is from the top competitor
    # titles (1.0 = fully distinct, 0.0 = near-duplicate), by word overlap
    # (Jaccard), not a model. With nothing to compare it is unknown; a fixed
    # 0.5 used to stand in for it.
    uniqueness_score = None
    competitor_titles = [
        str(item.get("title", "")).strip()
        for item in (youtube_results or [])[:5]
        if isinstance(item, dict) and item.get("title")
    ]
    if target_title and competitor_titles:
        uniqueness_score = round(1.0 - max(find_content_similarity(target_title, c) for c in competitor_titles), 3)

    differentiation = _differentiation_plan(keyword_gaps, competition, youtube_results)
    opportunity_score = _opportunity_score(
        keyword_gaps, competition, top_opportunities,
        research_result_count=len(youtube_results or []), keyword_signal_count=len(keyword_signals or []),
    )
    format_lock = _format_lock_in(top_opportunities, youtube_results, competition)
    viability_verdict = _viability_verdict(opportunity_score, competition, idea_kill_switch, keyword_gaps)
    if not youtube_results:
        # Without competitor results the score was 25 from "empty competition"
        # alone, labelled WEAK, beside a kill switch saying "strong enough to
        # keep pursuing". Neither was measured; say so instead.
        unmeasured = "No competitor results were available, so demand and competition could not be measured."
        opportunity_score = {**opportunity_score, "score": None, "label": "UNMEASURED", "confidence": "NONE",
                             "measured": False, "reason": unmeasured,
                             "breakdown": {**opportunity_score["breakdown"], "score": None, "confidence": "none",
                                           "confidence_reason": "No score was calculated.", "warnings": [unmeasured]}}
        idea_kill_switch = {**idea_kill_switch, "proceed": True, "status": "insufficient_evidence",
                            "reason": unmeasured + " This is not a verdict on the idea.", "confidence": "none",
                            "recommended_action": "Re-run research when YouTube results are available before making a go/no-go call."}
        viability_verdict = {"status": "unknown", "proceed": True,
                             "summary": "Viability could not be judged without public YouTube results."}

    return {
        "keyword_gaps": keyword_gaps,
        "competition": competition,
        "idea_kill_switch": idea_kill_switch,
        "entity_focus": _entity_focus(entity_signals),
        "differentiation": differentiation,
        "opportunity_score": opportunity_score,
        "ai_uniqueness_score": uniqueness_score,
        "competitor_shadow": _competitor_shadow(youtube_results),
        "format_lock": format_lock,
        "viability_verdict": viability_verdict,
    }


def _keyword_gaps(
    keyword_signals: list[dict[str, Any]],
    youtube_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Phrases of the creator's script that the sampled competitors leave unused.

    A signal's mentions count the script and the competitor metadata together,
    so a quote six competitor titles shared used to read as a six-mention "gap".
    Only a phrase the script itself uses can be one: a gap is high when no
    sampled result uses the phrase and medium when one result in a sample of
    five or more does. Without a sample there is nothing to leave a phrase unused.
    """

    sample = len(youtube_results)
    if not sample:
        return []

    gaps: list[dict[str, Any]] = []
    for signal in keyword_signals:
        keyword = str(signal.get("keyword", "")).strip()
        mentions = int(signal.get("mentions", 0))
        if not keyword or keyword in {"youtube", "video", "will", "what"} or mentions < 2:
            continue
        per_result = [
            _phrase_count(keyword, item.get("title")) + _phrase_count(keyword, item.get("description"))
            for item in youtube_results
        ]
        if mentions - sum(per_result) < 1:
            continue  # every mention came from the competitors, not from the script
        using = sum(1 for count in per_result if count)
        if using == 0:
            strength = "high"
            reason = f"Present in your script; none of the {sample} sampled competitor titles or descriptions use it."
        elif using == 1 and sample >= 5:
            strength = "medium"
            reason = f"Present in your script; 1 of the {sample} sampled competitor titles or descriptions uses it."
        else:
            continue
        gaps.append({"keyword": keyword, "gap_strength": strength, "reason": reason})

    return gaps[:6]


def _phrase_count(phrase: str, text: object) -> int:
    """How often a keyword signal's phrase occurs in one competitor title or description.

    The extractor joins words after dropping stop words, so "people come life"
    stands for "people come into your life" and is in no title as written; it
    is counted in both spellings, as the extractor counted it. Whole words are
    compared: a regex word boundary falls inside Indic words, before a vowel
    sign, and found "प्यार" in "प्यारा".
    """

    target = unicode_words(phrase, min_length=1)

    def occurrences(words: list[str]) -> int:
        size = len(target)
        return sum(1 for start in range(len(words) - size + 1) if words[start:start + size] == target) if size else 0

    written = str(text or "")
    return max(occurrences(unicode_words(written, min_length=1)), occurrences(extractor_words(written)))


def _title_opening(title: object) -> str:
    """The first three words of a title: the framing a copycat title repeats. "" when shorter."""

    words = unicode_words(title)[:3]
    return " ".join(words) if len(words) == 3 else ""


def _repeated_openings(youtube_results: list[dict[str, Any]]) -> dict[str, int]:
    """Each opening shared by sampled titles, with how many titles repeat it after the first."""

    openings = Counter(_title_opening(item.get("title")) for item in youtube_results)
    openings.pop("", None)
    return {opening: count - 1 for opening, count in openings.items() if count >= 2}


def _competition_meter(youtube_results: list[dict[str, Any]], language_context: dict[str, Any]) -> dict[str, Any]:
    if not youtube_results:
        return {
            "score": 0,
            "label": "UNKNOWN",
            "reason": "No competitor data available.",
        }

    sample = len(youtube_results)
    # Titles that repeat another sampled title's opening. A count of '30 days'
    # titles, left over from another niche, stood here before.
    repeated_title_patterns = sum(_repeated_openings(youtube_results).values())
    # A hidden or unfetched subscriber count is unknown, not a small channel.
    subscriber_counts = [optional_number(item.get("subscriber_count")) for item in youtube_results]
    big_channel_count = sum(1 for count in subscriber_counts if count is not None and count >= 250000)
    unknown_channel_sizes = sum(1 for count in subscriber_counts if count is None)
    outlier_scores = [
        score for item in youtube_results[:5] if (score := optional_number(item.get("outlier_score"))) is not None
    ]

    # Shares of the sample, so a page of 25 results reads like a page of 5 did:
    # every repeated opening or large channel in five results adds what it added.
    score = round(60 * repeated_title_patterns / sample) + round(75 * big_channel_count / sample)
    if outlier_scores:
        average_outlier = sum(outlier_scores) / len(outlier_scores)
        if average_outlier > 100000:
            score += 25
        elif average_outlier > 10000:
            score += 15
        else:
            score += 5

    audience_type = str(language_context.get("audience_type", "")).strip().lower()
    region = str(language_context.get("region", "")).strip().lower()
    if audience_type in {"local", "diaspora"}:
        score -= 10
    if region in {"tamil nadu", "sri lanka", "gulf"}:
        score -= 5
    score = max(score, 0)

    if score >= 70:
        label = "SATURATED"
        reason = "Large channels and repeated title openings suggest heavy competition."
    elif score >= 40:
        label = "COMPETITIVE"
        reason = "The topic has traction, but several established videos are already fighting for the click."
    else:
        label = "UNDERSERVED"
        reason = "There is still room to differentiate packaging and angle."
    if unknown_channel_sizes:
        reason += f" Channel size was unavailable for {unknown_channel_sizes} result(s), so large channels may be undercounted."

    return {
        "score": round(score, 2),
        "label": label,
        "reason": reason,
        "confidence": "low",
        "evidence_state": "heuristic",
        "basis": (
            f"Shares of the {sample} sampled results whose title repeats another's opening (the same opening "
            "three words) or whose channel has 250K+ subscribers, plus the average outlier score of the first "
            "five; not a measurement of market size or demand."
        ),
        "repeated_title_patterns": repeated_title_patterns,
        "big_channel_count": big_channel_count,
        "unknown_channel_size_count": unknown_channel_sizes,
    }


def _entity_focus(entity_signals: list[dict[str, Any]]) -> list[str]:
    return [str(item.get("entity", "")).strip() for item in entity_signals[:4] if item.get("entity")]


def _differentiation_plan(
    keyword_gaps: list[dict[str, Any]],
    competition: dict[str, Any],
    youtube_results: list[dict[str, Any]],
) -> dict[str, Any]:
    repeated_openings = _repeated_openings(youtube_results)
    repeated_shocking = sum(1 for item in youtube_results if "shocking" in str(item.get("title", "")).lower())

    # The two most repeated openings; a title that starts the same way blends in.
    avoid_patterns: list[str] = [
        f"{repeats + 1} competitor titles open with \"{opening}\"; a title that starts the same way blends in."
        for opening, repeats in sorted(repeated_openings.items(), key=lambda item: -item[1])[:2]
    ]
    if repeated_shocking >= 2:
        avoid_patterns.append("Curiosity words like 'shocking' are already heavily used in this pocket.")

    emphasis = [item["keyword"] for item in keyword_gaps[:3]]
    if not emphasis:
        emphasis = ["clearer outcome framing", "stronger specificity", "better retention promise"]

    recommendation = (
        "Lean into underused subtopics and a clearer promise."
        if competition.get("label") != "SATURATED"
        else "Differentiate by narrowing the angle and removing generic curiosity phrasing."
    )

    return {
        "recommendation": recommendation,
        "emphasize": emphasis,
        "avoid_patterns": avoid_patterns,
    }


def _opportunity_score(
    keyword_gaps: list[dict[str, Any]],
    competition: dict[str, Any],
    top_opportunities: list[dict[str, Any]],
    *,
    research_result_count: int | None = None,
    keyword_signal_count: int | None = None,
) -> dict[str, Any]:
    opportunities = [item for item in top_opportunities[:3] if isinstance(item, dict)]
    # An unmeasured velocity is left out rather than averaged in as zero.
    velocity_scores = [
        min(100.0, 25.0 * math.log10(1.0 + max(views_per_day, 0.0)))
        for item in opportunities
        if (views_per_day := optional_number(item.get("views_per_day"))) is not None
    ]
    demand_score = sum(velocity_scores) / len(velocity_scores) if velocity_scores else 0.0
    gap_score = min((len(keyword_gaps) / 6.0) * 100.0, 100.0)
    competition_score = min(max(float(competition.get("score") or 0), 0.0), 100.0)
    competition_room = 100.0 - competition_score
    breakout_score = (
        sum(1 for item in opportunities if item.get("small_channel_outlier")) / len(opportunities) * 100.0
        if opportunities else 0.0
    )
    relevance_score = (
        sum(min(len(item.get("matched_queries") or []) / 3.0, 1.0) for item in opportunities)
        / len(opportunities) * 100.0
        if opportunities else 0.0
    )

    values = {
        "demand_velocity": demand_score,
        "competition_room": competition_room,
        "keyword_gap": gap_score,
        "small_channel_breakout": breakout_score,
        "research_relevance": relevance_score,
    }
    # Summed in the order the formula always used, so the score is unchanged.
    score = round(sum(values[key] * weight for key, _, weight in OPPORTUNITY_INPUTS), 2)
    score = min(max(score, 0.0), 100.0)

    if score >= 70:
        label = "STRONG"
    elif score >= 45:
        label = "WORKABLE"
    else:
        label = "WEAK"

    breakdown = _opportunity_breakdown(
        values, score, keyword_gaps, competition, opportunities, len(velocity_scores),
        research_result_count=research_result_count, keyword_signal_count=keyword_signal_count,
    )

    return {
        "score": score,
        "label": label,
        "confidence": breakdown["confidence"].upper(),
        "reason": "Weighted from current view velocity, competition room, keyword gaps, small-channel breakouts, and research relevance.",
        # Every input describes the competitor sample, none the title: one score
        # per run, the same for every package option of that run.
        "scope": OPPORTUNITY_SCORE_SCOPE,
        "varies_by_title": False,
        "components": {key: round(value, 2) for key, value in values.items()},
        "breakdown": breakdown,
    }


# The heuristic's five inputs, in the order the score sums them, and their weights.
OPPORTUNITY_INPUTS = (
    ("demand_velocity", "Demand (view velocity)", 0.35),
    ("competition_room", "Competition room", 0.25),
    ("keyword_gap", "Keyword gaps", 0.20),
    ("small_channel_breakout", "Small-channel breakouts", 0.10),
    ("research_relevance", "Research relevance", 0.10),
)
OPPORTUNITY_SCORE_SCOPE = "per_run"
OPPORTUNITY_SCORE_STATEMENT = (
    "A local heuristic that weighs five signals from this idea's YouTube research, computed once per run: "
    "the title is not an input, so every package option in a run shares it. "
    "It is not a prediction of views, reach or click-through rate."
)
# Sources of an input: counts YouTube reported, a local rule applied to the
# research, or a stand-in value because the data was missing.
MEASURED, HEURISTIC, DEFAULT = "youtube_measured", "local_heuristic", "missing_default"


def _opportunity_breakdown(
    values: dict[str, float],
    score: float,
    keyword_gaps: list[dict[str, Any]],
    competition: dict[str, Any],
    opportunities: list[dict[str, Any]],
    velocity_count: int,
    *,
    research_result_count: int | None,
    keyword_signal_count: int | None,
) -> dict[str, Any]:
    """Each input's value, weight, contribution and source, what was missing, and how complete it was."""
    top = len(opportunities)
    warnings: list[str] = []
    if not top:
        warnings.append("No research video qualified as a top opportunity, so demand, breakouts and relevance counted as 0.")
    elif top < 3:
        warnings.append(f"Only {top} top research video(s) were available; the score uses up to 3.")
    if top and not velocity_count:
        warnings.append("None of the top videos had a view velocity (no view count or publish date), so demand counted as 0.")
    elif velocity_count < top:
        warnings.append(
            f"View velocity was unavailable for {top - velocity_count} of the top {top} video(s) "
            "(no view count or publish date); they were left out of demand."
        )
    # A hidden subscriber or view count cannot show a breakout, so it counted as none.
    unknown_breakouts = sum(
        1 for item in opportunities
        if not item.get("small_channel_outlier")
        and (optional_number(item.get("subscriber_count")) is None or optional_number(item.get("view_count")) is None)
    )
    if unknown_breakouts:
        warnings.append(
            f"Subscriber or view count was unavailable for {unknown_breakouts} of the top {top} video(s), "
            "so they counted as non-breakouts."
        )
    competition_measured = (
        optional_number(competition.get("score")) is not None and str(competition.get("label") or "").upper() != "UNKNOWN"
    )
    if not competition_measured:
        warnings.append("Competition was not measured, so competition room counted as the maximum (100).")
    elif unknown_sizes := int(optional_number(competition.get("unknown_channel_size_count")) or 0):
        warnings.append(
            f"Channel size was unavailable for {unknown_sizes} sampled result(s), so large channels may be "
            "undercounted and competition room overstated."
        )
    if keyword_signal_count == 0:
        warnings.append("No keywords were extracted from your script, so keyword gaps counted as 0.")
    if research_result_count is not None and research_result_count < 5:
        warnings.append(f"Only {research_result_count} YouTube research result(s) were sampled.")

    sources = {
        "demand_velocity": MEASURED if velocity_count else DEFAULT,
        "competition_room": HEURISTIC if competition_measured else DEFAULT,
        "keyword_gap": DEFAULT if keyword_signal_count == 0 else HEURISTIC,
        "small_channel_breakout": MEASURED if top and unknown_breakouts < top else DEFAULT,
        "research_relevance": HEURISTIC if top else DEFAULT,
    }
    sampled = f"{research_result_count} sampled results" if research_result_count is not None else "the sampled results"
    bases = {
        "demand_velocity": (
            f"Average of 25 × log10(1 + views per day), capped at 100, for {velocity_count} of the top {top} research video(s)."
            if velocity_count else "No top research video had a view velocity, so this counted as 0."
        ),
        "competition_room": (
            f"100 minus the competition heuristic ({round(100.0 - values['competition_room'], 2):g}/100 from repeated "
            f"title openings, 250K+ subscriber channels and outlier scores in {sampled})."
            if competition_measured else "Competition was not measured, so this counted as 100."
        ),
        "keyword_gap": (
            f"{len(keyword_gaps)} phrase(s) of your script that none, or one, of the sampled competitor titles and "
            "descriptions use, out of 6 counted."
            if sources["keyword_gap"] == HEURISTIC else "No keywords were extracted from your script, so this counted as 0."
        ),
        "small_channel_breakout": (
            f"{sum(1 for item in opportunities if item.get('small_channel_outlier'))} of the top {top} research video(s) came "
            "from channels with 10K or fewer subscribers and reached 100K+ views."
            if sources["small_channel_breakout"] == MEASURED
            else "No top research video had a subscriber and view count, so this counted as 0."
        ),
        "research_relevance": (
            f"How many of this idea's research queries (up to 3) found each of the top {top} video(s)."
            if top else "No top research videos were available, so this counted as 0."
        ),
    }
    inputs = [
        {
            "key": key, "name": name, "value": round(values[key], 2), "weight": weight,
            "contribution": round(values[key] * weight, 4), "source": sources[key], "basis": bases[key],
        }
        for key, name, weight in OPPORTUNITY_INPUTS
    ]

    with_data = sum(1 for item in inputs if item["source"] != DEFAULT)
    # Fewer than five sampled results read as medium confidence from two; a
    # sample that small is low whatever the inputs.
    small_sample = research_result_count is not None and research_result_count < 5
    if with_data == len(inputs) and top >= 3 and not warnings and (research_result_count or 0) >= 10:
        confidence = "high"
    elif with_data >= 4 and top >= 2 and not small_sample:
        confidence = "medium"
    else:
        confidence = "low"
    backing = f"{top} top research video(s)" + (
        f" from {research_result_count} sampled result(s)" if research_result_count is not None else ""
    )
    return {
        "version": "opportunity-heuristic-v2",
        "kind": "local_heuristic",
        "scope": OPPORTUNITY_SCORE_SCOPE,
        "statement": OPPORTUNITY_SCORE_STATEMENT,
        "score": score,
        "inputs": inputs,
        "warnings": warnings,
        "confidence": confidence,
        "confidence_reason": (
            f"{with_data} of {len(inputs)} inputs had data, backed by {backing}. Confidence describes how complete "
            "the inputs were, not how likely the video is to get views."
        ),
        "inputs_with_data": with_data,
        "top_videos_used": top,
        "research_results": research_result_count,
    }


def _competitor_shadow(youtube_results: list[dict[str, Any]]) -> dict[str, Any]:
    if not youtube_results:
        return {
            "similar_video_count": 0,
            "dominant_title_pattern": "unknown",
            "dominant_hook_pattern": "unknown",
            "recommended_differentiation": "Not enough competitor data yet.",
        }

    titles = [str(item.get("title", "")) for item in youtube_results]
    # "for 7/30 days" titles, left over from another niche, no longer make an experiment.
    title_pattern_counts = {
        "experiment": sum(1 for title in titles if any(token in title.lower() for token in ["i tried", "i tested"])),
        "search": sum(1 for title in titles if any(token in title.lower() for token in ["how to", "guide", "tutorial"])),
        "curiosity": sum(1 for title in titles if any(token in title.lower() for token in ["shocking", "secret", "truth", "mistake"])),
    }
    dominant_title_pattern = _dominant(title_pattern_counts)

    hook_pattern_counts = {
        "first_person": sum(1 for title in titles if title.lower().startswith("i ")),
        "how_to": sum(1 for title in titles if title.lower().startswith("how to")),
        "question": sum(1 for title in titles if "?" in title),
    }
    dominant_hook_pattern = _dominant(hook_pattern_counts)

    if dominant_title_pattern == "experiment":
        differentiation = "Keep the experiment angle, but narrow the promise or conflict so it does not blend into the same repeated challenge pattern."
    elif dominant_title_pattern == "search":
        differentiation = "Avoid generic tutorial phrasing and lead with a more specific or surprising outcome."
    elif dominant_title_pattern == "curiosity":
        differentiation = "Reduce generic curiosity phrasing and make the payoff more concrete."
    else:
        differentiation = "No one title pattern dominates; lead with the most specific payoff your video delivers."

    return {
        "similar_video_count": len(youtube_results),
        "dominant_title_pattern": dominant_title_pattern,
        "dominant_hook_pattern": dominant_hook_pattern,
        "recommended_differentiation": differentiation,
    }


def _dominant(counts: dict[str, int]) -> str:
    """The most frequent pattern, or "other" when no title has any: max() of zeros named the first."""

    best = max(counts, key=counts.get)
    return best if counts[best] else "other"


def _format_lock_in(
    top_opportunities: list[dict[str, Any]],
    youtube_results: list[dict[str, Any]],
    competition: dict[str, Any],
) -> dict[str, Any]:
    candidates = top_opportunities[:3] if top_opportunities else youtube_results[:3]
    if not candidates:
        return {
            "recommended_format": "unknown",
            "recommended_length": "unknown",
            "title_style": "unknown",
            "reason": "Not enough competitor data to lock a format.",
        }

    short_form_count = 0
    long_form_count = 0
    unknown_duration_count = 0
    first_person_count = 0
    proof_count = 0

    for item in candidates:
        is_short = is_short_duration(duration_seconds(item.get("duration")))
        title = str(item.get("title") or "").lower()
        # Live, upcoming and unfetched videos have no length to vote with;
        # they used to count as long-form and lock "6-12 minutes". A Short is
        # up to three minutes, as everywhere else; a 60-second cut called a
        # 90-second Short long-form.
        if is_short is None:
            unknown_duration_count += 1
        elif is_short:
            short_form_count += 1
        else:
            long_form_count += 1
        if title.startswith("i "):
            first_person_count += 1
        if any(token in title for token in ["result", "truth", "worth it", "what happened", "mistake"]):
            proof_count += 1

    if short_form_count or long_form_count:
        recommended_format = "short-form" if short_form_count > long_form_count else "long-form"
        recommended_length = "3 minutes or less" if recommended_format == "short-form" else "6-12 minutes"
    else:
        recommended_format = recommended_length = "unknown"
    title_style = "first-person proof" if first_person_count >= 2 else "outcome-led"
    if proof_count >= 2:
        title_style = f"{title_style} with clear payoff"

    if recommended_format == "unknown":
        reason = "None of the compared videos had a known duration, so no format or length is locked."
    elif str(competition.get("label", "UNKNOWN")).upper() == "SATURATED":
        reason = "Competition is heavy, so the format should match proven behavior while the angle stays narrower."
    else:
        reason = "Competitor patterns are strong enough to guide packaging without forcing a copycat title."
    if unknown_duration_count and recommended_format != "unknown":
        reason += f" {unknown_duration_count} compared video(s) had no known duration and were left out of the format vote."

    return {
        "recommended_format": recommended_format,
        "recommended_length": recommended_length,
        "title_style": title_style,
        "reason": reason,
    }


def _viability_verdict(
    opportunity_score: dict[str, Any],
    competition: dict[str, Any],
    idea_kill_switch: dict[str, Any],
    keyword_gaps: list[dict[str, Any]],
) -> dict[str, Any]:
    score_label = str(opportunity_score.get("label", "WEAK")).upper()
    competition_label = str(competition.get("label", "UNKNOWN")).upper()
    gap_count = len(keyword_gaps)
    proceed = bool(idea_kill_switch.get("proceed"))

    if proceed and score_label == "STRONG":
        status = "green"
        summary = "The idea is viable now. Focus on packaging and execution."
    elif proceed and (score_label == "WORKABLE" or gap_count >= 2):
        status = "yellow"
        summary = "The idea is workable, but only if you commit to a clearer differentiation angle."
    else:
        status = "red"
        summary = "The idea is not strong enough yet. Reframe it before publishing."

    if competition_label == "SATURATED" and proceed:
        summary = "The idea can still work, but only with a tighter promise and stronger packaging."

    return {
        "status": status,
        "summary": summary,
        "proceed": proceed,
    }
