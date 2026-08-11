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
    "quotes": {
        "quote", "quotes", "motivation", "motivational", "healing", "heartbreak",
        "heart", "aesthetic", "rain", "peaceful", "wisdom", "lessons", "thoughts",
        "life quotes", "deep quotes",
    },
    "shorts": {
        "shorts", "short", "youtube shorts", "reels", "viral shorts", "aesthetic shorts",
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
    "quotes": [
        "quote video", "life quotes", "deep quotes", "motivational quote",
        "healing quotes", "aesthetic quotes", "shorts quotes", "heart quotes",
    ],
    "shorts": [
        "youtube shorts", "trending shorts", "short video", "viral shorts",
        "aesthetic shorts", "relatable shorts",
    ],
    "youtube_shorts": [
        "youtube shorts", "trending shorts", "short video", "viral shorts",
        "aesthetic shorts", "relatable shorts",
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
    # phrase priority — longest match wins (sorted by length at apply-time)
    "unlimited free diamonds": "ways to earn diamonds",
    "unlimited free diamond":  "ways to earn diamonds",
    "free fire hack":          "free fire tricks",
    "unlimited diamonds":      "earn diamonds",
    "unlimited money":         "money tips",
    "free diamonds":           "earn diamonds",
    "free diamond":            "earn diamonds",
    "mod apk":                 "official method",
    "hack":                    "tricks",
    "hacks":                   "tricks",
    "hacking":                 "smart methods",
    "cheat":                   "trick",
    "cheats":                  "tricks",
    "cheating":                "smart play",
    "scam":                    "real methods",
}

# Junk tag stop-list — drop these from any tag/hashtag output.
STOP_TAGS: set[str] = {
    "video", "additional", "step", "implementation", "valuable",
    "question", "introduction", "resource", "link", "today",
    "depth", "scratch", "analysis", "guide", "tip", "tips",
    "solution", "timestamp", "mistake", "comprehension",
    "understanding", "fire", "comment", "comments", "content",
    "actionable", "secret", "method", "methods", "thing", "things",
    "way", "ways", "stuff", "patreon", "subscribe", "like",
    "description", "descriptions", "result", "results", "free",
    "channel", "follow", "share", "watch", "click", "below",
    "common", "general", "basic", "simple", "easy",
}

# ---------------------------------------------------------------------------
# Fix 5: Title patterns — concrete, topic-locked, non-generic
# ---------------------------------------------------------------------------
TITLE_PATTERNS: List[str] = [
    "How to {topic} (2026 Guide)",
    "{topic}: Real Methods That Work",
    "{topic} Tips & Tricks (No Scam)",
    "Complete {topic} Guide for Beginners",
    "How I Improved {topic} (Step-by-Step)",
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
def _whole_word_in(term: str, lowered: str) -> bool:
    """Word-boundary check so 'tax' doesn't match 'syntax', 'app' doesn't match 'apply'."""
    return re.search(r"\b" + re.escape(term) + r"\b", lowered) is not None


def infer_category(text: str, hint: str | None = None) -> str:
    """Infer category from text via word-boundary keyword matching."""
    if hint and hint.lower() in CATEGORY_KEYWORDS:
        return hint.lower()
    lowered = (text or "").lower()
    if not lowered:
        return "general"
    scores = {cat: sum(1 for term in terms if _whole_word_in(term, lowered))
              for cat, terms in CATEGORY_KEYWORDS.items()}
    best_cat, best_score = max(scores.items(), key=lambda kv: kv[1])
    return best_cat if best_score > 0 else "general"


# ---------------------------------------------------------------------------
# Fix 1 — main topic extraction
# ---------------------------------------------------------------------------
def extract_main_topic(text: str) -> str:
    """Pull the main topic phrase. Prefers quote sentiment over camera/visual setup headers."""
    if not text:
        return ""
    
    clean_text = text
    clean_text = re.sub(
        r"(?i)\bbackground\s*visuals?\s*(?:is|:)?\s*[^.;,\n]*?(?=\s+and\s+|[.;,]|$)",
        " ",
        clean_text,
        count=1,
    )
    clean_text = re.sub(r"(?i)quote\s*on\s*screen:?", "", clean_text)
    
    quote_match = re.search(r'"([^"]+)"', text)
    if quote_match and len(quote_match.group(1).strip()) > 5:
        quote_body = quote_match.group(1).strip()
        quote_words = [
            w.lower()
            for w in re.findall(r"[A-Za-z]{4,}", quote_body)
            if w.lower() not in _STOPWORDS
            and w.lower() not in {
                "always", "someone", "entire", "offers", "some", "look", "looks",
                "because", "they", "theyre",
            }
        ]
        if quote_words:
            return " ".join(quote_words[:3])

    lowered = (clean_text or text).lower()

    matches = [
        term
        for terms in CATEGORY_KEYWORDS.values()
        for term in terms
        if _whole_word_in(term, lowered) and len(term) > 3
    ]
    if matches:
        return max(matches, key=len)

    words = [w for w in re.findall(r"[A-Za-z]{4,}", lowered) if w not in _STOPWORDS and w not in {"background", "visuals", "screen", "vertical", "format"}]
    if not words:
        return "deep quote"
    
    top_words = [pair[0] for pair in Counter(words).most_common(3)]
    return " ".join(top_words)


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
    idea_lower = idea.lower()
    if any(w in idea_lower for w in ["quote", "betrayal", "shorts", "reels", "sunset", "aesthetic", "motivation", "life lesson"]) or '"' in idea:
        return (
            f"{idea}. An emotional and relatable YouTube Short video featuring deep quote reflections, "
            f"an aesthetic visual mood, and powerful life perspective for viewers."
        )

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
def _is_junk_tag(tag: str) -> bool:
    """A tag is junk if it contains weird chars (#, |, etc.), is empty,
    or every meaningful word is in STOP_TAGS."""
    if not tag:
        return True
    if re.search(r"[^A-Za-z0-9\s\-'’]", tag):
        return True
    # A standalone contraction stem is a reliable sign that an LLM or keyword
    # tokenizer destroyed the original phrase ("didn't" -> "didn"). Do not
    # expose that word salad as an upload tag.
    if re.search(
        r"\b(?:didn|doesn|isn|wasn|weren|couldn|wouldn|shouldn|haven|hasn|hadn)(?!['’]t)\b",
        tag.lower(),
    ):
        return True
    words = [w for w in re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)?", tag.lower()) if w]
    if len(words) > 12:
        return True
    return not words or all(w in STOP_TAGS for w in words)


def fallback_keyword_signals(category: str) -> list[dict[str, object]]:
    seeds = CATEGORY_FALLBACK_KEYWORDS.get(category, CATEGORY_FALLBACK_KEYWORDS["general"])
    return [
        {"keyword": kw, "mentions": 1, "strength": "medium",
         "region_relevant": False, "source": "fallback"}
        for kw in seeds if not _is_junk_tag(kw)
    ]


# ---------------------------------------------------------------------------
# Fix 1 + 5 — topic-lock validators / regenerators
# ---------------------------------------------------------------------------
def title_contains_topic(title: str, topic: str) -> bool:
    if not topic:
        return True
    return topic.lower() in (title or "").lower()


def _topic_in_head(title: str, topic: str, max_words: int = 4) -> bool:
    """Keyword-first check: topic appears within the first `max_words` of the title."""
    if not topic:
        return True
    head = " ".join((title or "").split()[:max_words]).lower()
    return topic.lower() in head


def _title_is_broken(title: str) -> bool:
    """A title is broken only if empty or under 6 characters.
    AI generated titles (whether for Vlogs, Music, Gaming, Quotes, or Tutorials)
    are respected and preserved untouched."""
    if not title:
        return True
    cleaned = title.strip()
    return len(cleaned) < 6


QUOTE_TITLE_PATTERNS: List[str] = [
    "{topic} 💔 #Shorts",
    "The Hardest Truth: {topic} #Shorts",
    "{topic} | Watch Until The End... #Shorts",
    "What They Never Told You: {topic}",
    "{topic} #Shorts #Quote",
]


def force_topic_in_title(title: str, topic: str, category: str = "general",
                         variant_index: int = 0) -> str:
    """Regenerate ONLY when the LLM title is missing or unusable."""
    cleaned = (title or "").strip()
    if not _title_is_broken(cleaned):
        return cleaned

    is_shorts_or_quote = category in ("youtube_shorts", "shorts") or any(w in (topic or "").lower() for w in ["quote", "betrayal", "sunset", "aesthetic", "shorts"])
    patterns = QUOTE_TITLE_PATTERNS if is_shorts_or_quote else TITLE_PATTERNS
    pretty = topic.strip().title() if topic else ("Aesthetic Quote" if is_shorts_or_quote else f"{category.title()} Guide")
    pattern = patterns[variant_index % len(patterns)]
    return pattern.format(topic=pretty)


def force_topic_in_description(description: str, topic: str) -> str:
    """Trust a real description. Only synthesize one when it is missing.

    The old version prepended a robotic "{Topic} - complete guide. " whenever the
    topic string was not literally present — which made natural LLM/Tamil/Tanglish
    descriptions read like templates. We now leave any non-empty description alone
    and only fall back to a topic line when there is genuinely nothing to show.
    """
    desc = (description or "").strip()
    if desc:
        return desc
    if not topic:
        return ""
    return f"{topic.strip().title()} — a practical walkthrough."


def force_topic_in_tags(tags: list[str], topic: str, category: str,
                        max_tags: int = 12, min_before_fallback: int = 6) -> list[str]:
    """Drop junk tags, ensure the real topic is first, and preserve model tags.

    Generic category filler is intentionally not added. The separate Shorts rule
    in the strategy engine keeps shorts, yt, youtube shorts, and viral shorts.
    """
    pinned = {"shorts", "yt", "youtube shorts", "viral shorts"}
    required = list(dict.fromkeys(
        str(tag).strip().lower()
        for tag in (tags or [])
        if str(tag).strip().lower() in pinned
    ))
    out: list[str] = []
    seen: set[str] = set()
    reserved = min(len(required), max_tags)
    if topic and max_tags > reserved:
        out.append(topic.lower())
        seen.add(topic.lower())
    for raw in tags or []:
        t = (raw or "").strip().lower()
        if t in pinned or not t or t in seen or _is_junk_tag(t) or len(out) >= max_tags - reserved:
            continue
        out.append(t)
        seen.add(t)
    for tag in required:
        if tag not in seen and len(out) < max_tags:
            out.append(tag)
            seen.add(tag)
    return out[:max_tags]


def force_hashtags(existing: list[str] | None, topic: str, category: str,
                   count: int = 3) -> list[str]:
    """Prefer LLM-generated hashtags; only top up / regenerate when missing.

    Earlier version ignored `existing` entirely and rebuilt hashtags from a
    category template, which threw away LLM output. Now: keep the LLM's
    hashtags if they are non-junk, only fill the gap from topic + category
    fallbacks when the LLM returned nothing usable.
    """
    def _slug(s: str) -> str:
        parts = re.findall(r"[A-Za-z0-9]+", s)
        return "#" + "".join(p.title() for p in parts) if parts else ""

    out: list[str] = []
    seen: set[str] = set()

    for raw in existing or []:
        if not raw:
            continue
        tag = raw.strip()
        if not tag.startswith("#"):
            tag = "#" + tag.lstrip("#")
        body = tag.lstrip("#")
        if not body or _is_junk_tag(body):
            continue
        key = tag.lower()
        if key in seen:
            continue
        out.append(tag)
        seen.add(key)
        if len(out) >= count:
            return out[:count]

    if topic:
        h = _slug(topic)
        if h and h.lower() not in seen:
            out.append(h)
            seen.add(h.lower())

    for kw in CATEGORY_FALLBACK_KEYWORDS.get(category, []):
        if len(out) >= count:
            break
        if _is_junk_tag(kw):
            continue
        h = _slug(kw)
        if h and h.lower() not in seen:
            out.append(h)
            seen.add(h.lower())

    return out[:count]
