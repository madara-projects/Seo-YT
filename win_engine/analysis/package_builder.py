"""Create usable title-and-thumbnail choices from validated title variants."""

from __future__ import annotations

from typing import Any

from win_engine.ai_enhancement import find_content_similarity
from win_engine.analysis.generation_quality import candidate_mechanism
from win_engine.analysis.text_tokens import unicode_words


_GENERIC_WORDS = {
    "amazing", "best", "crazy", "epic", "life", "movie", "new", "video", "vlog", "wow",
    "today", "update", "watch", "must", "viral", "everything", "things",
}
_CONTEXT_STOPWORDS = {"about", "after", "and", "are", "for", "from", "have", "into", "my", "of", "our", "the", "this", "to", "with", "your"}
# Gate codes for a title that claims something the creator never said. Other
# rejections (a near-duplicate, a missing #shorts) are not misleading.
_MISLEADING_CODES = {
    "relationship_event", "invented_loss_event", "invented_outcome", "invented_evidence",
    "invented_relationship", "invented_causality", "invented_message_content", "unsupported_context",
    "invented_story_detail", "unsupported_action", "invented_timescale", "dropped_number",
    "unsupported_instructional_framing",
}


def title_gate_status(title: str, gate: dict[str, Any] | None, *, source: str) -> dict[str, Any]:
    """This title's verdict in a quality gate, or not_evaluated when the gate never judged it."""

    key = " ".join(unicode_words(title))
    for item in (gate or {}).get("accepted_candidates") or []:
        if isinstance(item, dict) and " ".join(unicode_words(item.get("title"))) == key:
            return {"status": "pass", "source": source}
    for item in (gate or {}).get("rejected_candidates") or []:
        if isinstance(item, dict) and " ".join(unicode_words(item.get("title"))) == key:
            codes = [
                str(reason.get("code") or "quality_failure")
                for reason in item.get("issues") or [] if isinstance(reason, dict)
            ]
            return {"status": "fail", "source": source, "issues": list(dict.fromkeys(codes))}
    return {"status": "not_evaluated", "source": source}


