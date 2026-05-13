"""Ollama-powered SEO writer.

Generates title, 5 variants, description, tags, and hashtags from a video
script + optional competitor titles. Returns None if Ollama is offline or
the model output cannot be parsed — callers fall back to the template path.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from win_engine.llm import ollama_client

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a YouTube SEO expert. Given a video script or idea, you write "
    "metadata that maximizes click-through and search ranking. You output "
    "ONLY valid JSON — no prose, no markdown fences, no commentary."
)

_USER_TEMPLATE = """Video script or idea:
\"\"\"
{script}
\"\"\"
{competitor_block}
Generate YouTube SEO metadata. Constraints:
- title: 50-65 characters, has the main keyword in the first 4 words, no clickbait scams
- variants: 5 DIFFERENT title styles (how-to, listicle, beginner, result-driven, question)
- description: 120-180 words, opens with the main keyword, includes 3-4 keywords naturally, ends with a soft CTA
- tags: 10 lowercase tags, single or two-word, no '#' symbol, no junk filler
- hashtags: exactly 3, each starting with '#', CamelCase, derived from the topic

Return ONLY this JSON object — no other text:
{{
  "title": "...",
  "variants": ["...", "...", "...", "...", "..."],
  "description": "...",
  "tags": ["...", "...", "...", "...", "...", "...", "...", "...", "...", "..."],
  "hashtags": ["#...", "#...", "#..."]
}}"""


def _build_competitor_block(competitor_titles: list[str]) -> str:
    titles = [t.strip() for t in (competitor_titles or []) if t and t.strip()][:8]
    if not titles:
        return ""
    lines = "\n".join(f"- {t}" for t in titles)
    return f"\nTop competitor titles in this niche (for tone reference, do not copy):\n{lines}\n"


def _extract_json(raw: str) -> Optional[dict[str, Any]]:
    """Pull the first JSON object out of model output. Tolerates code fences
    and trailing prose that small local models often emit."""
    if not raw:
        return None
    text = raw.strip()
    # Strip ``` and ```json fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Otherwise grab the first {...} block
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
    # Ensure hashtags start with '#'
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
    competitor_titles: Optional[list[str]] = None,
    *,
    temperature: float = 0.6,
    max_tokens: int = 700,
) -> Optional[dict[str, Any]]:
    """Generate a full SEO package via Ollama.

    Returns a dict with keys {title, variants, description, tags, hashtags}
    or None if Ollama is offline / output is unparseable. The caller is
    responsible for falling back to the template path on None.
    """
    if not script or not script.strip():
        return None
    if not ollama_client.is_available():
        return None
    prompt = _USER_TEMPLATE.format(
        script=script.strip(),
        competitor_block=_build_competitor_block(competitor_titles or []),
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
