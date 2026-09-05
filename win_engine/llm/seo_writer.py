"""SEO writer for YouTube Studio.

Generates title, 5 variants, description, tags, and hashtags from a video
script + competitor context. Language-aware and auto-detects content type
(Vlogs, Gaming, Quotes, Shorts, Music, Tutorials, etc.).
"""

from __future__ import annotations

import json
import logging
import re
from contextvars import ContextVar
from difflib import SequenceMatcher
from typing import Any, Optional, Union

from win_engine.analysis.generation_quality import (
    apply_quality_gate,
    evaluate_package_quality,
    is_short_content,
    is_silent_quote_only_short,
    source_requires_noninstructional_framing,
    source_withholds_message_content,
)
from win_engine.llm import gemini_client

logger = logging.getLogger(__name__)
_LAST_LANGUAGE_DIAGNOSTICS: ContextVar[dict[str, dict[str, Any]]] = ContextVar(
    "seo_writer_language_diagnostics", default={}
)

Competitor = Union[str, dict]


def last_generation_diagnostics() -> dict[str, dict[str, Any]]:
    """Return safe per-language diagnostics from the last writer invocation."""
    return {language: dict(trace) for language, trace in _LAST_LANGUAGE_DIAGNOSTICS.get().items()}


def _provider_summary(*traces: dict[str, Any], logical_calls: int) -> dict[str, Any]:
    """Aggregate bounded provider diagnostics without retaining prompts or secrets."""
    valid = [trace for trace in traces if trace]
    retry_reasons = list(dict.fromkeys(
        str(reason) for trace in valid for reason in (trace.get("retry_reasons") or []) if reason
    ))
    categories = [str(trace.get("failure_category")) for trace in valid if trace.get("failure_category")]
    return {
        "gemini_attempted": bool(logical_calls),
        "gemini_call_count": logical_calls,
        "provider_requests": logical_calls,
        "provider_attempts": sum(int(trace.get("attempts") or 0) for trace in valid),
        "retry_count": sum(int(trace.get("retries") or 0) for trace in valid),
        "provider_retries": sum(int(trace.get("retries") or 0) for trace in valid),
        "retry_reasons": retry_reasons,
        "provider_failure_category": categories[-1] if categories else None,
    }


def _quality_rejection_summary(gate: dict[str, Any]) -> dict[str, Any]:
    """Retain safe, bounded rejection evidence so repair failures are diagnosable."""

    issues = [
        {"code": str(item.get("code") or "quality_failure"), "field": str(item.get("field") or "package"),
         "message": str(item.get("message") or "")[:240]}
        for item in (gate.get("issues") or [])[:12]
        if isinstance(item, dict)
    ]
    rejected_titles = []
    for candidate in (gate.get("rejected_candidates") or [])[:5]:
        if not isinstance(candidate, dict):
            continue
        rejected_titles.append({
            "title": str(candidate.get("title") or "")[:120],
            "codes": [str(item.get("code") or "quality_failure") for item in (candidate.get("issues") or [])[:8] if isinstance(item, dict)],
        })
    return {"status": str(gate.get("status") or "fail"), "issues": issues, "rejected_titles": rejected_titles}

_SYSTEM_PROMPT = (
    "You are an expert YouTube SEO strategist. You analyze the user's video script, quote, or idea "
    "to write high-CTR title variants, descriptions, tags, and hashtags. "
    "Output ONLY valid JSON with keys: \"title\", \"variants\" (array of 5 strings), "
    "\"description\", \"tags\" (array of up to 10 contextual strings), and \"hashtags\" (array of up to 3 strings). "
    "Every title must be an exact, upload-ready value rather than a stem or template."
)


_LANGUAGE_INSTRUCTIONS = {
    "english": (
        "Write title, variants, and description in natural conversational English. "
        "Tags stay English. Hashtags stay English."
    ),
    "tamil": (
        "Write title, variants, and description in spoken Tamil using Tamil script. "
        "Use natural Tamil creator voice — not literal translation. Tamil words "
        "for emotion and curiosity. Tags stay English (YouTube search needs them). "
        "Hashtags stay English."
    ),
    "tanglish": (
        "Write title, variants, and description in Tanglish — Tamil words written "
        "in English Roman letters mixed naturally with English. Use real creator "
        "phrasing like 'da', 'macha', 'semma', 'vera level', 'illa', 'ah' where "
        "they fit naturally. Do not force them. Tags stay English. Hashtags stay English."
    ),
    "hindi": (
        "Write title, variants, and description in Hinglish (Hindi-English mix in "
        "Roman script). Natural Indian creator voice. Tags stay English."
    ),
}

