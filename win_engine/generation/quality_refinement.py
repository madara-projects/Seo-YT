"""Bounded editorial refinement with explicit, measured acceptance targets."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from win_engine.analysis.generation_quality import evaluate_package_quality, is_short_content, short_title_fit
from win_engine.analysis.source_cues import source_quote
from win_engine.analysis.text_tokens import normalize_unicode, unicode_words
from win_engine.llm import gemini_client
from win_engine.llm.seo_writer import generate_one

TARGET = 90.0
SCORE_FIELDS = ("title_score", "description_score", "tag_score")
# A tag this weak is dropped even from a small package.
_WEAK_TAG_SCORE = 60.0
# Minimum title score for search-phrase presence to decide between titles.
_KEYWORD_TITLE_FLOOR = 70.0


def title_demand_words(title: str, evidence: dict[str, Any] | None) -> int:
    """Length in words of the longest real search phrase the title carries verbatim.

    Titles that pass every check often tie on score; between "Step-by-step
    cold brew coffee with a paper filter" and "Making cold brew coffee at home
    without special gear", the one containing what viewers actually type
    ("making cold brew coffee at home") should lead.
    """

    demand = (evidence or {}).get("search_demand") or {}
    phrases = {*(demand.get("grounded_suggestions") or []), *(demand.get("validated_keywords") or [])}
    folded = f" {' '.join(unicode_words(title, min_length=1))} "
    best = 0
    for phrase in phrases:
        words = unicode_words(phrase, min_length=1)
        if len(words) >= 2 and f" {' '.join(words)} " in folded:
            best = max(best, len(words))
    return best


def target_fields(short_form: bool = False, quote_short: bool = False) -> tuple[str, ...]:
    """The scores the 90-point target counts.

    A Short's tag score is reported, not targeted: tags play a minimal role
    in its discovery (support.google.com/youtube/answer/146402). A quote
    Short's title is judged by the gate's pass/fail checks (the quote kept
    whole or to its punchline, no cut, no reversed meaning), not by a word
    overlap score, which only drove repairs toward the quote's own words.
    """

    skipped = {"tag_score"} if short_form else set()
    if quote_short:
        skipped.add("title_score")
    return tuple(field for field in SCORE_FIELDS if field not in skipped)


def enforce_quality_target(gate: dict[str, Any], *, short_form: bool = False, quote_short: bool | None = None) -> dict[str, Any]:
    """Annotate shortfalls without replacing scores or treating missing data as zero evidence."""
    result = deepcopy(gate)
    quality = result.setdefault("final_seo_quality", {})
    if quote_short is None:
        quote_short = bool(short_form and gate.get("exact_quote_checked"))
    fields = target_fields(short_form, quote_short)
    # An unmeasured score cannot show the target was met; it is named as not
    # measured rather than read as a low score.
    unmeasured = [field for field in fields if quality.get(field) is None]
    shortfalls = [field for field in fields
                  if quality.get(field) is None or float(quality[field]) < TARGET]
    result["quality_target"] = {"minimum": TARGET, "met": not shortfalls,
                                "shortfalls": shortfalls, "not_measured": unmeasured,
                                "basis": "local_heuristic_not_performance"}
    if short_form:
        result["quality_target"]["not_counted"] = {
            "tag_score": "Tags play a minimal role in a Short's discovery; the score is reported, not targeted.",
        }
    if quote_short:
        result["quality_target"]["not_counted"]["title_score"] = (
            "A quote Short's title passes or fails its checks (the quote kept whole or to its punchline, "
            "no cut, no reversed meaning); the score is reported, not targeted."
        )
    if shortfalls:
        named = [f"{field} (not measured)" if field in unmeasured else field for field in shortfalls]
        issue = {"code": "quality_target_not_met", "field": "package", "severity": "warning",
                 "message": "/".join(["90"] * len(fields)) + " target not met: " + ", ".join(named)
                 + ". Manual review required."}
        result.setdefault("warnings", []).append(issue)
        quality.setdefault("warnings", []).append(issue)
        if result.get("verdict") != "RED":
            result["verdict"] = quality["verdict"] = "YELLOW"
    return result


def _lead_with(title: str, variants: list[str]) -> list[str]:
    """The chosen title first, then every other alternative once."""

    ordered: list[str] = []
    seen: set[str] = set()
    for value in [title, *variants]:
        key = " ".join(str(value or "").casefold().split())
        if key and key not in seen:
            seen.add(key)
            ordered.append(value)
    return ordered


def _alternatives_request(kept: list[str], rejected: list[dict[str, Any]], *, quote_short: bool) -> str:
    """The repair instruction when fewer than three distinct titles passed the gate."""

    angles = (": the quote's punchline clause or the whole quote when it fits 70 characters, its core line in "
              "new words, speaking to the viewer, the feeling it names, a question the viewer asks themselves"
              if quote_short else "")
    faults = [*(["cut the quote mid-phrase, end in '...', stop before the quote's turn, or reverse its meaning"]
                if quote_short else []),
              "read almost like another title",
              "promise advice or a how-to the source does not give",
              "add a feeling, setting or claim the source does not state"]
    discarded = "; ".join(
        f"\"{item['title']}\" ({', '.join(item.get('codes') or []) or 'rejected'})"
        for item in rejected[:5] if isinstance(item, dict) and item.get("title")
    )
    return (
        f"Only {len(kept)} distinct title(s) passed the checks: " + "; ".join(f"\"{title}\"" for title in kept)
        + f". Keep them and return five distinct variants in total, each from a different angle{angles}. "
        "Every title keeps one of the source's own key words, in the form the source uses it. No title may "
        + ", ".join(faults[:-1]) + ", or " + faults[-1] + "."
        + (f" These titles were discarded; do not return them: {discarded}." if discarded else "")
    )


def refine_package(package: dict[str, Any], *, script: str, brief: dict[str, Any],
                   language: str, region: str, evidence: dict[str, Any],
                   competitors: list[dict[str, Any]],
                   channel_learning: dict[str, Any] | None = None,
                   local_fallback: bool = False,
                   rejected_titles: list[dict[str, Any]] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Rank existing alternatives, then attempt one repair; retain the stronger valid result.

    ``channel_learning`` carries the recent and published titles a refined
    title must not repeat. ``local_fallback`` marks a package the writer built
    locally; it is ranked but never sent to Gemini, since the writer's own
    request has just failed or been rejected. ``rejected_titles`` are the
    writer's titles its quality gate discarded, with their reason codes; when
    fewer than three titles passed, the repair asks for alternatives that
    avoid them.
    """
    learning = channel_learning or {}
    short_form = is_short_content(script, brief)
    # A quote Short's titles are ranked by how well they carry the quote;
    # search phrases only break ties (see short_title_fit).
    short_quote = source_quote(script, brief) if short_form else ""
    scene = " ".join(str(brief.get(field) or "") for field in ("content", "visual_requirements")).strip() or script

    def title_fit(title: Any) -> int:
        return short_title_fit(title, short_quote, scene)

    def evaluate(value: dict[str, Any]) -> dict[str, Any]:
        return evaluate_package_quality(value, script=script, creator_brief=brief,
            language=language, tag_evidence=evidence,
            recent_titles=learning.get("recent_titles") or [],
            published_titles=learning.get("published_titles") or [],
            competitor_titles=[str(row.get("title") or "") for row in competitors])

    def rank(gate: dict[str, Any], pkg: dict[str, Any]) -> tuple[Any, ...]:
        scores = gate.get("final_seo_quality", {})
        title = float(scores.get("title_score") or 0)
        description = float(scores.get("description_score") or 0)
        tag = float(scores.get("tag_score") or 0)
        # Between titles that score alike, one that carries the phrase viewers
        # search leads. It used to outrank every score, which made the title
        # that led with the main keyword win over a more specific, truthful
        # one ("Download and install OBS Studio..." over "My exact OBS settings...").
        carries_keyword = title >= _KEYWORD_TITLE_FLOOR and not any(
            isinstance(item, dict) and item.get("code") == "primary_keyword_missing_from_title"
            for item in scores.get("warnings") or []
        )
        ranked = (bool(gate.get("passed")), min(title, description, tag), title + description + tag,
                  carries_keyword, title_demand_words(str(pkg.get("title") or ""), evidence))
        if not short_quote:
            return ranked
        # The title the gate lets through first is the one the creator gets;
        # a package led by a title the gate rejects ("Alone quotes for ...")
        # ranks below the same titles led by one it accepts.
        accepted = [item.get("title") for item in gate.get("accepted_candidates") or [] if isinstance(item, dict)]
        leads = normalize_unicode(pkg.get("title")) in accepted
        return (ranked[0], leads, title_fit(accepted[0] if accepted else pkg.get("title")), *ranked[1:])

    def refine_tags_locally(pkg: dict[str, Any]) -> dict[str, Any]:
        pkg_tags = list(pkg.get("tags") or [])
        if not pkg_tags or not evidence:
            return pkg
        selected_keywords = {
            str(item.get("keyword") or "").casefold(): item
            for item in evidence.get("selected_keywords", [])
            if isinstance(item, dict) and item.get("keyword")
        }
        platform_tags = [t for t in pkg_tags if t.lower() in {"yt", "shorts"}]
        # Phrases viewers demonstrably search are kept whatever their heuristic
        # score: pruning "love quotes" (77) to lift the average toward 90
        # improved the number and made the package worse.
        protected = [
            t for t in pkg_tags
            if t.lower() not in {"yt", "shorts"} and selected_keywords.get(t.lower(), {}).get("demand_validated")
        ]
        topic_tags = [t for t in pkg_tags if t.lower() not in {"yt", "shorts"} and t not in protected]
        scored_topics = []
        for t in topic_tags:
            row = selected_keywords.get(t.lower(), {})
            score = float(row.get("keyword_relevance_score") or 0)
            scored_topics.append((t, score))
        avg = sum(s for _, s in scored_topics) / max(len(scored_topics), 1)
        if avg >= TARGET:
            return pkg
        # Sort ascending to prune the lowest scoring tags pulling down the average
        scored_topics.sort(key=lambda x: x[1])
        pruned = False
        # At least two grounded tags beyond the validated ones are kept: pruning
        # everything under 90 left a travel vlog with three tags. Below that
        # floor only a genuinely weak interpretation ("forbidden love", 51) goes,
        # and only when validated searches are there to carry the package.
        while scored_topics and (sum(s for _, s in scored_topics) / len(scored_topics)) < TARGET:
            lowest = scored_topics[0][1]
            if lowest >= TARGET:
                break
            if len(scored_topics) > 2 or (protected and lowest < _WEAK_TAG_SCORE):
                scored_topics.pop(0)
                pruned = True
            else:
                break
        # A package still under target keeps its tags. Raw candidates include
        # phrases the final selector rejected; promoting one here would bypass
        # its relevance, quote-copy and diversity checks.
        if not pruned:
            return pkg
        kept = {t for t, _ in scored_topics} | set(protected) | set(platform_tags)
        return {**pkg, "tags": [t for t in pkg_tags if t in kept]}

    def fit_order(pkg: dict[str, Any], pkg_gate: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        """A quote Short's alternatives in the order they carry the quote, the chosen title first."""
        if not short_quote:
            return pkg, pkg_gate
        ordered = sorted(pkg.get("variants") or [], key=title_fit, reverse=True)
        reordered = {**pkg, "variants": _lead_with(pkg.get("title", ""), ordered)}
        return (pkg, pkg_gate) if reordered["variants"] == pkg.get("variants") else (reordered, evaluate(reordered))

    def accepted_titles(pkg_gate: dict[str, Any]) -> list[str]:
        return [item["title"] for item in pkg_gate.get("accepted_candidates") or []
                if isinstance(item, dict) and item.get("title")]

    def with_alternatives(pkg: dict[str, Any], pkg_gate: dict[str, Any],
                          extra: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
        """``pkg`` with the titles of ``extra`` that pass beside its own, five at most.

        Kept only when more titles pass and the package ranks no lower: the
        repair's alternatives were discarded whenever its whole package did not
        outrank the current one, which left a quote Short with two titles.
        """
        merged = {**pkg, "variants": _lead_with(pkg.get("title", ""), [*(pkg.get("variants") or []), *extra])}
        merged_gate = evaluate(merged)
        passing = accepted_titles(merged_gate)
        if len(passing) <= len(accepted_titles(pkg_gate)) or rank(merged_gate, merged) < rank(pkg_gate, pkg):
            return pkg, pkg_gate
        merged = {**pkg, "title": passing[0], "variants": passing[:5]}
        return merged, evaluate(merged)

    best = deepcopy(package)
    gate = evaluate(best)
    # Check local tag refinement first
    candidate_tag_pkg = refine_tags_locally(best)
    if candidate_tag_pkg != best:
        candidate_tag_gate = evaluate(candidate_tag_pkg)
        if rank(candidate_tag_gate, candidate_tag_pkg) > rank(gate, best):
            best, gate = candidate_tag_pkg, candidate_tag_gate
    for title in dict.fromkeys([best.get("title", ""), *(best.get("variants") or [])]):
        candidate = {**best, "title": title, "variants": _lead_with(title, best.get("variants") or [])}
        candidate_gate = evaluate(candidate)
        if rank(candidate_gate, candidate) > rank(gate, best):
            best, gate = candidate, candidate_gate
    best, gate = fit_order(best, gate)
    trace: dict[str, Any] = {"target": TARGET, "attempted": False, "accepted": False,
                             "before": deepcopy(gate.get("final_seo_quality", {}))}
    scores = gate.get("final_seo_quality", {})
    # Only a measured shortfall is worth a repair request: a score the local
    # check cannot measure (a Tamil title) would not show any improvement,
    # a Short's tag score is not targeted at all, and a quote Short's title
    # is judged by its pass/fail checks rather than a word-overlap score.
    targeted = target_fields(short_form, bool(short_quote))
    below_target = any(scores.get(field) is not None and float(scores[field]) < TARGET for field in targeted)
    # The writer asks for five titles; when fewer than three passed, the one
    # repair asks for the missing alternatives rather than accepting two.
    few_titles = any(isinstance(item, dict) and item.get("code") == "fewer_legitimate_alternatives"
                     for item in gate.get("warnings") or [])
    needs_repair = below_target or few_titles
    if needs_repair and local_fallback:
        trace["skipped_reason"] = "writer_used_local_fallback"
    elif needs_repair and not gemini_client.is_available():
        trace["skipped_reason"] = "provider_not_configured"
    elif needs_repair and gemini_client.provider_health().get("cooldown_active"):
        trace["skipped_reason"] = "provider_cooling_down"
    elif needs_repair:
        trace["attempted"] = True
        feedback = []
        if below_target:
            feedback.append({"message":
                "Improve the title and description for source fidelity, natural wording and complementary meaning. "
                "Keep exact on-screen text in the description, followed by one useful non-repetitive sentence. "
                "Avoid vague hooks, invented claims, quote-copy titles and keyword stuffing. "
                "Measured scores: " + ", ".join(
                    f"{label}={'not measured' if scores.get(field) is None else scores.get(field)}"
                    for label, field in (("title", "title_score"), ("description", "description_score"), ("tags", "tag_score"))
                    if field in targeted
                ) + "; target 90 each."})
        if few_titles:
            feedback.append({"message": _alternatives_request(accepted_titles(gate), rejected_titles or [],
                                                              quote_short=bool(short_quote))})
        unrepaired = best
        repaired = generate_one(script, competitors, language=language, region=region,
            audience_type="general", category="quotes" if brief.get("exact_quote") else None,
            creator_brief=brief, channel_learning=learning, temperature=0.2, max_tokens=2200,
            repair_feedback=feedback, previous_package=best)
        # Attempts, retries and status of this request, so the caller can add
        # it to the package's Gemini totals whether or not it succeeded.
        trace["provider_call"] = dict(
            (repaired or {}).pop("_provider_trace", None) or gemini_client.last_generation_diagnostic()
        )
        if repaired:
            # Writer suggestions cannot bypass the research tag selector.
            repaired["tags"], repaired["hashtags"] = best["tags"], best["hashtags"]
            repaired_tag_pkg = refine_tags_locally(repaired)
            for title in dict.fromkeys([repaired_tag_pkg.get("title", ""), *(repaired_tag_pkg.get("variants") or [])]):
                candidate = {**repaired_tag_pkg, "title": title,
                             "variants": _lead_with(title, repaired_tag_pkg.get("variants") or [])}
                cand_gate = evaluate(candidate)
                if rank(cand_gate, candidate) > rank(gate, best):
                    best, gate = candidate, cand_gate
                    trace["accepted"] = True
            if few_titles:
                count = len(accepted_titles(gate))
                best, gate = with_alternatives(best, gate, [
                    unrepaired.get("title", ""), *(unrepaired.get("variants") or []),
                    repaired_tag_pkg.get("title", ""), *(repaired_tag_pkg.get("variants") or []),
                ])
                if len(accepted_titles(gate)) > count:
                    trace["accepted"] = True
                    trace["alternatives_added"] = len(accepted_titles(gate)) - count
            if trace["accepted"]:
                best, gate = fit_order(best, gate)
    trace["after"] = deepcopy(gate.get("final_seo_quality", {}))
    return best, trace
