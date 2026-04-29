"""Lightweight content analysis (drop-in replacement for the prior HF version).

Heavy ML inference (sentence-transformer cosine, Roberta sentiment) was
removed. Quality and similarity now use rule-based heuristics so the import
is instant and the FastAPI app starts in < 1 s. Narrative generation is
delegated to Ollama on demand (never at import time).

Public surface preserved so existing callers in `strategy_engine` keep working:
- get_ai_insights(script, competitor_scripts=None) -> dict
- analyze_content_quality_ai(script) -> dict
- find_content_similarity(text1, text2) -> float
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_POSITIVE = {
    "great", "best", "amazing", "easy", "new", "love", "win", "beat", "grow",
    "fast", "free", "secret", "proven", "results", "worked", "boost", "smart",
}
_NEGATIVE = {
    "bad", "fail", "worst", "scam", "hate", "broken", "wrong", "poor", "fake",
    "loss", "useless", "worst",
}


def _word_set(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z]{3,}", (text or "").lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def find_content_similarity(text1: str, text2: str) -> float:
    """Jaccard similarity over content words (0-1)."""
    return round(_jaccard(_word_set(text1), _word_set(text2)), 3)


def analyze_content_quality_ai(script: str) -> Dict[str, Any]:
    """Rule-based quality analysis. Same return shape as the old HF version."""
    script = script or ""
    words = script.split()
    word_count = len(words)
    lowered = script.lower()

    pos_hits = sum(1 for w in _POSITIVE if w in lowered)
    neg_hits = sum(1 for w in _NEGATIVE if w in lowered)
    if pos_hits > neg_hits:
        sentiment = "positive"
    elif neg_hits > pos_hits:
        sentiment = "negative"
    else:
        sentiment = "neutral"
    confidence = min(1.0, abs(pos_hits - neg_hits) / 5.0)

    score = 5.0
    if 50 <= word_count <= 2000:
        score += 1.0
    elif word_count < 50:
        score -= 1.0
    if sentiment == "positive":
        score += 0.5
    elif sentiment == "negative":
        score -= 0.5
    score += confidence * 2.0
    if "?" in script:
        score += 0.5
    if any(c in script for c in ("•", "- ", "1.", "2.")):
        score += 0.5
    score = max(0.0, min(10.0, score))

    return {
        "quality_score": round(score, 2),
        "sentiment": sentiment,
        "confidence": round(confidence, 2),
        "analysis": {
            "word_count": word_count,
            "sentence_count": len([s for s in script.split(".") if s.strip()]),
            "has_questions": "?" in script,
            "has_lists": any(c in script for c in ("•", "- ", "1.", "2.")),
        },
    }


def get_ai_insights(script: str,
                    competitor_scripts: Optional[List[str]] = None) -> Dict[str, Any]:
    quality = analyze_content_quality_ai(script)
    insights: list[dict[str, Any]] = []

    if quality["quality_score"] < 6.0:
        insights.append({
            "type": "quality",
            "level": "warning",
            "message": (
                f"Content quality score is {quality['quality_score']:.1f}/10. "
                "Consider adding more engaging elements."
            ),
        })

    if competitor_scripts:
        sims = [find_content_similarity(script, s) for s in competitor_scripts]
        if sims:
            mx = max(sims)
            if mx > 0.7:
                insights.append({
                    "type": "competition",
                    "level": "warning",
                    "message": (
                        f"High overlap ({mx:.2f}) with competitor content. "
                        "Consider differentiation."
                    ),
                })

    if quality["sentiment"] == "negative":
        insights.append({
            "type": "sentiment",
            "level": "warning",
            "message": "Content sentiment skews negative. Consider rephrasing for engagement.",
        })

    return {
        "insights": insights,
        "quality_score": quality["quality_score"],
        "sentiment": quality["sentiment"],
    }