_LANGUAGE_ALIASES = {
    "hinglish_or_hindi": "hindi",
    "hinglish": "hindi",
    "spanish_like": "english",
}

_NICHE_GUIDANCE = {
    "gaming": (
        "Niche: GAMING. Lead with the game name and the stakes (win/clutch/rank/"
        "loot). Energetic, fast, FOMO-driven. Numbers and 'how I' framing work well."
    ),
    "education": (
        "Niche: EDUCATION. Lead with the concept and the outcome ('understand X', "
        "'pass Y'). Clear, credible, promise-of-clarity voice. Avoid hype words."
    ),
    "finance": (
        "Niche: FINANCE. Lead with the money outcome and a concrete number/timeframe. "
        "Trustworthy, specific, no get-rich-quick scam phrasing."
    ),
    "tech": (
        "Niche: TECH/REVIEW. Lead with the product/tool and the verdict or use-case. "
        "Honest, specific, benefit-led. 'worth it?' and comparison framing work well."
    ),
    "fitness": (
        "Niche: FITNESS. Lead with the body/goal and a realistic result + timeframe. "
        "Motivating but honest; avoid miracle claims."
    ),
    "cooking": (
        "Niche: COOKING. Lead with the dish and the hook (easy/quick/authentic/"
        "secret ingredient). Appetite-driven, sensory voice."
    ),
    "vlog": (
        "Niche: VLOG/LIFESTYLE. Lead with the relatable moment or transformation. "
        "Warm, personal, first-person voice. Curiosity over keywords, but keep it "
        "searchable."
    ),
    "quotes": (
        "Niche: QUOTE SHORT. Package the exact emotional idea without inventing a "
        "breakup, betrayal, departure, motive, or relationship event. Prefer one "
        "natural search phrase and one honest emotional hook over generic 'deep "
        "quote' wording. Keep the description concise and faithful to the on-screen text."
    ),
    "shorts": (
        "Niche: YOUTUBE SHORT. Use a concise, truthful hook that matches the visible "
        "content. Do not pad the package with generic viral claims."
    ),
    "youtube_shorts": (
        "Niche: YOUTUBE SHORT. Use a concise, truthful hook that matches the visible "
        "content. Do not pad the package with generic viral claims."
    ),
    "general": (
        "Niche: GENERAL. Lead with the clearest specific promise. Natural, "
        "human creator voice; avoid generic filler."
    ),
}

def _language_instruction(language: str) -> str:
    key = (language or "english").lower()
    key = _LANGUAGE_ALIASES.get(key, key)
    return _LANGUAGE_INSTRUCTIONS.get(key, _LANGUAGE_INSTRUCTIONS["english"])


def _niche_header(category: Optional[str]) -> str:
    return _NICHE_GUIDANCE.get((category or "general").lower(), _NICHE_GUIDANCE["general"])


def _fmt_views(value: Any) -> str:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return ""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M views"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K views"
    return f"{n} views"


def _engagement_label(entry: dict) -> str:
    """Like/comment rates relative to views — signal for WHY a title won."""
    try:
        views = int(entry.get("views") or 0)
    except (TypeError, ValueError):
        views = 0
    if views <= 0:
        return ""
    parts: list[str] = []
    try:
        likes = int(entry.get("likes") or 0)
        if likes:
            parts.append(f"{(likes / views) * 100:.1f}% like rate")
    except (TypeError, ValueError):
        pass
    try:
        comments = int(entry.get("comments") or 0)
        if comments:
            parts.append(f"{(comments / views) * 1000:.1f} comments/1k")
    except (TypeError, ValueError):
        pass
    return ", ".join(parts)


def _build_competitor_block(competitors: Optional[list[Competitor]]) -> str:
    if not competitors:
        return ""
    lines: list[str] = []
    for entry in competitors[:8]:
        if isinstance(entry, dict):
            title = (entry.get("title") or "").strip()
            if not title:
                continue
            meta_bits = [b for b in (_fmt_views(entry.get("views")), _engagement_label(entry)) if b]
            meta = f" ({' · '.join(meta_bits)})" if meta_bits else ""
            lines.append(f"- {title}{meta}")
        elif isinstance(entry, str) and entry.strip():
            lines.append(f"- {entry.strip()}")
    if not lines:
        return ""
    return (
        "\nTop-performing competitor videos in this niche (titles + engagement, for "
        "tone/structure reference — note which framing drives likes & comments, do NOT "
        "copy verbatim):\n" + "\n".join(lines) + "\n"
    )