def build_title_thumbnail_packages(
    title_variants: list[dict[str, Any]],
    creator_brief: dict[str, Any] | None = None,
    competitor_titles: list[str] | None = None,
    validated: bool = False,
    focus_phrases: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Return only clear, non-duplicated packages a creator can compare.

    ``focus_phrases`` are the video's final subject tags; the
    thumbnail text keeps them when the title is too long to use whole.
    A variant's ``quality_gate`` (see ``title_gate_status``) decides its
    approval and misleading-risk labels; ``validated`` only skips this
    module's own checks, so an unjudged title reads "not evaluated".
    """

    brief = creator_brief or {}
    packages: list[dict[str, Any]] = []
    seen: set[str] = set()
    for variant in title_variants:
        title = str(variant.get("title") or "").strip()
        key = title.casefold()
        if not title or key in seen:
            continue
        seen.add(key)
        issues = [] if validated else _quality_issues(title, brief, competitor_titles or [])
        if issues:
            continue
        gate = variant.get("quality_gate") if isinstance(variant.get("quality_gate"), dict) else (
            {"status": "not_evaluated", "source": "none"} if validated
            else {"status": "pass", "source": "package_builder_checks"}
        )
        style = _title_style(title)
        package_intent = str(variant.get("package_intent") or "Alternative")
        packages.append(
            {
                "package_id": f"package-{chr(97 + len(packages))}",
                "package": chr(65 + len(packages)),
                "title": title,
                "thumbnail_text": _thumbnail_text(title, focus_phrases),
                "thumbnail_visual": str(brief.get("thumbnail_idea") or _default_visual(brief)).strip(),
                "viewer_promise": str(brief.get("viewer_promise") or _default_promise(brief)).strip(),
                "why_click": _why_click(style, brief, package_intent),
                "approach": style,
                "package_intent": package_intent,
                "best_for": _best_for(style, brief, package_intent),
                "misleading_risk": _misleading_risk(gate),
                "quality_status": _quality_status(gate),
                "mechanism": str(variant.get("mechanism") or candidate_mechanism(title)),
                "reason": str(variant.get("reason") or "A distinct, source-supported packaging option."),
                "discovery_surface": str(variant.get("discovery_surface") or package_intent),
                "evidence_used": variant.get("evidence_used") or {"status": "insufficient_evidence"},
                "tradeoffs": variant.get("tradeoffs") or ["Generated suggestion; publishing outcome is not guaranteed."],
                "quality_gate": gate,
                "provenance": "generated_suggestion",
            }
        )
    return packages[:8]


def _quality_status(gate: dict[str, Any]) -> str:
    status = gate.get("status")
    return "approved" if status == "pass" else "rejected" if status == "fail" else "not evaluated"


def _misleading_risk(gate: dict[str, Any]) -> str:
    status = gate.get("status")
    if status == "pass":
        return "low"
    if status == "fail":
        return "high" if _MISLEADING_CODES & set(gate.get("issues") or []) else "low"
    return "not evaluated"


def _quality_issues(title: str, brief: dict[str, Any], competitor_titles: list[str]) -> list[str]:
    issues: list[str] = []
    if len(title) < 28 or len(title) > 70:
        issues.append("title length is outside the useful range")
    lowered = title.lower()
    if any(term in lowered for term in ("guaranteed", "100%", "secret trick", "get rich quick", "you won't believe")):
        issues.append("misleading claim")
    title_words = _meaningful_words(title)
    if len(title_words) < 3 or all(word in _GENERIC_WORDS for word in title_words):
        issues.append("title is too vague")
    context_words = _meaningful_words(" ".join(str(brief.get(field) or "") for field in ("content", "unique_angle", "viewer_promise", "proof")))
    if context_words and not set(title_words).intersection(context_words):
        issues.append("title is not connected to the video brief")
    if any(find_content_similarity(title, competitor) >= 0.78 for competitor in competitor_titles if competitor):
        issues.append("title is too similar to a competitor")
    return issues


def _meaningful_words(value: str) -> list[str]:
    return [word for word in unicode_words(value) if len(word) >= 3 and word not in _CONTEXT_STOPWORDS]


# Words a thumbnail phrase may contain but must not start or end with: a
# preposition, pronoun, auxiliary or negation leaves "LOVE QUOTES WHEN IT".
_EDGE_WORDS = {
    "of", "in", "on", "at", "for", "with", "and", "or", "but", "to", "from", "by", "than", "that", "is", "are",
    "was", "were", "be", "been", "being", "it", "its", "when", "what", "which", "who", "about", "can", "cannot",
    "can't", "never", "not", "so", "very", "more", "most", "there", "this", "these", "those", "them", "they",
}


def _stem(word: str) -> str:
    folded = word.casefold()
    for suffix in ("ing", "ed", "es", "s"):
        if folded.endswith(suffix) and len(folded) - len(suffix) >= 3:
            folded = folded[: -len(suffix)]
            break
    return folded.rstrip("e")


def _thumbnail_text(title: str, focus_phrases: list[str] | None = None) -> str:
    # The creator's thumbnail direction describes the image and is shown as
    # the visual. Its first words are not text for the image: "Show me holding
    # the phone..." became the thumbnail text "show me holding the". Lines
    # written for two test quotes ("SILENCE KNOWS", "KNOW YOUR WORTH") went on
    # any quote that shared their words; the text now comes from the title.
    # A validated search phrase that the title contains is a ready-made,
    # grammatical thumbnail line ("SAD LOVE QUOTES", "PAINFUL LOVE").
    phrases = [" ".join(str(item).split()) for item in (focus_phrases or []) if str(item).strip()]
    title_folded = f" {' '.join(unicode_words(title))} ".casefold()
    contained = [phrase for phrase in phrases if 2 <= len(phrase.split()) <= 4 and f" {phrase.casefold()} " in title_folded]
    if contained:
        return max(contained, key=lambda phrase: len(phrase.split())).upper()
    ignored = {"the", "a", "an", "how", "to", "my", "your", "with", "for", "what", "is", "really", "shorts"}
    words = [word for word in unicode_words(title) if word.lower() not in ignored]
    # Next best: the strongest tag sharing a word with this title (stems, so
    # "loving" finds "love quotes"). A real search phrase reads cleanly; a
    # window cut from a sentence gave "HIDDEN DETAIL IN NEW".
    title_stems = {_stem(word) for word in words if word.lower() not in _EDGE_WORDS}

    def shared_count(phrase: str) -> int:
        return len({_stem(word) for word in phrase.split()} & title_stems)

    shared = [phrase for phrase in phrases if 2 <= len(phrase.split()) <= 4 and shared_count(phrase)]
    if shared:
        # The tag that overlaps this title most; the earlier (stronger) tag on ties.
        return max(shared, key=lambda phrase: (shared_count(phrase), -phrases.index(phrase))).upper()
    # The first four words cut "The heavy weight of impossible love" down to
    # "HEAVY WEIGHT OF IMPOSSIBLE". Choose the window that names the most of the
    # subject and does not start or end on a connective.
    focus = {word.casefold() for phrase in phrases for word in phrase.split()}
    best: tuple[int, int, list[str]] | None = None
    for size in (4, 3, 2):
        for start in range(max(len(words) - size, 0) + 1):
            window = words[start:start + size]
            while window and window[0].lower() in _EDGE_WORDS:
                window = window[1:]
            while window and window[-1].lower() in _EDGE_WORDS:
                window = window[:-1]
            if len(window) < 2 and len(words) >= 2:
                continue
            rank = (sum(word.casefold() in focus for word in window), len(window))
            if best is None or rank > best[:2]:
                best = (*rank, window)
    if best is None:
        chosen = words[:4]
        while len(chosen) > 1 and chosen[0].lower() in _EDGE_WORDS:
            chosen = chosen[1:]
        while len(chosen) > 1 and chosen[-1].lower() in _EDGE_WORDS:
            chosen = chosen[:-1]
    else:
        chosen = best[2]
    return " ".join(word.upper() for word in chosen) or "WATCH THIS"


def _default_visual(brief: dict[str, Any]) -> str:
    proof = str(brief.get("proof") or "").strip()
    if proof:
        return proof
    visual = str(brief.get("visual_requirements") or "").strip(" .")
    if visual:
        return f"Use a wide, uncluttered frame showing {visual[:1].lower() + visual[1:]}; keep the subject and text readable."
    return "Use one clear real frame from the video with a readable emotional focal point."


def _default_promise(brief: dict[str, Any]) -> str:
    quote = str(brief.get("exact_quote") or brief.get("on_screen_text") or "").casefold()
    if quote:
        return "A brief moment of recognition for viewers who connect with the quote."
    topic = str(brief.get("topic") or "the video's subject").strip()
    return f"A clear, source-faithful look at {topic}."


def _title_style(title: str) -> str:
    lowered = title.lower()
    if lowered.startswith("how to") or any(word in lowered for word in ("guide", "tips", "step-by-step")):
        return "searchable"
    if "?" in title or any(word in lowered for word in ("real", "truth", "inside", "what nobody")):
        return "curiosity-led"
    return "balanced"


def _why_click(style: str, brief: dict[str, Any], package_intent: str = "") -> str:
    # Whole sentences only: stitching the brief in produced "...while
    # promising: A brief moment..." and "backed by Rainy road with vehicles."
    proof = str(brief.get("proof") or "").strip().rstrip(".")
    visual = str(brief.get("visual_requirements") or "").strip().rstrip(".")
    support = (f" The proof ({proof[:1].lower() + proof[1:]}) backs it up." if proof
               else f" The background ({visual[:1].lower() + visual[1:]}) sets the mood." if visual and len(visual.split()) <= 12
               else "")
    if package_intent == "Existing audience":
        return "It speaks directly to viewers who already follow this subject." + support
    if package_intent == "Browse":
        return "It leads with the feeling rather than a keyword, which suits the Home and Shorts feeds." + support
    if style == "searchable" or package_intent == "Search":
        return "It leads with the words viewers type into search, so the video can be found for that phrase."
    if style == "curiosity-led":
        return "It raises a question the video answers." + support
    return "It names the subject clearly and hints at the payoff." + support


def _best_for(style: str, brief: dict[str, Any], package_intent: str = "") -> str:
    if package_intent == "Search":
        return "Search / new viewers"
    if package_intent == "Browse":
        return "Browse / home and suggested viewers"
    if package_intent == "Existing audience":
        return "Returning viewers / existing audience"
    if style == "searchable":
        return "Search / new viewers"
    if style == "curiosity-led":
        return "Browse / relatable viewers"
    return "Search and browse"
