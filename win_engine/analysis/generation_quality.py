"""Deterministic Phase 4 generation quality and diversity checks.

The gate is deliberately provider-independent. It accepts a generated package,
checks it against the creator's source material and recent title history, and
returns structured reasons that can be stored and rendered without claiming a
performance prediction.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Iterable


_TAMIL_RANGE = re.compile(r"[\u0B80-\u0BFF]")
_GENERIC_TITLE_PATTERNS = (
    re.compile(r"^the honest truth about\b", re.IGNORECASE),
    re.compile(r"^what .+ really means\b", re.IGNORECASE),
    re.compile(r"^.+: what you need to know\b", re.IGNORECASE),
    re.compile(r"^a different way to see\b", re.IGNORECASE),
    re.compile(r"^the most useful lesson from\b", re.IGNORECASE),
    re.compile(r"^a quiet reminder about\b", re.IGNORECASE),
    re.compile(r"^(?:how .+ works in practice|the practical side of|a closer look at|what to know about)\b", re.IGNORECASE),
    re.compile(r"^(?:best .+ tips|complete guide to|everything you need to know|learn how to|methods for|ways to|common questions about)\b", re.IGNORECASE),
    re.compile(r"^(?:a quiet look at|a moment about|reflecting on)\s*(?:your|the)?\s*(?:topic|video|story)?\s*$", re.IGNORECASE),
)
_UNSUPPORTED_CLAIMS = (
    ("relationship_event", re.compile(r"\b(?:they|he|she) (?:left|cheated|lied|returned|came back|walked away)\b", re.IGNORECASE)),
    ("invented_outcome", re.compile(r"\b(?:guaranteed|proven to|will make you|will get you|100%|go viral)\b", re.IGNORECASE)),
    ("invented_evidence", re.compile(r"\b(?:studies show|research proves|scientists found|data proves)\b", re.IGNORECASE)),
    ("invented_relationship", re.compile(r"\b(?:breakup|toxic relationship|one-sided relationship|just an option)\b", re.IGNORECASE)),
)
_SHORT_FORMATS = {"short", "shorts", "youtube_shorts", "quote", "reel", "reels"}
# Platform-format words are useful as a title hashtag/hashtag, but they are not
# meaningful search tags.  The old phase contract required ``shorts`` in the
# tag list; that produced filler rather than a source-grounded search concept.
_PLATFORM_TAGS = {
    "short", "shorts", "yt", "youtube", "youtube shorts", "viral", "viral shorts",
    "trending", "trending shorts", "short video", "video", "fyp",
}
_SHORTS_TITLE_RE = re.compile(r"(?<![\w#])#shorts(?!\w)", re.IGNORECASE)
_TITLE_EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]")
_EMOJI_CONTEXT_TERMS = {
    "aesthetic", "beach", "beautiful", "breakup", "city", "comedy", "emotional",
    "food", "funny", "heart", "heartbreak", "hill", "love", "memory", "miss",
    "moon", "mountain", "nature", "night", "quote", "rain", "rainy", "road",
    "sad", "sky", "storm", "sunset", "surprise", "travel", "unexpected",
}
_GENERIC_FORMAT_TAGS = {
    "shorts", "yt", "youtube", "youtube shorts", "viral", "viral shorts",
    "trending", "trending shorts", "short video", "video", "fyp",
}
_UNSUPPORTED_CONTEXT_TERMS = {
    "childhood", "workplace", "therapy", "therapist", "clinical", "diagnosis", "depression",
    "anxiety", "trauma", "partner", "boyfriend", "girlfriend", "husband", "wife", "product",
    "review", "comparison", "customer", "office", "school", "family",
    "night", "nighttime", "midnight", "dark", "darkness", "empty", "deserted",
    "peace", "peaceful", "comfort", "comforting", "healing",
}
_DESCRIPTION_BOILERPLATE = (
    re.compile(r"\b(?:this video focuses on|this video explores|experience a brief moment of)\b", re.IGNORECASE),
    re.compile(r"\b(?:perfect for anyone who|take a moment to breathe and process)\b", re.IGNORECASE),
)
_INSTRUCTIONAL_SOURCE_RE = re.compile(
    r"\b(?:tutorial|walkthrough|step[- ]by[- ]step|practical tips?|guide|"
    r"we (?:explain|cover|break down|show)|here are|demonstrat(?:e|ion)|instructions?)\b",
    re.IGNORECASE,
)
_UNSUPPORTED_INSTRUCTIONAL_RE = re.compile(
    r"\b(?:coping with|dealing with|overcome|practical (?:tips?|ways?)|advice|"
    r"common questions?|q\s*&\s*a|tutorial|explain(?:s|ing)?|break(?:ing)? down|"
    r"step[- ]by[- ]step|beginner(?:-friendly)? guide|complete guide|guide to|lessons?|"
    r"how to (?:cope|deal|fix|make|clean|improve|handle|recover)|how you can handle|"
    r"walk(?:s|ing)? through)\b",
    re.IGNORECASE,
)
_INSTRUCTIONAL_CONTEXT_RE = re.compile(
    r"\b(?:tutorial|how[- ]to|walkthrough|guide|educational|explainer|comparison|review|demonstration)\b",
    re.IGNORECASE,
)
_PROCEDURAL_ACTION_RE = re.compile(
    r"\b(?:check|inspect|adjust|reduce|lower|use|remove|blow|clean|try|reposition)\b",
    re.IGNORECASE,
)


def normalize_unicode(value: Any) -> str:
    """Return stable printable Unicode without invisible control characters."""

    text = unicodedata.normalize("NFKC", str(value or ""))
    return "".join(
        char for char in text
        if char in "\n\t\u200d" or not unicodedata.category(char).startswith("C")
    ).strip()


def unicode_words(value: Any) -> list[str]:
    """Tokenize letters and numbers from every Unicode script."""

    # Python's ``\w`` does not consistently retain Indic combining marks on
    # every supported runtime. Keep the Tamil block with its base characters
    # so language validation and source-overlap checks do not erase Tamil text.
    return [
        token.casefold()
        for token in re.findall(r"[\w\u0B80-\u0BFF]+(?:['’][\w\u0B80-\u0BFF]+)?", normalize_unicode(value), re.UNICODE)
        if len(token.replace("_", "")) > 1
    ]


def title_similarity(left: Any, right: Any) -> float:
    """Combine Unicode sequence and token overlap similarity."""

    left_text = " ".join(unicode_words(left))
    right_text = " ".join(unicode_words(right))
    if not left_text or not right_text:
        return 0.0
    sequence = SequenceMatcher(None, left_text, right_text).ratio()
    left_tokens, right_tokens = set(left_text.split()), set(right_text.split())
    overlap = len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)
    return round(max(sequence, overlap), 4)


def title_copies_quote(value: Any, exact_quote: Any) -> bool:
    """Catch full and truncated quote copies after hashtags/emoji are removed."""

    title_words = [word for word in unicode_words(value) if word != "shorts"]
    quote_words = unicode_words(exact_quote)
    if not title_words or not quote_words:
        return False
    if title_similarity(" ".join(title_words), " ".join(quote_words)) >= 0.86:
        return True
    title_set, quote_set = set(title_words), set(quote_words)
    return len(title_words) >= 5 and len(title_set & quote_set) / len(title_set) >= 0.9


def candidate_mechanism(title: str) -> str:
    """Describe a title mechanism without pretending it predicts performance."""

    lowered = normalize_unicode(title).casefold()
    if re.search(r"\bhow (?:to|i)\b|\bguide\b|\bsteps?\b|\btips?\b", lowered):
        return "practical utility"
    if "?" in title or re.search(r"\bwhy\b|\bwhat\b|\bhow\b", lowered):
        return "explanation"
    if re.search(r"\bvs\.?\b|\bcompared?\b|\bbetter\b", lowered):
        return "comparison"
    if re.search(r"\bmistake\b|\bwrong\b|\bmyth\b|\bmisconception\b", lowered):
        return "misconception correction"
    if re.search(r"\bafter\b|\bbefore\b|\bbecame\b|\bchanged\b|\bfrom .+ to\b", lowered):
        return "transformation"
    if re.search(r"\btruth\b|\bsecret\b|\bhidden\b|\bnobody\b", lowered):
        return "hidden mechanism"
    if re.search(r"\bdeserve\b|\bhurts?\b|\bsilence\b|\bheart\b|\bfeel\b", lowered):
        return "emotional tension"
    return "direct topic framing"


def is_short_content(script: str, creator_brief: dict[str, Any] | None = None) -> bool:
    """Resolve Short intent from the structured brief first, then explicit source wording."""

    brief = creator_brief or {}
    format_value = normalize_unicode(brief.get("video_format")).casefold().replace("-", "_").replace(" ", "_")
    if format_value in _SHORT_FORMATS or any(token in format_value for token in ("youtube_short", "short_form", "quote_short")):
        return True
    # The structured brief preserves the creator's original source.  The caller's
    # `script` can be an expanded research query, so it must not turn a silent
    # quote into an apparent tutorial merely because it contains helper text.
    source = normalize_unicode(brief.get("content") or script)
    return bool(re.search(r"\b(?:youtube\s+shorts?|short[- ]form|shorts?|reels?|quote\s+short)\b", source, re.IGNORECASE))


def is_silent_quote_only_short(script: str, creator_brief: dict[str, Any] | None = None) -> bool:
    """Identify a quote-led Short that does not supply instructional content."""

    brief = creator_brief or {}
    # Prefer the creator's preserved source to the expanded request/query text.
    # The latter is a research aid, not evidence that the video teaches anything.
    source = normalize_unicode(brief.get("content") or script)
    quote = normalize_unicode(brief.get("exact_quote") or brief.get("on_screen_text") or _extract_quote(source))
    return bool(
        quote
        and normalize_unicode(brief.get("voice_over")).casefold() == "none"
        and is_short_content(source, brief)
        and not source_supports_instructional_framing(source, brief)
    )


def source_supports_instructional_framing(script: str, creator_brief: dict[str, Any] | None = None) -> bool:
    """Return whether the creator source actually supports teaching/advice framing."""

    brief = creator_brief or {}
    source = normalize_unicode(brief.get("content") or script)
    context = " ".join(normalize_unicode(brief.get(field)) for field in (
        "video_format", "creator_intent", "content_constraints", "viewer_promise",
    ))
    if _INSTRUCTIONAL_CONTEXT_RE.search(context) or _INSTRUCTIONAL_SOURCE_RE.search(source):
        return True
    # A procedural source can be instructional even when the creator labels it
    # as a Short rather than a tutorial (for example, check/inspect/adjust).
    actions = _PROCEDURAL_ACTION_RE.findall(source)
    return len(actions) >= 2 and bool(re.search(r"\b(?:if|then|to)\b", source, re.IGNORECASE))


def source_requires_noninstructional_framing(script: str, creator_brief: dict[str, Any] | None = None) -> bool:
    """Identify source-bound silent, story, and reflection content that cannot become a guide."""

    brief = creator_brief or {}
    if is_silent_quote_only_short(script, brief):
        return True
    context = " ".join(normalize_unicode(brief.get(field)) for field in (
        "creator_intent", "content_constraints", "visual_requirements",
    ))
    return bool(
        re.search(r"\b(?:story|storytelling|reflection|reflective|minimal|cinematic|narrative)\b", context, re.IGNORECASE)
        or re.search(r"\bnot\s+(?:a\s+)?(?:tutorial|guide|advice|therapy)\b", context, re.IGNORECASE)
    ) and not source_supports_instructional_framing(script, brief)


def source_withholds_message_content(script: str, creator_brief: dict[str, Any] | None = None) -> bool:
    """Identify story sources that mention an unread message but do not supply its words."""

    brief = creator_brief or {}
    source = normalize_unicode(brief.get("content") or script)
    mentions_short_message = bool(re.search(
        r"\bmessage\b.*?\b(?:only|just)?\s*(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+words?\b",
        source,
        re.IGNORECASE,
    ))
    quoted_content = bool(re.search(r'["\u201c][^"\u201d]{1,80}["\u201d]', source))
    return mentions_short_message and not quoted_content


def has_unsupported_instructional_framing(value: Any) -> bool:
    """Return whether text promises instruction a silent quote does not contain."""

    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", normalize_unicode(value).replace("#", " "))
    return bool(_UNSUPPORTED_INSTRUCTIONAL_RE.search(text))


def filter_source_hashtags(
    hashtags: Iterable[str], script: str, creator_brief: dict[str, Any] | None = None,
) -> list[str]:
    """Drop instructional hashtags when the creator source is non-instructional."""

    values = [normalize_unicode(item) for item in hashtags if normalize_unicode(item)]
    if not source_requires_noninstructional_framing(script, creator_brief):
        return values
    return [item for item in values if not has_unsupported_instructional_framing(item)]


def title_emojis(value: Any) -> list[str]:
    """Return visible emoji bases for deterministic count/template checks."""

    return _TITLE_EMOJI_RE.findall(normalize_unicode(value))


def evaluate_package_quality(
    package: dict[str, Any],
    *,
    script: str,
    creator_brief: dict[str, Any] | None = None,
    language: str = "english",
    recent_titles: Iterable[str] | None = None,
    published_titles: Iterable[str] | None = None,
    require_shorts_tags: bool = True,
    tag_context: Any = None,
    tag_evidence: dict[str, Any] | None = None,
    competitor_titles: Iterable[str] | None = None,
    enforce_final_tag_rules: bool = True,
) -> dict[str, Any]:
    """Return a structured, deterministic quality decision for one package."""

    brief = creator_brief or {}
    source = normalize_unicode(script or brief.get("content"))
    source_folded = " ".join(unicode_words(source))
    exact_quote = normalize_unicode(brief.get("exact_quote") or _extract_quote(source))
    is_short = is_short_content(source, brief)
    silent_quote_only = is_silent_quote_only_short(source, brief)
    non_instructional = source_requires_noninstructional_framing(source, brief)
    emoji_context = " ".join(unicode_words(" ".join(
        normalize_unicode(brief.get(field))
        for field in ("content", "exact_quote", "on_screen_text", "visual_requirements", "viewer_promise", "unique_angle")
    ) + " " + source))
    emoji_recommended = is_short and any(term in set(emoji_context.split()) for term in _EMOJI_CONTEXT_TERMS)
    requested_language = normalize_unicode(language).casefold() or "english"

    title_values = [package.get("title"), *(package.get("variants") or [])]
    titles = _unique([normalize_unicode(item) for item in title_values if normalize_unicode(item)])
    recent = [normalize_unicode(item) for item in (recent_titles or []) if normalize_unicode(item)]
    published = [normalize_unicode(item) for item in (published_titles or []) if normalize_unicode(item)]
    competitors = [normalize_unicode(item) for item in (competitor_titles or []) if normalize_unicode(item)]

    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for index, title in enumerate(titles):
        reasons: list[dict[str, Any]] = []
        shorts_count = len(_SHORTS_TITLE_RE.findall(title))
        emojis = title_emojis(title)
        if is_short and shorts_count == 0:
            reasons.append(_issue("missing_shorts_title_hashtag", "title", "A YouTube Short title must contain #shorts exactly once.", index=index))
        elif shorts_count > 1:
            reasons.append(_issue("duplicate_shorts_title_hashtag", "title", "The title contains #shorts more than once.", index=index))
        elif not is_short and shorts_count:
            reasons.append(_issue("unexpected_shorts_title_hashtag", "title", "A non-Short title must not be labelled #shorts.", index=index))
        if len(title) > 100:
            reasons.append(_issue("title_too_long", "title", "The upload-ready title exceeds YouTube's 100-character limit.", index=index))
        if len(emojis) > 2:
            reasons.append(_issue("excessive_title_emojis", "title", "Use no more than two relevant emojis in a title.", index=index))
        if any(left == right for left, right in zip(emojis, emojis[1:])):
            reasons.append(_issue("repeated_title_emoji", "title", "The title repeats the same emoji in sequence.", index=index))
        if emoji_recommended and not emojis:
            warnings.append(_issue(
                "missing_contextual_title_emoji", "title",
                "A relevant emoji may improve visual fit, but it is not required for a source-faithful title.",
                severity="warning", index=index,
            ))
        if exact_quote and len(titles) > 1 and title_copies_quote(title, exact_quote):
            reasons.append(_issue(
                "title_duplicates_on_screen_quote", "title",
                "When alternatives exist, the title must complement rather than repeat the complete on-screen quote.",
                index=index,
            ))
        signature = "".join(emojis)
        recent_signatures = ["".join(title_emojis(old)) for old in recent[-3:]]
        if signature and len(recent_signatures) == 3 and all(item == signature for item in recent_signatures):
            reasons.append(_issue("repeated_emoji_template", "title", "The emoji pattern repeats across the three most recent generated titles.", index=index))
        if any(pattern.search(title) for pattern in _GENERIC_TITLE_PATTERNS):
            reasons.append(_issue("generic_template", "title", "Title uses a repeatedly generic template.", index=index))
        reasons.extend(_title_usefulness_issues(
            title, source, brief, non_instructional, competitors, index=index,
            source_overlap_supported=requested_language not in {"tamil", "tanglish", "hindi"},
        ))
        unsupported = _unsupported_claims(title, source)
        reasons.extend(_issue(code, "title", "Title introduces a claim not supported by the creator source.", index=index) for code in unsupported)
        if non_instructional and has_unsupported_instructional_framing(title):
            reasons.append(_issue("unsupported_instructional_framing", "title", "A non-instructional source must not be framed as advice, a guide, or instruction.", index=index))
        duplicate_index = next(
            (other for other, item in enumerate(accepted) if title_similarity(title, item["title"]) >= 0.82),
            None,
        )
        if duplicate_index is not None:
            reasons.append(_issue("semantic_duplicate", "title", f"Title is too similar to accepted candidate {duplicate_index + 1}.", index=index))
        if any(title_similarity(title, old) >= 0.88 for old in [*recent, *published]):
            reasons.append(_issue("recent_title_repetition", "title", "Title repeats a recent generated or published title pattern.", index=index))
        if requested_language == "tamil" and not _TAMIL_RANGE.search(title):
            reasons.append(_issue("language_mismatch", "title", "Tamil output title does not contain Tamil script.", index=index))
        if requested_language == "tanglish" and not _has_latin_or_tamil(title):
            reasons.append(_issue("language_mismatch", "title", "Tanglish title has no usable Roman or Tamil text.", index=index))
        if len(unicode_words(title)) < 2:
            reasons.append(_issue("title_too_vague", "title", "Title does not contain enough meaningful text.", index=index))
        if reasons:
            rejected.append({"title": title, "issues": reasons})
        else:
            accepted.append({
                "title": title,
                "mechanism": candidate_mechanism(title),
                "source": "generated_suggestion",
            })

    description = normalize_unicode(package.get("description"))
    if not description:
        issues.append(_issue("missing_description", "description", "Description is empty."))
    else:
        description_folded = " ".join(unicode_words(description))
        if re.search(r"(?i)\ba\s+(?:one|a|an|the)\s+(?:person|man|woman|boy|girl)\b", description):
            issues.append(_issue("broken_description_grammar", "description", "Description contains a duplicated article or production-note fragment."))
        exact_quote_text = re.sub(r"\s+", " ", exact_quote).strip()
        normalized_description = re.sub(r"\s+", " ", description).strip()
        if exact_quote and exact_quote_text not in normalized_description:
            issues.append(_issue("quote_fidelity", "description", "Description does not preserve the exact on-screen quote."))
        for code in _unsupported_claims(description, source):
            issues.append(_issue(code, "description", "Description introduces a claim not supported by the creator source."))
        if non_instructional and has_unsupported_instructional_framing(description):
            issues.append(_issue("unsupported_instructional_framing", "description", "A non-instructional source must not claim tips, advice, explanations, or instructional content absent from the source."))
        if _looks_like_tag_list(description):
            issues.append(_issue("tag_list_contamination", "description", "Description reads like a repeated SEO tag list."))
        issues.extend(_description_usefulness_issues(
            description, source, brief, non_instructional,
            source_overlap_supported=requested_language not in {"tamil", "tanglish", "hindi"},
        ))
        if normalize_unicode(brief.get("voice_over")).casefold() == "none" and re.search(
            r"\b(?:listen to|hear (?:me|the)|voice[- ]?over|narrat(?:e|ed|ion))\b", description, re.IGNORECASE
        ):
            issues.append(_issue("voice_over_contradiction", "description", "Description claims narration although the brief says no voice-over."))
        if requested_language == "tamil" and not _TAMIL_RANGE.search(description):
            issues.append(_issue("language_mismatch", "description", "Tamil output description does not contain Tamil script."))
        if requested_language == "tanglish" and not _has_latin_or_tamil(description):
            issues.append(_issue("language_mismatch", "description", "Tanglish description has no usable Roman or Tamil text."))

    tags = _unique([normalize_unicode(tag).casefold().lstrip("#") for tag in (package.get("tags") or [])])
    for tag in tags:
        if len(unicode_words(tag)) > 8 or "," in tag:
            issues.append(_issue("tag_list_contamination", "tags", f"Tag is not one focused phrase: {tag}"))
        if non_instructional and has_unsupported_instructional_framing(tag):
            issues.append(_issue("unsupported_instructional_framing", "tags", f"Tag implies instruction not present in this source: {tag}"))
        if enforce_final_tag_rules and tag in _PLATFORM_TAGS:
            issues.append(_issue("platform_tag_filler", "tags", f"Platform-format filler is not a useful video tag: {tag}"))
    context_text = " ".join(normalize_unicode(item) for item in tag_context) if isinstance(tag_context, (list, tuple, set)) else normalize_unicode(tag_context)
    source_tokens = set(unicode_words(" ".join([
        source,
        *(normalize_unicode(brief.get(field)) for field in (
            "content", "exact_quote", "on_screen_text", "visual_requirements",
            "viewer_promise", "unique_angle", "topic", "creator_intent", "content_constraints",
        )),
    ]))) | set(unicode_words(context_text))
    source_tokens |= set(unicode_words(" ".join(
        str(item) for item in (brief.get("seo_research_targets") or []) if str(item).strip()
    )))
    selected_tag_evidence = {
        normalize_unicode(item.get("keyword")).casefold(): item
        for item in (tag_evidence or {}).get("selected_keywords", [])
        if isinstance(item, dict) and normalize_unicode(item.get("keyword"))
    }

    def _tag_has_grounding(tag: str) -> bool:
        if set(unicode_words(tag)) & source_tokens:
            return True
        row = selected_tag_evidence.get(normalize_unicode(tag).casefold())
        return bool(row and int(row.get("source_support_score") or 0) >= 70)

    contextual_tags = [
        tag for tag in tags
        if tag not in _GENERIC_FORMAT_TAGS
        and _tag_has_grounding(tag)
    ]
    if tags and not contextual_tags:
        issues.append(_issue("non_contextual_tags", "tags", "At least one tag must be derived from the actual video or creator brief."))
    generic_count = sum(1 for tag in tags if tag in _GENERIC_FORMAT_TAGS)
    if generic_count and generic_count >= max(2, len(contextual_tags) + 1):
        issues.append(_issue(
            "generic_tag_filler", "tags",
            "Generic platform tags outnumber subject-specific tags; remove filler rather than pad the package.",
        ))
    for tag in tags:
        if tag not in _GENERIC_FORMAT_TAGS and not _tag_has_grounding(tag):
            issues.append(_issue("unrelated_tag", "tags", f"Tag is not grounded in the supplied topic: {tag}"))
    if enforce_final_tag_rules:
        issues.extend(_tag_provenance_issues(tags, tag_evidence))

    hashtags = [normalize_unicode(item) for item in (package.get("hashtags") or []) if normalize_unicode(item)]
    normalized_hashtags = [item.casefold().lstrip("#") for item in hashtags]
    if len(normalized_hashtags) != len(set(normalized_hashtags)):
        issues.append(_issue("duplicate_hashtag", "hashtags", "Hashtags contain duplicates."))
    if len(hashtags) > 3:
        issues.append(_issue("excessive_hashtags", "hashtags", "Use no more than three focused hashtags."))
    if non_instructional:
        for hashtag in hashtags:
            if has_unsupported_instructional_framing(hashtag):
                issues.append(_issue("unsupported_instructional_framing", "hashtags", f"Hashtag implies instruction not present in this source: {hashtag}"))
        if any(len(unicode_words(item.lstrip("#"))) > 4 for item in hashtags):
            issues.append(_issue("hashtag_too_long", "hashtags", "A hashtag must be a short readable topic label, not a sentence."))

    if not accepted:
        issues.append(_issue("no_acceptable_title", "titles", "No title candidate passed the local quality gate."))
    elif len(accepted) < 3:
        warnings.append(_issue(
            "fewer_legitimate_alternatives",
            "titles",
            f"Only {len(accepted)} materially distinct title alternative(s) passed; the result was not padded.",
            severity="warning",
        ))

    semantic_quality = _final_semantic_quality(
        package=package,
        accepted=accepted,
        tags=tags,
        source=source,
        brief=brief,
        tag_evidence=tag_evidence,
        competitors=competitors,
        source_overlap_supported=requested_language not in {"tamil", "tanglish", "hindi"},
    )
    issues.extend(semantic_quality["critical_issues"])
    warnings.extend(semantic_quality["warnings"])

    all_errors = [*issues, *(reason for item in rejected for reason in item["issues"])]
    passed = not issues and bool(accepted)
    verdict = (
        "RED" if not passed or semantic_quality["verdict"] == "RED"
        else "YELLOW" if semantic_quality["verdict"] == "YELLOW"
        else "GREEN"
    )
    return {
        "status": "pass" if passed else "fail",
        "passed": passed,
        "repairable": bool(all_errors),
        "issues": issues,
        "warnings": warnings,
        "rejected_candidates": rejected,
        "accepted_candidates": accepted,
        "candidate_count": len(accepted),
        "requested_language": requested_language,
        "exact_quote_checked": bool(exact_quote),
        "required_shorts_tags_checked": False,
        "short_title_contract_checked": True,
        "emoji_context_recommended": emoji_recommended,
        "silent_quote_only_checked": silent_quote_only,
        "final_seo_quality": {**semantic_quality, "verdict": verdict},
        "verdict": verdict,
        "rules_version": "phase2g-v1",
    }


def apply_quality_gate(package: dict[str, Any], gate: dict[str, Any]) -> dict[str, Any]:
    """Apply accepted candidates without manufacturing replacements."""

    cleaned = dict(package)
    accepted = [item["title"] for item in gate.get("accepted_candidates", []) if item.get("title")]
    if accepted:
        cleaned["title"] = accepted[0]
        cleaned["variants"] = accepted
    cleaned["quality_gate"] = gate
    return cleaned


def _title_usefulness_issues(
    title: str,
    source: str,
    brief: dict[str, Any],
    non_instructional: bool,
    competitors: Iterable[str],
    *,
    index: int,
    source_overlap_supported: bool,
) -> list[dict[str, Any]]:
    """Reject valid-looking titles that do not describe this actual video."""

    issues: list[dict[str, Any]] = []
    clean = re.sub(r"(?<![\w#])#shorts(?!\w)", "", normalize_unicode(title), flags=re.IGNORECASE)
    words = _meaningful_words(clean)
    source_words = _source_words(source, brief)
    sparse_source = len(_meaningful_words(source)) <= 2
    if re.search(r"(?i)^\s*(?:how\s+to\s+)?(?:the\s+)?(?:quote\s+)?is\s*[-:]", clean):
        issues.append(_issue("malformed_title_fragment", "title", "Title starts with a creator-input marker instead of natural viewer-facing language.", index=index))
    if re.search(r"(?i)\b(?:used\s+talk\s+every\s+then|quote\s+on\s+(?:the\s+)?(?:reel|screen)|background\s+(?:of\s+the\s+video\s+)?is)\b", clean):
        issues.append(_issue("creator_instruction_leakage", "title", "Title contains parsed input instructions or an unnatural keyword fragment.", index=index))
    if len(words) < 3 and not (sparse_source and words):
        issues.append(_issue("title_too_vague", "title", "Title is too short to identify a useful topic.", index=index))
    if words and words[0] in {"and", "but", "or", "with", "from", "about", "the"}:
        issues.append(_issue("title_fragment", "title", "Title starts like a sentence fragment.", index=index))
    if words and words[-1] in {"and", "but", "or", "with", "from", "about", "to", "for"}:
        issues.append(_issue("title_fragment", "title", "Title ends like a sentence fragment.", index=index))
    if any(term in words and term not in source_words for term in _UNSUPPORTED_CONTEXT_TERMS):
        issues.append(_issue("unsupported_context", "title", "Title adds a context or entity absent from the creator source.", index=index))
    if re.search(r"\b(?:prompt|creator instruction|video concept|without inventing|do not invent)\b", clean, re.IGNORECASE):
        issues.append(_issue("creator_instruction_leakage", "title", "Title exposes internal creator instructions.", index=index))
    if re.search(r"\bthinking out loud\b", clean, re.IGNORECASE) and not re.search(r"\bthinking out loud\b", source, re.IGNORECASE):
        issues.append(_issue("unsupported_action", "title", "Title invents spoken thoughts that are not supplied by the creator.", index=index))
    if re.search(r"\bheavy comfort\b", clean, re.IGNORECASE):
        issues.append(_issue("unnatural_title_phrase", "title", "Title uses an unnatural emotional phrase.", index=index))
    if source_overlap_supported and words and source_words and not ({_quality_root(word) for word in words} & {_quality_root(word) for word in source_words}):
        issues.append(_issue("title_not_source_specific", "title", "Title has no meaningful anchor in the creator source.", index=index))
    for competitor in competitors:
        if title_similarity(clean, competitor) >= 0.94:
            issues.append(_issue("competitor_title_copy", "title", "Title is too close to a researched YouTube result.", index=index))
            break
    if non_instructional and re.search(r"\b(?:how to|tips?|methods?|guide|learn|complete)\b", clean, re.IGNORECASE):
        issues.append(_issue("unsupported_instructional_framing", "title", "Title applies instructional framing unsupported by this source.", index=index))
    return issues


def _description_usefulness_issues(
    description: str,
    source: str,
    brief: dict[str, Any],
    non_instructional: bool,
    *,
    source_overlap_supported: bool,
) -> list[dict[str, Any]]:
    """Require a concise, source-faithful description rather than harmless filler."""

    issues: list[dict[str, Any]] = []
    words = _meaningful_words(description)
    source_words = _source_words(source, brief)
    overlap = set(words) & source_words
    if re.search(
        r"(?i)\b(?:the\s+)?(?:quote|background|visuals?)\s+(?:on\s+(?:the\s+)?(?:reel|screen)\s+)?is\s*[-:]",
        description,
    ):
        issues.append(_issue("creator_instruction_leakage", "description", "Description exposes creator-facing input labels instead of audience-facing copy."))
    if len(words) < 3:
        issues.append(_issue("description_too_thin", "description", "Description does not identify the actual video."))
    if source_overlap_supported and words and source_words and not overlap:
        issues.append(_issue("description_not_source_specific", "description", "Description has no meaningful anchor in the creator source."))
    if any(term in words and term not in source_words for term in _UNSUPPORTED_CONTEXT_TERMS):
        issues.append(_issue("unsupported_context", "description", "Description adds a context or entity absent from the creator source."))
    if re.search(r"\b(?:the (?:creator|speaker) shares|my personal experience|our relationship story)\b", description, re.IGNORECASE):
        source_folded = normalize_unicode(source).casefold()
        if not any(phrase in source_folded for phrase in ("my personal experience", "our relationship", "the speaker", "the creator shares")):
            issues.append(_issue("invented_story_detail", "description", "Description invents a personal story or relationship detail."))
    if any(pattern.search(description) for pattern in _DESCRIPTION_BOILERPLATE) and len(overlap) < 3:
        issues.append(_issue("generic_description_filler", "description", "Description uses generic framing instead of video-specific context."))
    if non_instructional and re.search(r"\b(?:this (?:video|short) (?:teaches|explains|breaks down)|learn how|here are \d+|tips? for)\b", description, re.IGNORECASE):
        issues.append(_issue("unsupported_instructional_framing", "description", "Description claims instruction the source does not provide."))
    return issues


def _tag_provenance_issues(tags: list[str], evidence: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Ensure final tags can be explained without trusting model/result text."""

    if evidence is None:
        return []
    selected = {
        normalize_unicode(item.get("keyword")).casefold(): item
        for item in evidence.get("selected_keywords", [])
        if isinstance(item, dict) and normalize_unicode(item.get("keyword"))
    }
    issues: list[dict[str, Any]] = []
    allowed = {"script_derived", "combined", "research_discovered"}
    for tag in tags:
        row = selected.get(normalize_unicode(tag).casefold())
        if not row:
            issues.append(_issue("missing_tag_provenance", "tags", f"Tag has no deterministic selection provenance: {tag}"))
            continue
        provenance = str(row.get("source_classification") or "")
        if provenance not in allowed:
            issues.append(_issue("invalid_tag_provenance", "tags", f"Tag has unsupported provenance: {tag}"))
        if provenance == "research_discovered" and int(row.get("source_support_score") or 0) < 70:
            issues.append(_issue("weak_research_tag_support", "tags", f"Research-derived tag lacks strong creator-source support: {tag}"))
        if provenance == "combined" and int(row.get("source_support_score") or 0) < 50:
            issues.append(_issue("weak_combined_tag_support", "tags", f"Combined tag lacks sufficient creator-source support: {tag}"))
        if not str(row.get("source_support") or "").strip():
            issues.append(_issue("missing_tag_support", "tags", f"Tag has no recorded source support: {tag}"))
    return issues