def _build_creator_brief_block(creator_brief: Optional[dict[str, Any]]) -> str:
    """Format creator context so the model packages the real video, not a generic topic."""
    if not creator_brief:
        return ""

    fields = [
        ("Topic", creator_brief.get("topic")),
        ("Target viewer", creator_brief.get("target_audience")),
        ("Viewer promise", creator_brief.get("viewer_promise")),
        ("Unique angle", creator_brief.get("unique_angle")),
        ("Proof or real footage", creator_brief.get("proof")),
        ("Video format", creator_brief.get("video_format")),
        ("Preferred title style", creator_brief.get("title_style")),
        ("Thumbnail direction", creator_brief.get("thumbnail_idea")),
        ("Exact quote", creator_brief.get("exact_quote")),
        ("On-screen text", creator_brief.get("on_screen_text")),
        ("Voice-over", creator_brief.get("voice_over")),
        ("Visual requirements", creator_brief.get("visual_requirements")),
        ("Factual claims supplied", creator_brief.get("factual_claims")),
        ("Claim restrictions", creator_brief.get("claim_restrictions")),
        ("Creator intent", creator_brief.get("creator_intent")),
        ("Content constraints", creator_brief.get("content_constraints")),
        ("Research-backed SEO targets", ", ".join(str(item) for item in (creator_brief.get("seo_research_targets") or []) if str(item).strip())),
    ]
    lines = [f"- {label}: {str(value).strip()}" for label, value in fields if value and str(value).strip()]
    if not lines:
        return ""
    return "\nCreator brief (source of truth for audience and promise):\n" + "\n".join(lines) + "\n"


def _build_channel_learning_block(channel_learning: Optional[dict[str, Any]]) -> str:
    """Format only policy-approved evidence, plus recent-title anti-repetition context."""
    if not channel_learning:
        return ""
    lines: list[str] = []
    confidence = str(channel_learning.get("confidence") or "collecting")
    cohort = channel_learning.get("cohort") or {}
    learning_allowed = isinstance(cohort, dict) and bool(cohort.get("learning_allowed"))
    best_videos = channel_learning.get("best_videos") or []
    if learning_allowed:
        for v in best_videos[:3]:
            t = (v.get("title") or "").strip()
            views = v.get("views")
            retention = v.get("average_view_percentage")
            if t:
                details = [f"{int(views):,} views" if views is not None else ""]
                if retention is not None:
                    details.append(f"{float(retention):.1f}% average viewed")
                details = [detail for detail in details if detail]
                label = str(channel_learning.get("confidence_label") or confidence.replace("_", " ").title())
                lines.append(f"- {label} linked-video pattern: \"{t}\" ({', '.join(details)})")
                actual_tags = [str(tag).strip() for tag in (v.get("actual_tags") or []) if str(tag).strip()]
                if actual_tags:
                    lines.append(f"  Actual uploaded tags: {', '.join(actual_tags[:6])}")
    rec = channel_learning.get("recommendation")
    if learning_allowed and rec and str(rec).strip():
        lines.append(f"- Channel Insight: {str(rec).strip()}")
    if confidence == "collecting" and channel_learning.get("linked_video_count"):
        lines.append(
            f"- Only {channel_learning.get('sample_size', 0)} linked videos have a mature 24-hour snapshot; "
            "do not imitate or reject a title pattern from this small sample yet."
        )
    recent_titles = channel_learning.get("recent_titles") or []
    if recent_titles:
        lines.append("- Avoid repeating these recent generated titles or their sentence patterns:")
        lines.extend(f"  - {str(title).strip()}" for title in recent_titles[:10] if str(title).strip())
    if isinstance(cohort, dict) and cohort.get("sample_size"):
        lines.append(
            f"- Personal evidence: {cohort.get('confidence_label', 'Collecting evidence')}; "
            f"sample size {cohort.get('sample_size')}."
        )
    if not lines:
        return ""
    return "\nChannel learning signals (past performance on this channel):\n" + "\n".join(lines) + "\n"


