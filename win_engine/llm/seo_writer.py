"""Ollama-powered SEO writer.

Generates title, 5 variants, description, tags, and hashtags from a video
script + competitor context. Language-aware (English / Tamil / Tanglish).
Returns None if Ollama is offline or the model output cannot be parsed.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional, Union

from win_engine.llm import ollama_client

logger = logging.getLogger(__name__)

Competitor = Union[str, dict]

_SYSTEM_PROMPT = (
    "You are a senior YouTube SEO strategist who writes upload-ready metadata "
    "for real creators. You match the natural voice and rhythm of top-performing "
    "videos in the niche. You output ONLY valid JSON — no prose, no markdown "
    "fences, no commentary."
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


def _language_instruction(language: str) -> str:
    return _LANGUAGE_INSTRUCTIONS.get(
        (language or "english").lower(),
        _LANGUAGE_INSTRUCTIONS["english"],
    )


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


def _build_competitor_block(competitors: Optional[list[Competitor]]) -> str:
    if not competitors:
        return ""
    lines: list[str] = []
    for entry in competitors[:8]:
        if isinstance(entry, dict):
            title = (entry.get("title") or "").strip()
            if not title:
                continue
            views_label = _fmt_views(entry.get("views"))
            lines.append(f"- {title} ({views_label})" if views_label else f"- {title}")
        elif isinstance(entry, str) and entry.strip():
            lines.append(f"- {entry.strip()}")
    if not lines:
        return ""
    return (
        "\nTop-performing competitor titles in this niche (for tone and "
        "structure reference — do not copy verbatim):\n" + "\n".join(lines) + "\n"
    )


def _build_user_prompt(
    script: str,
    competitor_block: str,
    language: str,
    region: str,
    audience_type: str,
) -> str:
    return f"""Video script or idea:
\"\"\"
{script.strip()}
\"\"\"
{competitor_block}
Target language: {language}
Target region: {region}
Audience type: {audience_type}

Constraints:
- {_language_instruction(language)}
- title: 50-65 characters, has the main keyword in the first 4 words, no clickbait scams, no all-caps shouting
- variants: 5 GENUINELY DIFFERENT title styles — (1) how-to, (2) listicle/number, (3) beginner-focused, (4) result-driven outcome, (5) curious question. Each variant must feel like a real creator wrote it.
- description: 120-180 words, opens with the main keyword, includes 3-4 keywords naturally, mentions what the viewer will learn, ends with a soft call to engage. No timestamps, no fake "What I'll cover" lists.
- tags: 10 lowercase tags, single or two-word, no '#' symbol, no junk filler like "video" "guide" "tips"
- hashtags: exactly 3, each starting with '#', CamelCase, derived from the topic and niche

Return ONLY this JSON object — no other text:
{{
  "title": "...",
  "variants": ["...", "...", "...", "...", "..."],
  "description": "...",
  "tags": ["...", "...", "...", "...", "...", "...", "...", "...", "...", "..."],
  "hashtags": ["#...", "#...", "#..."]
}}"""


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
        logger.warning("Ollama returned malformed JSON: %s", exc)
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


def write_seo_package(
    script: str,
    competitors: Optional[list[Competitor]] = None,
    *,
    language: str = "english",
    region: str = "global",
    audience_type: str = "general",
    temperature: float = 0.7,
    max_tokens: int = 900,
) -> Optional[dict[str, Any]]:
    """Generate a full SEO package via Ollama.

    Args:
        script: User's video script or idea.
        competitors: List of competitor entries — either plain title strings
            or dicts with {"title": str, "views": int|None}. View counts give
            the model signal about which patterns actually win.
        language: Target output language. One of english/tamil/tanglish/hindi.
        region: Geographic / cultural target (Global, India, Tamil Nadu, ...).
        audience_type: General / Local / Diaspora — shapes phrasing.

    Returns dict {title, variants, description, tags, hashtags} or None.
    """
    if not script or not script.strip():
        return None
    if not ollama_client.is_available():
        return None
    prompt = _build_user_prompt(
        script=script,
        competitor_block=_build_competitor_block(competitors),
        language=(language or "english"),
        region=(region or "global"),
        audience_type=(audience_type or "general"),
    )
    raw = ollama_client.generate(
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
