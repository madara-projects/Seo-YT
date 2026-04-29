"""Lightweight AI engine facade (drop-in replacement for the HF version).

All heavy ML imports were removed. Sentiment and uniqueness now use
rule-based heuristics; viral-package and title generation route through
Ollama on demand. Nothing here triggers network or model loading at import
time, so FastAPI starts immediately.

Public surface preserved so existing callers keep working:
- get_ai_engine() -> LightweightAIEngine
- engine.score_emotional_hook(text) -> {"primary_emotion", "confidence_score"}
- engine.calculate_uniqueness(target, competitors) -> float
- engine.generate_viral_package(script_summary) -> dict
- engine.generate_title(script_summary) -> str
- engine.generate_cloud_title(script_summary) -> str
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from win_engine.ai_enhancement import (
    analyze_content_quality_ai,
    find_content_similarity,
)
from win_engine.llm import ollama_client

logger = logging.getLogger(__name__)


class LightweightAIEngine:
    """Stateless facade that lazily talks to Ollama."""

    def score_emotional_hook(self, text: str) -> Dict[str, Any]:
        quality = analyze_content_quality_ai(text)
        return {
            "primary_emotion": quality["sentiment"],
            "confidence_score": quality["confidence"],
        }

    def calculate_uniqueness(self, user_script: str,
                             competitor_scripts: List[str]) -> float:
        if not competitor_scripts:
            return 1.0
        max_sim = max(find_content_similarity(user_script, s)
                      for s in competitor_scripts)
        return round(max(0.0, 1.0 - max_sim), 2)

    def generate_viral_package(self, script_summary: str) -> Dict[str, Any]:
        titles = self._generate_titles(script_summary)
        hook = self._generate_hook(script_summary)
        thumb = self._generate_thumbnail_text(script_summary)
        best = titles[0] if titles else "How to Learn Faster (Step-by-Step Guide)"
        return {
            "title": best,
            "alt_titles": titles[1:] if len(titles) > 1 else [],
            "hook": hook,
            "thumbnail_text": thumb,
        }

    def generate_title(self, script_summary: str) -> str:
        pkg = self.generate_viral_package(script_summary)
        return pkg.get("title", "How to Learn Faster (Step-by-Step Guide)")

    # Back-compat alias used by older call sites
    def generate_cloud_title(self, script_summary: str) -> str:
        return self.generate_title(script_summary)

    # ---- internals -----------------------------------------------------
    def _generate_titles(self, script_summary: str) -> List[str]:
        system = (
            "You are a YouTube growth expert. Generate EXACTLY 5 highly "
            "clickable YouTube titles under 60 characters. No quotes. "
            "No hashtags. Return ONLY a numbered list."
        )
        prompt = (
            "Rules:\n* Use power words\n* Create curiosity\n* Make it viral\n\n"
            f"Topic:\n{script_summary[:500]}"
        )
        res = ollama_client.generate(prompt, system=system, max_tokens=250)
        if not res:
            return []
        lines = [ln.strip() for ln in res.split("\n") if len(ln.strip()) > 5]
        return [self._clean_title(t) for t in lines][:5]

    def _generate_hook(self, script_summary: str) -> str:
        system = "You are a viral YouTube scriptwriter."
        prompt = (
            "Write the first 5 seconds (hook). Pattern interrupt, massive "
            "curiosity, extremely fast pacing, max 2 lines. No quotes.\n\n"
            f"Topic:\n{script_summary[:500]}"
        )
        res = ollama_client.generate(prompt, system=system, max_tokens=100)
        if res:
            return res.replace('"', "").strip()
        return "You're doing this WRONG...\nHere's what nobody tells you."

    def _generate_thumbnail_text(self, script_summary: str) -> str:
        system = "You are a YouTube thumbnail expert."
        prompt = (
            "Write the text for a YouTube thumbnail. 2 to 5 words ONLY. "
            "Big emotional impact. No punctuation.\n\n"
            f"Topic:\n{script_summary[:500]}"
        )
        res = ollama_client.generate(prompt, system=system, max_tokens=20)
        if res:
            return re.sub(r"[^\w\s]", "", res).upper().strip()
        return "BIG MISTAKE"

    @staticmethod
    def _clean_title(title: str) -> str:
        title = re.sub(r"^(\d+[\.\-\)]|\-|\*)\s*", "", title.strip())
        title = title.replace("\n", "").strip().strip("\"'")
        title = title.replace("**", "").replace("*", "")
        if len(title) > 60:
            title = title[:57] + "..."
        return title


_engine_instance: LightweightAIEngine | None = None


def get_ai_engine() -> LightweightAIEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = LightweightAIEngine()
    return _engine_instance