def _build_user_prompt(
    script: str,
    competitor_block: str,
    language: str,
    region: str,
    audience_type: str,
    category: Optional[str] = None,
    creator_brief: Optional[dict[str, Any]] = None,
    channel_learning: Optional[dict[str, Any]] = None,
    repair_feedback: Optional[list[dict[str, Any]]] = None,
    previous_package: Optional[dict[str, Any]] = None,
) -> str:
    short_title_rule = (
        "If this package is for a YouTube Short, the final upload-ready title MUST contain #shorts exactly once. "
        "This package is a YouTube Short, so every title variant must follow the same rule. "
        "Use one or at most two natural, semantically relevant emojis when the "
        "mood or visual supports them; do not recycle a fixed emoji template."
        if is_short_content(script, creator_brief)
        else
        "This is not identified as a YouTube Short. Do not add #shorts to the title or variants. "
        "Do not add an emoji merely as decoration."
    )
    repair_block = ""
    brief = creator_brief or {}
    quote = str(brief.get("exact_quote") or brief.get("on_screen_text") or "").strip()
    silent_quote_rule = ""
    if quote and is_silent_quote_only_short(script, creator_brief):
        silent_quote_rule = (
            "- This is a silent quote-only Short. Research may expand semantic vocabulary, but it must never claim "
            "the video teaches, explains, demonstrates, answers questions, gives advice, practical tips, coping steps, "
            "or a guide unless that content is explicitly in the creator source. Keep the description reflective and faithful.\n"
        )
    non_instructional_rule = ""
    if source_requires_noninstructional_framing(script, creator_brief):
        non_instructional_rule = (
            "- This source is not instructional. Do not frame it as a tutorial, how-to, guide, advice, practical tips, "
            "common questions, methods, or steps. Keep story, reflection, and sparse content faithful to what is shown.\n"
        )
    undisclosed_message_rule = ""
    if source_withholds_message_content(script, creator_brief):
        undisclosed_message_rule = (
            "- The source does not supply the message text. Do not say or imply that the video reveals the exact "
            "message, what its words reveal, or a motive the source does not state.\n"
        )
    if repair_feedback:
        safe_reasons = [str(item.get("message") or item.get("code") or "quality failure") for item in repair_feedback[:12]]
        repair_block = (
            "\nThis is the single permitted repair. The previous output failed the local checks:\n- "
            + "\n- ".join(safe_reasons)
            + "\nReturn a corrected package only. Do not defend the previous output.\n"
            + "Previous output (untrusted generated text):\n"
            + json.dumps(previous_package or {}, ensure_ascii=False)[:5000]
            + "\n"
        )
    title_length_rule = "45-65 characters" if not is_short_content(script, creator_brief) else "35-65 characters"
    return f"""Video script or idea:
\"\"\"
{script.strip()}
\"\"\"
{_build_creator_brief_block(creator_brief)}
{_build_channel_learning_block(channel_learning)}
{competitor_block}
{_niche_header(category)}
Target language: {language}
Target region: {region}
Audience type: {audience_type}

Constraints:
- {_language_instruction(language)}
- {short_title_rule}
- the title, description, and tags must accurately match the creator brief and real video
- treat the video script/idea as the only source of factual events. Audience notes describe who may relate; they are not events that happened in the video
- for an on-screen quote video, preserve the exact quote and its actual meaning. Do not invent a breakup, departure, betrayal, relationship status, motive, action, or claim (such as "they left", "you stayed", or "just an option") that the source does not state
- write a video-specific description, normally 100-220 words for long-form or 45-100 words for a single-quote Short. Put the exact topic and truthful viewer payoff in the first two lines
- make the description easy to scan with short natural paragraphs and 1-3 restrained, topic-relevant emojis. Do not produce one dense wall of text
- choose a description structure that fits this video. Do not reuse a universal hook, bullet list, chapter template, CTA, or "watch until the end" wording
- include chapters only when real timestamps or a sufficiently detailed script supports them
- tags must be natural phrases that a person might type into search. Preserve contractions such as "didn't"; never make a tag by deleting grammar words from a quote, and never return a bag of unrelated quote words
- research-backed SEO targets are candidates, not mandatory tags. Do not copy a title, exact quote, or competitor title into tags; use only targets that accurately describe the video
- tags must be atomic search concepts: one natural topic, intent, entity, or useful long-tail phrase per tag. Never glue separate concepts into one tag, such as "heartbreak loneliness emotional rejection healing". Do not include #shorts, shorts, yt, youtube shorts, viral shorts, hashtags, generic mood words, or visual footage terms unless the creator explicitly says viewers search for that visual subject
- tags must come from the actual topic, named entities, exact phrases, useful spelling variants, and language transliterations. Return only tags justified by this specific video; do not pad the list to a fixed count and do not add generic viral/trending filler
- a researched YouTube title or result phrase is evidence only, never text to copy into a title, description, or tag. Research may improve wording for the same source-supported subject, but may not introduce a new situation, entity, relationship, product, lesson, or claim
- a package that is merely valid is not enough: prefer a short, natural, source-faithful result over a generic, keyword-stuffed, or invented one
- research may inform topic vocabulary, but it cannot invent what the video teaches, explains, demonstrates, or advises
- do not infer a time of day, darkness, empty streets, weather, spoken narration, peace, comfort, or healing unless the creator source explicitly supplies it
{silent_quote_rule}{non_instructional_rule}{undisclosed_message_rule}- title: {title_length_rule}, engaging, and matched to the actual content category
- return exactly five distinct variants. Variant 1 is SEARCH (natural topic phrase), variant 2 is BROWSE (truthful curiosity or emotion), and variant 3 is EXISTING AUDIENCE only when the source or channel evidence supports a personal proof/story; otherwise use a faithful resonance angle. Variants 4-5 are additional truthful alternatives
- each variant must use a materially different opening, sentence structure, and psychological angle. Avoid stock openings such as "A quiet reminder", "The painful reality", and repeated "When you realize" templates. Do not repeat recent-title patterns supplied above
- use idiomatic phrases such as "one-sided effort"; never write unnatural phrases such as "unrequited effort" or "fractions of effort"
- thumbnail text must add a short new idea; it must not merely repeat the title. Never use false guarantees, unrelated trends, or misleading claims.
{repair_block}
"""