def _final_semantic_quality(
    *,
    package: dict[str, Any],
    accepted: list[dict[str, Any]],
    tags: list[str],
    source: str,
    brief: dict[str, Any],
    tag_evidence: dict[str, Any] | None,
    competitors: list[str],
    source_overlap_supported: bool,
) -> dict[str, Any]:
    """Score usefulness separately from structural validity.

    The score is a local quality explanation, not a CTR/ranking prediction.  A
    RED verdict represents a safety/usefulness failure; YELLOW means a usable
    but conservative package with a non-critical limitation.
    """

    title = str((accepted[0] if accepted else {}).get("title") or package.get("title") or "")
    description = normalize_unicode(package.get("description"))
    source_words = _source_words(source, brief)
    title_words = set(_meaningful_words(title))
    description_words = set(_meaningful_words(description))
    source_roots = {_quality_root(word) for word in source_words}
    title_overlap = len({word for word in title_words if _quality_root(word) in source_roots}) / max(len(title_words), 1)
    description_overlap = len({word for word in description_words if _quality_root(word) in source_roots}) / max(min(len(description_words), 12), 1)
    title_score = _bounded_score(
        35 + title_overlap * 45 + (10 if 3 <= len(title_words) <= 12 else 0)
        + (10 if not any(title_similarity(title, item) >= 0.94 for item in competitors) else 0)
    )
    quote = normalize_unicode(brief.get("exact_quote") or brief.get("on_screen_text"))
    direct_quote_title = bool(quote and title_copies_quote(title, quote))
    if direct_quote_title:
        # Faithful is not the same as optimized: repeating the complete on-screen
        # quote gives the viewer no complementary packaging idea.
        title_score = min(title_score, 68.0)
    description_score = _bounded_score(
        35 + min(description_overlap * 55, 45) + (10 if 4 <= len(description_words) <= 120 else 0)
    )
    if not source_overlap_supported:
        # Preserve language checks while avoiding false semantic failures for
        # scripts whose morphology cannot be safely judged by an English-only
        # local lexical matcher.
        title_score = max(title_score, 70.0 if title_words else 0.0)
        description_score = max(description_score, 70.0 if description_words else 0.0)
    if len(source_words) <= 1 and description_words:
        description_score = max(description_score, 60.0)
    tag_keys = {normalize_unicode(tag).casefold() for tag in tags}
    selected_rows = [
        item for item in (tag_evidence or {}).get("selected_keywords", [])
        if isinstance(item, dict) and normalize_unicode(item.get("keyword")).casefold() in tag_keys
    ]
    tag_scores = [float(item.get("keyword_relevance_score") or 0) for item in selected_rows]
    tag_score = round(sum(tag_scores) / len(tag_scores), 1) if tag_scores else None
    title_description_agree = bool(
        {_quality_root(word) for word in title_words} & {_quality_root(word) for word in description_words}
    ) or not title_words or not description_words
    supported_tags = all(int(item.get("source_support_score") or 0) >= 50 for item in selected_rows)
    consistency = title_description_agree and supported_tags
    critical: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if accepted and title_score < 55:
        critical.append(_issue("low_title_usefulness", "title", "Title is too weakly anchored to the supplied source."))
    if description and description_score < 55:
        critical.append(_issue("low_description_usefulness", "description", "Description is too weakly anchored to the supplied source."))
    if not consistency:
        critical.append(_issue("package_consistency_failure", "package", "Title, description, and tags do not agree on the source-supported topic."))
    if tags and tag_score is not None and tag_score < 40:
        warnings.append(_issue("weak_tag_usefulness", "tags", "Final tags are source-safe but have limited search specificity.", severity="warning"))
    if direct_quote_title:
        warnings.append(_issue(
            "title_duplicates_on_screen_quote", "title",
            "Title largely duplicates the on-screen quote instead of adding a complementary hook.",
            severity="warning",
        ))
    rich_quote_context = bool(
        quote
        and normalize_unicode(brief.get("visual_requirements"))
        and normalize_unicode(brief.get("creator_intent"))
    )
    if is_short_content(source, brief) and rich_quote_context and len(tags) < 3:
        warnings.append(_issue(
            "sparse_tag_set", "tags",
            f"Only {len(tags)} useful tag(s) survived; this package needs at least three distinct grounded concepts before it can be rated GREEN.",
            severity="warning",
        ))
    verdict = "RED" if critical else ("YELLOW" if warnings else "GREEN")
    return {
        "title_score": round(title_score, 1),
        "description_score": round(description_score, 1),
        "tag_score": tag_score,
        "tag_count": len(tags),
        "package_consistency": consistency,
        "critical_issues": critical,
        "warnings": warnings,
        "verdict": verdict,
        "policy": "source fidelity + natural language + specificity + grounded search usefulness; not a performance prediction",
    }


