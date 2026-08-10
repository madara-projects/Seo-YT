"""SEO writer for YouTube Studio.

Generates title, 5 variants, description, tags, and hashtags from a video
script + competitor context. Language-aware and auto-detects content type
(Vlogs, Gaming, Quotes, Shorts, Music, Tutorials, etc.).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional, Union

from win_engine.llm import gemini_client

logger = logging.getLogger(__name__)

Competitor = Union[str, dict]

_SYSTEM_PROMPT = (
    "You are an expert YouTube SEO strategist. You analyze the user's video script, quote, or idea "
    "to write high-CTR title variants, descriptions, tags, and hashtags. "
    "Output ONLY valid JSON with keys: \"title\", \"variants\" (array of 5 strings), "
    "\"description\", \"tags\" (array of 10 strings), and \"hashtags\" (array of 3 strings)."
)


def _validate(pkg: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Shape-check + light coercion. Coerces flexible model outputs cleanly."""
    if not isinstance(pkg, dict):
        return None
    
    title = str(pkg.get("title") or pkg.get("primary_title") or "").strip()
    
    raw_variants = pkg.get("variants") or pkg.get("title_variants") or pkg.get("titles") or []
    variants: list[str] = []
    if isinstance(raw_variants, dict):
        variants = [str(v).strip() for v in raw_variants.values() if str(v).strip()]
    elif isinstance(raw_variants, list):
        for item in raw_variants:
            if isinstance(item, dict):
                v_str = str(item.get("title") or item.get("text") or "").strip()
                if v_str:
                    variants.append(v_str)
            elif str(item).strip():
                variants.append(str(item).strip())
    elif isinstance(raw_variants, str) and raw_variants.strip():
        variants = [raw_variants.strip()]

    if not title and variants:
        title = variants[0]
    elif title and not variants:
        variants = [title]

    description = str(pkg.get("description") or pkg.get("summary") or "").strip()

    raw_tags = pkg.get("tags") or pkg.get("keywords") or []
    tags: list[str] = []
    if isinstance(raw_tags, list):
        tags = [str(t).strip().lower().lstrip("#") for t in raw_tags if str(t).strip()]
    elif isinstance(raw_tags, str):
        tags = [str(t).strip().lower().lstrip("#") for t in raw_tags.split(",") if str(t).strip()]

    raw_hashtags = pkg.get("hashtags") or []
    hashtags: list[str] = []
    if isinstance(raw_hashtags, list):
        hashtags = [str(h).strip() for h in raw_hashtags if str(h).strip()]
    elif isinstance(raw_hashtags, str):
        hashtags = [str(h).strip() for h in raw_hashtags.split() if str(h).strip()]

    if not title or not variants:
        return None

    if not description:
        description = f"A powerful reflection on {title}. Watch until the end for the full realization."

    if not tags:
        tags = [t.lower() for t in title.split() if len(t) > 3][:10]

    hashtags = [h if h.startswith("#") else f"#{h}" for h in hashtags]
    if not hashtags:
        hashtags = ["#shorts", "#quotes", "#viral"]

    return {
        "title": title,
        "variants": variants[:5],
        "description": description,
        "tags": tags[:12],
        "hashtags": hashtags[:5],
    }

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
    "general": (
        "Niche: GENERAL. Lead with the clearest specific promise. Natural, "
        "human creator voice; avoid generic filler."
    ),
}

# Compact few-shot examples — a 7B model follows examples far better than prose.
_FEWSHOT = {
    "tamil": (
        'Example tone (Tamil): title "ஆபீஸ் வாழ்க்கை உண்மை — யாரும் சொல்லாத விஷயங்கள்", '
        'variant "9-5 ஜாப் ல நான் கத்துக்கிட்ட 5 விஷயங்கள்".'
    ),
    "tanglish": (
        'Example tone (Tanglish): title "Office Life Reality — Yaarum Sollatha Truth", '
        'variant "Semma Boring 9-5 Job ah Interesting Aakkura 5 Tips".'
    ),
    "english": (
        'Example tone (English): title "Office Life Honestly — What Nobody Tells You", '
        'variant "5 Things I Learned in My First Year at a 9-5".'
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
        ("Target viewer", creator_brief.get("target_audience")),
        ("Viewer promise", creator_brief.get("viewer_promise")),
        ("Unique angle", creator_brief.get("unique_angle")),
        ("Proof or real footage", creator_brief.get("proof")),
        ("Video format", creator_brief.get("video_format")),
        ("Preferred title style", creator_brief.get("title_style")),
        ("Thumbnail direction", creator_brief.get("thumbnail_idea")),
    ]
    lines = [f"- {label}: {str(value).strip()}" for label, value in fields if value and str(value).strip()]
    if not lines:
        return ""
    return "\nCreator brief (source of truth for audience and promise):\n" + "\n".join(lines) + "\n"


def _build_channel_learning_block(channel_learning: Optional[dict[str, Any]]) -> str:
    """Format channel learning history so the LLM models titles after proven channel winners."""
    if not channel_learning:
        return ""
    lines: list[str] = []
    best_videos = channel_learning.get("best_videos") or []
    for v in best_videos[:3]:
        t = (v.get("title") or "").strip()
        views = v.get("views")
        if t:
            v_str = f" ({int(views):,} views)" if views else ""
            lines.append(f"- Proven Top Video: \"{t}\"{v_str}")
    rec = channel_learning.get("recommendation")
    if rec and str(rec).strip():
        lines.append(f"- Channel Insight: {str(rec).strip()}")
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
) -> str:
    fewshot_key = (language or "english").lower()
    fewshot_key = _LANGUAGE_ALIASES.get(fewshot_key, fewshot_key)
    fewshot = _FEWSHOT.get(fewshot_key, _FEWSHOT["english"])
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
{fewshot}