def _extract_json(raw: str) -> Optional[dict[str, Any]]:
    """Pull the first JSON object out of model output."""
    if not raw:
        return None
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        logger.warning("Gemini returned malformed JSON: %s", exc)
        return None


def _validate(pkg: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Shape-check + light coercion. Returns None on missing required fields."""
    try:
        title = str(pkg["title"]).strip()
        variants = _unique_text([str(v).strip() for v in pkg["variants"] if str(v).strip()])
        description = str(pkg["description"]).strip()
        tags = _unique_text([str(t).strip().lower().lstrip("#") for t in pkg["tags"] if str(t).strip()])
        hashtags = _unique_text([str(h).strip() for h in pkg["hashtags"] if str(h).strip()])
    except (KeyError, TypeError, AttributeError):
        return None
    # A sparse source may honestly have no defensible search tag. The final
    # deterministic selector decides whether any tag survives; do not force
    # generic filler merely to satisfy a shape check.
    if not title or not description or not variants:
        return None
    hashtags = [h if h.startswith("#") else f"#{h}" for h in hashtags]
    return {
        "title": title,
        "variants": variants[:5],
        "description": description,
        "tags": tags[:10],
        "hashtags": hashtags[:3],
    }


_PHRASE_REPLACEMENTS = {
    "unrequited effort": "one-sided effort",
    "fractions of effort": "very little effort",
    "a fraction of effort": "very little effort",
    "one-sided connection": "one-sided relationship",
}

_UNSUPPORTED_QUOTE_CLAIMS = (
    (r"\bthey (?:left|walked away|came back|cheated|lied)\b", r"\b(?:left|walked away|came back|cheated|lied)\b"),
    (r"\byou (?:stayed|accepted)\b", r"\b(?:stayed|accepted)\b"),
    (r"\bstaying in\b", r"\bstay(?:ed|ing)?\b"),
    (r"\b(?:breakup|toxic relationship|just an option)\b", r"\b(?:breakup|toxic|option)\b"),
)


def _naturalize_generated_text(value: str) -> str:
    text = value
    for unnatural, natural in _PHRASE_REPLACEMENTS.items():
        def _replacement(match: re.Match[str], replacement: str = natural) -> str:
            return replacement.capitalize() if match.group(0)[:1].isupper() else replacement

        text = re.sub(re.escape(unnatural), _replacement, text, flags=re.IGNORECASE)
    return re.sub(r"[ \t]+", " ", text).strip()


def _extract_on_screen_quote(script: str) -> str:
    matches = re.findall(r'["“]([^"“”]{12,})["”]', script or "")
    if not matches:
        matches = re.findall(r"(?<![A-Za-z])'([^'\n]{12,})'(?![A-Za-z])", script or "")
    return max((re.sub(r"\s+", " ", item).strip() for item in matches), key=len, default="")


def _has_unsupported_quote_claim(text: str, source: str) -> bool:
    lowered_source = source.casefold()
    return any(
        re.search(claim, text, flags=re.IGNORECASE)
        and not re.search(evidence, lowered_source, flags=re.IGNORECASE)
        for claim, evidence in _UNSUPPORTED_QUOTE_CLAIMS
    )


def _remove_unsupported_description_sentences(description: str, source: str) -> str:
    paragraphs: list[str] = []
    for paragraph in re.split(r"\n\s*\n", description):
        sentences = re.split(r"(?<=[.!?])\s+", paragraph.strip())
        kept = [sentence for sentence in sentences if sentence and not _has_unsupported_quote_claim(sentence, source)]
        if kept:
            paragraphs.append(" ".join(kept))
    return "\n\n".join(paragraphs).strip()


def _safe_quote_title(quote: str) -> str:
    is_question = "?" in quote
    clauses = [part.strip(" .,:;!?—–-") for part in re.split(r"\.{2,}|[;—–]", quote) if part.strip()]
    focus = clauses[-1] if clauses else quote
    focus = focus[:1].upper() + focus[1:]
    suffix = " #Shorts"
    if len(focus) + len(suffix) <= 70:
        return focus.rstrip(".!?") + ("?" if is_question else "") + suffix
    words: list[str] = []
    for word in focus.split():
        if len(" ".join([*words, word])) > 58:
            break
        words.append(word)
    return " ".join(words).rstrip(".,;:!?") + "… #Shorts"


def _sanitize_generated_package(
    pkg: dict[str, Any], script: str, creator_brief: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Apply deterministic fidelity checks after generation, especially for quote Shorts."""
    cleaned = dict(pkg)
    quote = str((creator_brief or {}).get("exact_quote") or (creator_brief or {}).get("on_screen_text") or "").strip()
    quote = quote or _extract_on_screen_quote(script)
    description = _naturalize_generated_text(str(cleaned.get("description") or ""))
    if quote:
        description = _remove_unsupported_description_sentences(description, script)
        if not description:
            description = f'“{quote}”\n\nA quiet reflection for anyone who connects with these words.'
        elif re.sub(r"\s+", " ", quote).strip() not in re.sub(r"\s+", " ", description).strip():
            paragraphs = [item.strip() for item in re.split(r"\n\s*\n", description) if item.strip()]
            quote_words = set(re.findall(r"[\w’']+", quote.casefold(), re.UNICODE))
            if paragraphs:
                first_words = set(re.findall(r"[\w’']+", paragraphs[0].casefold(), re.UNICODE))
                if quote_words and len(quote_words & first_words) / len(quote_words) >= 0.8:
                    paragraphs[0] = f'“{quote}”'
                else:
                    paragraphs.insert(0, f'“{quote}”')
            else:
                paragraphs = [f'“{quote}”']
            description = "\n\n".join(paragraphs)
    cleaned["description"] = description

    titles = [str(cleaned.get("title") or ""), *(cleaned.get("variants") or [])]
    safe_titles: list[str] = []
    for raw_title in titles:
        title = _naturalize_generated_text(raw_title)
        if not title or (quote and _has_unsupported_quote_claim(title, script)):
            continue
        if any(_title_similarity(title, existing) >= 0.90 for existing in safe_titles):
            continue
        safe_titles.append(title)
    if not safe_titles and quote:
        safe_titles = [_safe_quote_title(quote)]
    if safe_titles:
        cleaned["title"] = safe_titles[0]
        cleaned["variants"] = safe_titles[:5]
    return cleaned


def _unique_text(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = re.sub(r"\s+", " ", value).strip().casefold()
        if key and key not in seen:
            seen.add(key)
            out.append(value.strip())
    return out


def _title_similarity(left: str, right: str) -> float:
    a = re.sub(r"[\W_]+", " ", left.casefold(), flags=re.UNICODE)
    b = re.sub(r"[\W_]+", " ", right.casefold(), flags=re.UNICODE)
    return SequenceMatcher(None, " ".join(a.split()), " ".join(b.split())).ratio()


def _prefer_fresh_titles(pkg: dict[str, Any], channel_learning: Optional[dict[str, Any]]) -> dict[str, Any]:
    recent = [str(item).strip() for item in (channel_learning or {}).get("recent_titles", []) if str(item).strip()]
    candidates = _unique_text([str(pkg.get("title") or ""), *(pkg.get("variants") or [])])
    fresh = [title for title in candidates if not any(_title_similarity(title, old) >= 0.86 for old in recent)]
    ordered = fresh + [title for title in candidates if title not in fresh]
    if ordered:
        pkg["title"] = ordered[0]
        pkg["variants"] = _unique_text(ordered)[:5]
    return pkg


def _generate_one(
    script: str,
    competitors: Optional[list[Competitor]],
    *,
    language: str,
    region: str,
    audience_type: str,
    category: Optional[str],
    creator_brief: Optional[dict[str, Any]],
    channel_learning: Optional[dict[str, Any]] = None,
    temperature: float,
    max_tokens: int,
    repair_feedback: Optional[list[dict[str, Any]]] = None,
    previous_package: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    """Generate and validate one SEO package with Gemini."""
    prompt = _build_user_prompt(
        script=script,
        competitor_block=_build_competitor_block(competitors),
        language=(language or "english"),
        region=(region or "global"),
        audience_type=(audience_type or "general"),
        category=category,
        creator_brief=creator_brief,
        channel_learning=channel_learning,
        repair_feedback=repair_feedback,
        previous_package=previous_package,
    )
    raw = gemini_client.generate(
        prompt=prompt,
        system=_SYSTEM_PROMPT,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    provider_trace = gemini_client.last_generation_diagnostic()
    if not raw:
        return None
    parsed = _extract_json(raw)
    if parsed is None:
        logger.warning("Gemini response was rejected because it did not contain a usable JSON package.")
        provider_trace["status"] = "gemini_invalid_response"
        provider_trace["failure_category"] = "malformed_provider_response"
        gemini_client.set_last_generation_diagnostic(provider_trace)
        _LAST_LANGUAGE_DIAGNOSTICS.set({language: provider_trace})
        return None
    validated = _validate(parsed)
    if not validated:
        logger.warning("Gemini response was rejected because required package fields were missing or invalid.")
        provider_trace["status"] = "gemini_invalid_response"
        provider_trace["failure_category"] = "malformed_provider_response"
        gemini_client.set_last_generation_diagnostic(provider_trace)
        _LAST_LANGUAGE_DIAGNOSTICS.set({language: provider_trace})
        return None
    sanitized = _sanitize_generated_package(validated, script, creator_brief)
    cleaned = _prefer_fresh_titles(sanitized, channel_learning)
    cleaned["_provider_trace"] = provider_trace
    _LAST_LANGUAGE_DIAGNOSTICS.set({language: provider_trace})
    return cleaned


def write_seo_package(
    script: str,
    competitors: Optional[list[Competitor]] = None,
    *,
    language: str = "english",
    region: str = "global",
    audience_type: str = "general",
    category: Optional[str] = None,
    creator_brief: Optional[dict[str, Any]] = None,
    channel_learning: Optional[dict[str, Any]] = None,
    temperature: float = 0.75,
    max_tokens: int = 1200,
) -> Optional[dict[str, Any]]:
    """Generate a full SEO package with Gemini, or return ``None`` when unavailable."""
    if not script or not script.strip():
        return None
    if not gemini_client.is_available():
        return None
    return _generate_one(
        script,
        competitors,
        language=language,
        region=region,
        audience_type=audience_type,
        category=category,
        creator_brief=creator_brief,
        channel_learning=channel_learning,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def write_multilang_packages(
    script: str,
    competitors: Optional[list[Competitor]] = None,
    *,
    languages: Optional[list[str]] = None,
    region: str = "global",
    audience_type: str = "general",
    category: Optional[str] = None,
    creator_brief: Optional[dict[str, Any]] = None,
    channel_learning: Optional[dict[str, Any]] = None,
    temperature: float = 0.75,
    max_tokens: int = 1200,
) -> dict[str, Optional[dict[str, Any]]]:
    packages, _ = write_multilang_packages_with_source(
        script,
        competitors,
        languages=languages,
        region=region,
        audience_type=audience_type,
        category=category,
        creator_brief=creator_brief,
        channel_learning=channel_learning,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return packages


def write_multilang_packages_with_source(
    script: str,
    competitors: Optional[list[Competitor]] = None,
    *,
    languages: Optional[list[str]] = None,
    region: str = "global",
    audience_type: str = "general",
    category: Optional[str] = None,
    creator_brief: Optional[dict[str, Any]] = None,
    channel_learning: Optional[dict[str, Any]] = None,
    temperature: float = 0.75,
    max_tokens: int = 1200,
) -> tuple[dict[str, Optional[dict[str, Any]]], str]:
    """Generate SEO packages for several languages in one pass.

    Uses Gemini for every requested language. Returns ``gemini`` or ``fallback``.
    """
    langs = [l.lower() for l in (languages or ["english", "tamil", "tanglish"])]
    if not script or not script.strip():
        return {lang: None for lang in langs}, "fallback"

    out: dict[str, Optional[dict[str, Any]]] = {}
    language_diagnostics: dict[str, dict[str, Any]] = {}
    gemini_ready = gemini_client.is_available()
    for lang in langs:
        first = _generate_one(
            script,
            competitors,
            language=lang,
            region=region,
            audience_type=audience_type,
            category=category,
            creator_brief=creator_brief,
            channel_learning=channel_learning,
            temperature=temperature,
            max_tokens=max_tokens,
        ) if gemini_ready else None
        first_trace = dict((first or {}).pop("_provider_trace", {}) or (
            gemini_client.last_generation_diagnostic() if gemini_ready else {
                "status": "gemini_unavailable", "failure_category": "authentication_or_configuration",
                "attempts": 0, "retries": 0, "retry_reasons": [],
            }
        ))
        if first is None:
            language_diagnostics[lang] = {
                **first_trace,
                **_provider_summary(first_trace, logical_calls=1 if gemini_ready else 0),
                "fallback_used": True,
                "fallback_level": "deterministic",
            }
            out[lang] = None
            continue
        gate = evaluate_package_quality(
            first,
            script=script,
            creator_brief=creator_brief,
            language=lang,
            recent_titles=(channel_learning or {}).get("recent_titles") or [],
            published_titles=(channel_learning or {}).get("published_titles") or [],
            require_shorts_tags=False,
            competitor_titles=[str(item.get("title") or "") for item in (competitors or []) if isinstance(item, dict)],
            enforce_final_tag_rules=False,
        )
        first = apply_quality_gate(first, gate)
        first["generation_trace"] = {
            **_provider_summary(first_trace, logical_calls=1),
            "repair_attempted": False, "repair_succeeded": False,
            "initial_quality_status": gate["status"], "events": [str(first_trace.get("status") or "gemini_success")],
            **first_trace,
        }
        if gate["passed"] or not gate["repairable"]:
            language_diagnostics[lang] = dict(first["generation_trace"])
            out[lang] = first
            continue
        first["generation_trace"]["events"].append("gemini_quality_rejection")
        first["generation_trace"]["initial_quality_rejection"] = _quality_rejection_summary(gate)
        repair_reasons = [*gate.get("issues", [])]
        repair_reasons.extend(reason for item in gate.get("rejected_candidates", []) for reason in item.get("issues", []))
        repaired = _generate_one(
            script, competitors, language=lang, region=region, audience_type=audience_type,
            category=category, creator_brief=creator_brief, channel_learning=channel_learning,
            temperature=temperature, max_tokens=max_tokens, repair_feedback=repair_reasons,
            previous_package=first,
        )
        repaired_trace = dict((repaired or {}).pop("_provider_trace", {}) or gemini_client.last_generation_diagnostic())
        if repaired is None:
            language_diagnostics[lang] = {
                **repaired_trace, **_provider_summary(first_trace, repaired_trace, logical_calls=2), "repair_attempted": True,
                "repair_succeeded": False, "initial_quality_status": gate["status"],
                "final_quality_status": "invalid_response",
                "initial_quality_rejection": _quality_rejection_summary(gate),
                "events": [str(first_trace.get("status") or "gemini_success"), "gemini_quality_rejection",
                           str(repaired_trace.get("status") or "gemini_validator_rejection"), "fallback_used"],
                "fallback_used": True,
                "fallback_reason": "gemini_invalid_repair_response",
                "fallback_level": "deterministic",
            }
            out[lang] = None
            continue
        repaired_gate = evaluate_package_quality(
            repaired, script=script, creator_brief=creator_brief, language=lang,
            recent_titles=(channel_learning or {}).get("recent_titles") or [],
            published_titles=(channel_learning or {}).get("published_titles") or [],
            require_shorts_tags=False,
            competitor_titles=[str(item.get("title") or "") for item in (competitors or []) if isinstance(item, dict)],
            enforce_final_tag_rules=False,
        )
        repaired = apply_quality_gate(repaired, repaired_gate)
        repaired["generation_trace"] = {
            **_provider_summary(first_trace, repaired_trace, logical_calls=2),
            "status": str(repaired_trace.get("status") or "gemini_success"), "repair_attempted": True,
            "repair_succeeded": bool(repaired_gate["passed"]),
            "initial_quality_status": gate["status"], "final_quality_status": repaired_gate["status"],
            "initial_quality_rejection": _quality_rejection_summary(gate),
            "repair_quality_rejection": _quality_rejection_summary(repaired_gate) if not repaired_gate["passed"] else None,
            "events": [str(first_trace.get("status") or "gemini_success"), "gemini_quality_rejection",
                       str(repaired_trace.get("status") or "gemini_success"),
                       "gemini_repair_success" if repaired_gate["passed"] else "gemini_quality_rejection_after_repair",
                       *([] if repaired_gate["passed"] else ["fallback_used"])],
            "fallback_used": not repaired_gate["passed"],
            "fallback_reason": None if repaired_gate["passed"] else "quality_gate_rejection",
            "fallback_level": None if repaired_gate["passed"] else "deterministic",
        }
        language_diagnostics[lang] = dict(repaired["generation_trace"])
        out[lang] = repaired if repaired_gate["passed"] else None

    _LAST_LANGUAGE_DIAGNOSTICS.set(language_diagnostics)
    return out, "gemini" if any(out.values()) else "fallback"