def _source_words(source: str, brief: dict[str, Any]) -> set[str]:
    values = [source]
    values.extend(brief.get(field) for field in (
        "content", "topic", "exact_quote", "on_screen_text", "viewer_promise", "unique_angle", "factual_claims",
        "visual_requirements", "creator_intent", "content_constraints",
    ))
    return {word for value in values for word in _meaningful_words(value)}


def _meaningful_words(value: Any) -> list[str]:
    stop = {"a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "how", "i", "in", "is", "it", "my", "of", "on", "or", "our", "that", "the", "this", "to", "was", "we", "with", "you", "your", "shorts"}
    return [word for word in unicode_words(value) if len(word) > 2 and word not in stop]


def _bounded_score(value: float) -> float:
    return max(0.0, min(100.0, value))


def _quality_root(value: str) -> str:
    word = str(value or "").casefold()
    if len(word) > 5 and word.endswith("ing"):
        word = word[:-3]
        if len(word) > 2 and word[-1:] == word[-2:-1]:
            word = word[:-1]
    elif len(word) > 4 and word.endswith("ied"):
        word = word[:-3] + "y"
    elif len(word) > 4 and word.endswith("ed"):
        word = word[:-1] if word[-2:-1] == "e" else word[:-2]
    elif len(word) > 4 and word.endswith("s") and not word.endswith("ss"):
        word = word[:-1]
    return word


def evidence_trace(channel_learning: dict[str, Any] | None) -> dict[str, Any]:
    """Expose only evidence-policy output used for personalization."""

    learning = channel_learning or {}
    cohort = learning.get("cohort") if isinstance(learning.get("cohort"), dict) else {}
    allowed = bool(cohort.get("learning_allowed"))
    return {
        "status": "mature_evidence_used" if allowed else "insufficient_evidence",
        "learning_allowed": allowed,
        "confidence": cohort.get("confidence_label") or learning.get("confidence_label") or "Collecting evidence",
        "sample_size": int(cohort.get("sample_size") or 0),
        "window": cohort.get("snapshot_window") or "24h",
        "evidence_source": "comparable_owned_video_cohort" if allowed else "none",
        "message": (
            "Mature comparable channel evidence was available to the generation prompt."
            if allowed else
            "Insufficient mature comparable evidence; no creator winning pattern was applied."
        ),
    }


def _issue(code: str, field: str, message: str, *, severity: str = "error", index: int | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"code": code, "field": field, "severity": severity, "message": message}
    if index is not None:
        result["candidate_index"] = index
    return result


def _extract_quote(source: str) -> str:
    matches = re.findall(r'["“]([^"“”]{6,})["”]', source)
    if not matches:
        matches = re.findall(r"(?<![A-Za-z])'([^'\n]{6,})'(?![A-Za-z])", source)
    return max((normalize_unicode(item) for item in matches), key=len, default="")


def _unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = " ".join(unicode_words(value))
        if key and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _unsupported_claims(text: str, source_text: str) -> list[str]:
    source = normalize_unicode(source_text).casefold()
    codes = [code for code, pattern in _UNSUPPORTED_CLAIMS if pattern.search(text) and not pattern.search(source)]
    if source_withholds_message_content(source_text) and re.search(
        r"\b(?:exact (?:text|message)|what those words reveal|find out what)\b",
        text,
        re.IGNORECASE,
    ):
        codes.append("invented_message_content")
    return codes


def _looks_like_tag_list(description: str) -> bool:
    lines = [line.strip() for line in description.splitlines() if line.strip()]
    comma_heavy = sum(1 for line in lines if line.count(",") >= 5)
    repeated_phrases = re.findall(r"\b([\w'’]+(?:\s+[\w'’]+){1,3})\b", description.casefold(), re.UNICODE)
    duplicates = len(repeated_phrases) - len(set(repeated_phrases))
    return comma_heavy > 0 or duplicates >= 8


def _has_latin_or_tamil(text: str) -> bool:
    return bool(re.search(r"[A-Za-z\u0B80-\u0BFF]", text))
