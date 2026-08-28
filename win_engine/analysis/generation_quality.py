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
)
_UNSUPPORTED_CLAIMS = (
    ("relationship_event", re.compile(r"\b(?:they|he|she) (?:left|cheated|lied|returned|came back|walked away)\b", re.IGNORECASE)),
    ("invented_outcome", re.compile(r"\b(?:guaranteed|proven to|will make you|will get you|100%|go viral)\b", re.IGNORECASE)),
    ("invented_evidence", re.compile(r"\b(?:studies show|research proves|scientists found|data proves)\b", re.IGNORECASE)),
    ("invented_relationship", re.compile(r"\b(?:breakup|toxic relationship|one-sided relationship|just an option)\b", re.IGNORECASE)),
)
_SHORT_FORMATS = {"short", "shorts", "youtube_shorts", "quote", "reel", "reels"}
_REQUIRED_SHORTS_TAGS = ("shorts",)
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


def normalize_unicode(value: Any) -> str:
    """Return stable printable Unicode without invisible control characters."""

    text = unicodedata.normalize("NFKC", str(value or ""))
    return "".join(
        char for char in text
        if char in "\n\t" or not unicodedata.category(char).startswith("C")
    ).strip()


def unicode_words(value: Any) -> list[str]:
    """Tokenize letters and numbers from every Unicode script."""

    return [
        token.casefold()
        for token in re.findall(r"[^\W_]+(?:['’][^\W_]+)?", normalize_unicode(value), re.UNICODE)
        if len(token) > 1
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
    source = normalize_unicode(script or brief.get("content"))
    return bool(re.search(r"\b(?:youtube\s+shorts?|short[- ]form|shorts?|reels?|quote\s+short)\b", source, re.IGNORECASE))


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
) -> dict[str, Any]:
    """Return a structured, deterministic quality decision for one package."""

    brief = creator_brief or {}
    source = normalize_unicode(script or brief.get("content"))
    source_folded = " ".join(unicode_words(source))
    exact_quote = normalize_unicode(brief.get("exact_quote") or _extract_quote(source))
    is_short = is_short_content(source, brief)
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
            reasons.append(_issue("missing_contextual_title_emoji", "title", "This Short has clear mood or visual context where one relevant emoji should be considered.", index=index))
        signature = "".join(emojis)
        recent_signatures = ["".join(title_emojis(old)) for old in recent[-3:]]
        if signature and len(recent_signatures) == 3 and all(item == signature for item in recent_signatures):
            reasons.append(_issue("repeated_emoji_template", "title", "The emoji pattern repeats across the three most recent generated titles.", index=index))
        if any(pattern.search(title) for pattern in _GENERIC_TITLE_PATTERNS):
            reasons.append(_issue("generic_template", "title", "Title uses a repeatedly generic template.", index=index))
        unsupported = _unsupported_claims(title, source_folded)
        reasons.extend(_issue(code, "title", "Title introduces a claim not supported by the creator source.", index=index) for code in unsupported)
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
        if exact_quote and " ".join(unicode_words(exact_quote)) not in description_folded:
            issues.append(_issue("quote_fidelity", "description", "Description does not preserve the exact on-screen quote."))
        for code in _unsupported_claims(description, source_folded):
            issues.append(_issue(code, "description", "Description introduces a claim not supported by the creator source."))
        if _looks_like_tag_list(description):
            issues.append(_issue("tag_list_contamination", "description", "Description reads like a repeated SEO tag list."))
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
    if is_short and require_shorts_tags:
        missing = [tag for tag in _REQUIRED_SHORTS_TAGS if tag not in tags]
        if missing:
            issues.append(_issue("missing_required_shorts_tags", "tags", "Missing required Shorts tags: " + ", ".join(missing)))
    context_text = " ".join(normalize_unicode(item) for item in tag_context) if isinstance(tag_context, (list, tuple, set)) else normalize_unicode(tag_context)
    source_tokens = set(unicode_words(" ".join([
        source,
        *(normalize_unicode(brief.get(field)) for field in (
            "content", "exact_quote", "on_screen_text", "visual_requirements",
            "viewer_promise", "unique_angle", "topic",
        )),
    ]))) | set(unicode_words(context_text))
    contextual_tags = [
        tag for tag in tags
        if tag not in _GENERIC_FORMAT_TAGS
        and set(unicode_words(tag)) & source_tokens
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
        if tag not in _GENERIC_FORMAT_TAGS and not (set(unicode_words(tag)) & source_tokens):
            issues.append(_issue("unrelated_tag", "tags", f"Tag is not grounded in the supplied topic: {tag}"))

    hashtags = [normalize_unicode(item) for item in (package.get("hashtags") or []) if normalize_unicode(item)]
    normalized_hashtags = [item.casefold().lstrip("#") for item in hashtags]
    if len(normalized_hashtags) != len(set(normalized_hashtags)):
        issues.append(_issue("duplicate_hashtag", "hashtags", "Hashtags contain duplicates."))
    if len(hashtags) > 3:
        issues.append(_issue("excessive_hashtags", "hashtags", "Use no more than three focused hashtags."))

    if not accepted:
        issues.append(_issue("no_acceptable_title", "titles", "No title candidate passed the local quality gate."))
    elif len(accepted) < 3:
        warnings.append(_issue(
            "fewer_legitimate_alternatives",
            "titles",
            f"Only {len(accepted)} materially distinct title alternative(s) passed; the result was not padded.",
            severity="warning",
        ))

    all_errors = [*issues, *(reason for item in rejected for reason in item["issues"])]
    passed = not issues and bool(accepted)
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
        "required_shorts_tags_checked": is_short and require_shorts_tags,
        "short_title_contract_checked": True,
        "emoji_context_recommended": emoji_recommended,
        "rules_version": "phase2b-v1",
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


def _unsupported_claims(text: str, source_folded: str) -> list[str]:
    source = normalize_unicode(source_folded).casefold()
    return [code for code, pattern in _UNSUPPORTED_CLAIMS if pattern.search(text) and not pattern.search(source)]


def _looks_like_tag_list(description: str) -> bool:
    lines = [line.strip() for line in description.splitlines() if line.strip()]
    comma_heavy = sum(1 for line in lines if line.count(",") >= 5)
    repeated_phrases = re.findall(r"\b([\w'’]+(?:\s+[\w'’]+){1,3})\b", description.casefold(), re.UNICODE)
    duplicates = len(repeated_phrases) - len(set(repeated_phrases))
    return comma_heavy > 0 or duplicates >= 8


def _has_latin_or_tamil(text: str) -> bool:
    return bool(re.search(r"[A-Za-z\u0B80-\u0BFF]", text))
