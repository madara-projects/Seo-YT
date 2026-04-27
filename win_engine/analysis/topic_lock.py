"""Lightweight, rule-based topic-lock + safety layer.

Pure-Python, no ML, no extra deps. All six fixes live here so the rest of the
pipeline stays untouched. Used as a thin pre/post wrapper around the existing
SEO generator.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import List

# ---------------------------------------------------------------------------
# Fix 2: Category awareness — keyword sets per category
# ---------------------------------------------------------------------------
CATEGORY_KEYWORDS: dict[str, set[str]] = {
    "gaming": {
        "free fire", "ff", "diamonds", "pubg", "minecraft", "fortnite", "roblox",
        "valorant", "cod", "battle royale", "redeem code", "loadout", "sensitivity",
        "noob", "pro player", "gameplay", "esports", "clash", "bgmi",
    },
    "education": {
        "learn", "tutorial", "course", "study", "exam", "lesson", "explained",
        "syllabus", "concept", "basics", "physics", "math", "chemistry", "biology",
        "history", "english", "lecture", "notes",
    },
    "finance": {
        "investment", "stocks", "trading", "mutual fund", "money", "income",
        "salary", "tax", "crypto", "bitcoin", "savings", "budget", "loan",
        "credit card", "passive income", "sip",
    },
    "tech": {
        "smartphone", "android", "ios", "app", "software", "hardware", "review",
        "unboxing", "ai", "coding", "python", "laptop", "gadget", "iphone",
        "samsung", "windows", "linux",
    },
    "fitness": {
        "workout", "gym", "exercise", "diet", "weight loss", "muscle", "protein",
        "yoga", "cardio", "abs", "bodybuilding",
    },
    "cooking": {
        "recipe", "cook", "kitchen", "ingredients", "dish", "meal", "vegan",
        "biryani", "curry", "baking",
    },
    "vlog": {
        "vlog", "daily routine", "morning routine", "weekend", "day in life",
        "lifestyle",
    },
}

# ---------------------------------------------------------------------------
# Fix 3: API fallback — predefined keyword sets when YouTube returns nothing
# ---------------------------------------------------------------------------
CATEGORY_FALLBACK_KEYWORDS: dict[str, List[str]] = {
    "gaming": [
        "free fire diamonds", "ff tips", "redeem code", "battle royale tricks",
        "free fire guide", "ff pro tips",
    ],
    "education": [
        "study tips", "exam preparation", "learning guide", "concept explained",
        "tutorial", "complete course",
    ],
    "finance": [
        "personal finance", "investment guide", "money management",
        "saving tips", "budget plan", "tax saving",
    ],
    "tech": [
        "tech review", "smartphone guide", "app tutorial", "best gadgets",
        "tech tips", "honest review",
    ],
    "fitness": [
        "workout plan", "diet tips", "weight loss", "fitness routine",
        "gym guide", "home workout",
    ],
    "cooking": [
        "easy recipe", "quick meal", "cooking tips", "kitchen hacks",
        "tasty dish", "step by step recipe",
    ],
    "vlog": [
        "daily vlog", "morning routine", "weekend vlog", "lifestyle",
        "day in life", "real life",
    ],
    "general": [
        "complete guide", "tips and tricks", "how to", "tutorial",
        "real methods", "beginner guide",
    ],
}

# ---------------------------------------------------------------------------
# Fix 6: Risk filter — risky words → safer alternatives
# ---------------------------------------------------------------------------
RISK_TERMS: dict[str, str] = {
    # multi-word first (matched before single-word equivalents)
    "free fire hack": "free fire tricks",
    "unlimited diamonds": "earn diamonds",
    "unlimited money": "money tips",
    "free diamonds": "earn diamonds",
    "free diamond": "earn diamonds",
    "mod apk": "official method",
    # single-word
    "hack": "tricks",
    "hacks": "tricks",
    "hacking": "smart methods",
    "cheat": "trick",
    "cheats": "tricks",
    "cheating": "smart play",
    "scam": "real methods",
}

# ---------------------------------------------------------------------------
# Fix 5: Title patterns — concrete, topic-locked, non-generic
# ---------------------------------------------------------------------------
TITLE_PATTERNS: List[str] = [
    "How to {topic} (2026 Guide)",
    "{topic}: What Actually Works",
    "{topic} - Real Methods (No Scam)",
    "{topic} Tips That Actually Work in 2026",
    "Complete {topic} Guide (Beginner Friendly)",
]

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "i",
    "if", "in", "into", "is", "it", "my", "of", "on", "or", "our", "that", "the",
    "their", "this", "to", "was", "we", "with", "you", "your", "what", "why",
    "when", "video", "about", "just", "really", "actually", "today", "going",
}


# ---------------------------------------------------------------------------
# Fix 6 — risk normalization
# ---------------------------------------------------------------------------
def normalize_risk_terms(text: str) -> str:
    """Replace risky words/phrases with safer alternatives (word-boundary aware)."""
    if not text:
        return text
    out = text
    # longest first so multi-word terms win over single-word ones
    for risky, safe in sorted(RISK_TERMS.items(), key=lambda kv: -len(kv[0])):
        out = re.sub(r"\b" + re.escape(risky) + r"\b", safe, out, flags=re.IGNORECASE)
    return out


# ---------------------------------------------------------------------------
# Fix 2 — category inference
# ---------------------------------------------------------------------------
def infer_category(text: str, hint: str | None = None) -> str:
    """Infer category from text via keyword matching. Honors explicit hint."""
    if hint and hint.lower() in CATEGORY_KEYWORDS:
        return hint.lower()
    lowered = (text or "").lower()
    if not lowered:
        return "general"
    scores = {cat: sum(1 for term in terms if term in lowered)
              for cat, terms in CATEGORY_KEYWORDS.items()}
    best_cat, best_score = max(scores.items(), key=lambda kv: kv[1])
    return best_cat if best_score > 0 else "general"


# ---------------------------------------------------------------------------
# Fix 1 — main topic extraction
# ---------------------------------------------------------------------------
def extract_main_topic(text: str) -> str:
    """Pull the main topic phrase. Prefers longest known category term; falls
    back to the most frequent meaningful word."""
    if not text:
        return ""
    lowered = text.lower()

    # 1) Longest matched category phrase wins (e.g. "free fire" > "diamonds")
    matches = [
        term
        for terms in CATEGORY_KEYWORDS.values()
        for term in terms
        if term in lowered and len(term) > 3
    ]
    if matches:
        return max(matches, key=len)

    # 2) Most common meaningful word
    words = [w for w in re.findall(r"[A-Za-z]{4,}", lowered) if w not in _STOPWORDS]
    if not words:
        return ""
    return Counter(words).most_common(1)[0][0]


# ---------------------------------------------------------------------------
# Fix 4 — idea-mode expansion
# ---------------------------------------------------------------------------
def is_short_idea(text: str, threshold: int = 20) -> bool:
    return len((text or "").split()) < threshold


def expand_idea_to_script(idea: str) -> str:
    """If input is idea-sized, expand into a short narrative for downstream
    analysis. Pure templating — keeps the original intent intact."""
    idea = (idea or "").strip()
    if not idea:
        return idea
    topic = extract_main_topic(idea) or "this topic"
    return (
        f"{idea}. In this video we walk through what {topic} actually is, "
        f"why it matters, and the real methods that work. We cover the most "
        f"common questions, share practical tips, and break down the steps "
        f"in a beginner-friendly way so you can apply them today."
    )


# ---------------------------------------------------------------------------
# Fix 3 — keyword fallback when YouTube API has no data
# ---------------------------------------------------------------------------
def fallback_keyword_signals(category: str) -> list[dict[str, object]]:
    seeds = CATEGORY_FALLBACK_KEYWORDS.get(category, CATEGORY_FALLBACK_KEYWORDS["general"])
    return [
        {
            "keyword": kw,
            "mentions": 1,
            "strength": "medium",
            "region_relevant": False,
            "source": "fallback",
        }
        for kw in seeds
    ]


# ---------------------------------------------------------------------------
# Fix 1 + 5 — topic-lock validators / regenerators
# ---------------------------------------------------------------------------
def title_contains_topic(title: str, topic: str) -> bool:
    if not topic:
        return True
    return topic.lower() in (title or "").lower()


def force_topic_in_title(title: str, topic: str, category: str = "general") -> str:
    """Regenerate the title via a safe rule-based pattern if the topic is absent."""
    if title_contains_topic(title, topic):
        return title
    pretty = topic.strip().title() if topic else f"{category.title()} Guide"
    return TITLE_PATTERNS[0].format(topic=pretty)


def force_topic_in_description(description: str, topic: str) -> str:
    if not topic or topic.lower() in (description or "").lower():
        return description or ""
    return f"{topic.strip().title()} - complete guide. " + (description or "")


def force_topic_in_tags(tags: list[str], topic: str, category: str) -> list[str]:
    """Ensure the main topic and category fallback keywords appear as tags."""
    out: list[str] = list(tags or [])
    lowered = {t.lower() for t in out}
    if topic and topic.lower() not in lowered:
        out.insert(0, topic.lower())
        lowered.add(topic.lower())
    for kw in CATEGORY_FALLBACK_KEYWORDS.get(category, [])[:3]:
        if kw.lower() not in lowered:
            out.append(kw)
            lowered.add(kw.lower())
    return out