Constraints:
- {_language_instruction(language)}
- the title, description, and tags must accurately match the creator brief and real video
- description MUST be detailed and comprehensive (150-300 words), structured with an engaging opening hook, clear bullet points of takeaways or timestamps, subscriber call to action, and top hashtags
- title: 45-65 characters, engaging, matching content category (Shorts/Quotes, Vlogs, Gaming, Tutorials)
- return exactly five distinct variants. Variant 1 is SEARCH (main topic + clear outcome), variant 2 is BROWSE (truthful curiosity or emotion), and variant 3 is EXISTING AUDIENCE (a personal proof, story, or channel-relevant angle). Variants 4-5 are additional truthful alternatives.
- thumbnail text must add a short new idea; it must not merely repeat the title. Never use false guarantees, unrelated trends, or misleading claims.
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
        variants = [str(v).strip() for v in pkg["variants"] if str(v).strip()]
        description = str(pkg["description"]).strip()
        tags = [str(t).strip().lower().lstrip("#") for t in pkg["tags"] if str(t).strip()]
        hashtags = [str(h).strip() for h in pkg["hashtags"] if str(h).strip()]
    except (KeyError, TypeError, AttributeError):
        return None
    if not title or not description or not variants or not tags:
        return None
    hashtags = [h if h.startswith("#") else f"#{h}" for h in hashtags]
    return {
        "title": title,
        "variants": variants[:5],
        "description": description,
        "tags": tags[:10],
        "hashtags": hashtags[:3],
    }


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
    )
    raw = gemini_client.generate(
        prompt=prompt,
        system=_SYSTEM_PROMPT,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    if not raw:
        return None
    parsed = _extract_json(raw)
    if parsed is None:
        return None
    return _validate(parsed)


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
    temperature: float = 0.5,
    max_tokens: int = 2048,
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
    temperature: float = 0.5,
    max_tokens: int = 2048,
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
    temperature: float = 0.5,
    max_tokens: int = 2048,
) -> tuple[dict[str, Optional[dict[str, Any]]], str]:
    """Generate SEO packages for several languages in one pass.

    Uses Gemini for every requested language. Returns ``gemini`` or ``fallback``.
    """
    langs = [l.lower() for l in (languages or ["english", "tamil", "tanglish"])]
    if not script or not script.strip():
        return {lang: None for lang in langs}, "fallback"

    out: dict[str, Optional[dict[str, Any]]] = {}
    gemini_ready = gemini_client.is_available()
    
    primary_pkg = None
    if gemini_ready:
        primary_pkg = _generate_one(
            script, competitors, language="english", region=region, audience_type=audience_type,
            category=category, creator_brief=creator_brief, channel_learning=channel_learning,
            temperature=temperature, max_tokens=max_tokens,
        )
    
    if primary_pkg:
        out["english"] = primary_pkg
        for lang in langs:
            if lang == "english":
                continue
            # Try secondary language generation with short pause; if rate limited, adapt primary pkg
            import time
            time.sleep(0.5)
            sec_pkg = _generate_one(
                script, competitors, language=lang, region=region, audience_type=audience_type,
                category=category, creator_brief=creator_brief, channel_learning=channel_learning,
                temperature=temperature, max_tokens=max_tokens,
            )
            out[lang] = sec_pkg or primary_pkg
    else:
        for lang in langs:
            out[lang] = None

    return out, "gemini" if any(out.values()) else "fallback"
