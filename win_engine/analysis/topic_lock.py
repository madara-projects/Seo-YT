"""Lightweight, rule-based topic-lock + safety layer.

Pure-Python, no ML, no extra deps. All six fixes live here so the rest of the
pipeline stays untouched. Used as a thin pre/post wrapper around the existing
SEO generator.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable, List

# ---------------------------------------------------------------------------
# Fix 2: Category awareness — keyword sets per category
# ---------------------------------------------------------------------------
# Subject evidence only. Words that describe a *format* ("tutorial", "review",
# "lesson") used to live here, which classified every tutorial as education —
# a cold-brew recipe was then briefed to the model as an exam-prep video and
# stamped with #StudyTips. Formats now live in _FORMAT_HINTS as tie-breakers.
# Tamil-script and Tanglish subject words are included so a Tamil script is
# classified by what it is about rather than falling through to the defaults.
CATEGORY_KEYWORDS: dict[str, set[str]] = {
    "gaming": {
        "free fire", "ff", "diamonds", "pubg", "minecraft", "fortnite", "roblox",
        "valorant", "cod", "battle royale", "redeem code", "loadout", "sensitivity",
        "noob", "pro player", "gameplay", "esports", "clash", "bgmi", "gta",
        "playstation", "ps5", "ps4", "xbox", "nintendo", "steam", "gamer", "gaming",
        "boss fight", "speedrun", "fps", "rpg",
    },
    "education": {
        "study", "exam", "exams", "syllabus", "physics", "math", "maths",
        "chemistry", "biology", "lecture", "notes", "neet", "jee", "upsc", "tnpsc",
        "board exam", "homework", "semester", "question paper", "revision",
        "படிப்பு", "தேர்வு", "பாடம்",
    },
    "finance": {
        "investment", "investing", "stocks", "stock market", "trading", "mutual fund",
        "mutual funds", "money", "income", "salary", "tax", "crypto", "bitcoin",
        "savings", "budget", "loan", "credit card", "passive income", "sip", "emi",
        "insurance", "gold rate", "fixed deposit", "share market", "பணம்", "முதலீடு",
    },
    "tech": {
        "smartphone", "android", "ios", "app", "software", "hardware",
        "ai", "coding", "programming", "python", "javascript", "java",
        "react", "api", "rest api", "fastapi", "django", "flask", "html", "css",
        "database", "sql", "server", "backend", "frontend", "github", "developer",
        "laptop", "gadget", "iphone", "samsung", "galaxy", "pixel", "oneplus",
        "xiaomi", "redmi", "windows", "linux", "macbook", "chatgpt", "processor",
        "gpu", "earbuds", "smartwatch",
    },
    "fitness": {
        "workout", "gym", "exercise", "diet", "weight loss", "fat loss", "muscle",
        "protein", "yoga", "cardio", "abs", "bodybuilding", "calories", "pushups",
        "squats", "hiit", "stretching", "home workout", "உடற்பயிற்சி",
    },
    "cooking": {
        "recipe", "recipes", "cook", "cooking", "kitchen", "ingredients", "dish",
        "meal", "vegan", "biryani", "curry", "baking", "bake", "coffee", "tea",
        "brew", "latte", "juice", "smoothie", "cake", "bread", "chicken", "mutton",
        "fish", "egg", "rice", "dosa", "idli", "sambar", "rasam", "chutney",
        "masala", "breakfast", "lunch", "dinner", "snack", "snacks", "dessert",
        "food", "street food", "samayal", "kuzhambu", "biriyani", "poriyal",
        "payasam",
        "சமையல்", "ரெசிபி", "பிரியாணி", "குழம்பு", "சாதம்", "சிக்கன்", "மட்டன்",
        "முட்டை", "தோசை", "இட்லி", "சாம்பார்", "ரசம்", "மசாலா", "பொரியல்",
        "பாயசம்", "காபி", "குக்கர்",
    },
    "vlog": {
        "vlog", "daily routine", "morning routine", "weekend", "day in life",
        "day in my life", "lifestyle", "travel vlog", "road trip",
        # Travel: a Munnar trip whose script mentions its "budget" once was
        # otherwise read as finance.
        "trip", "travel", "itinerary", "hiked", "hiking", "trek", "trekking", "sightseeing",
        "homestay", "resort", "tourist", "tourism", "hill station", "places to visit",
        "backpacking",
    },
    "quotes": {
        "quote", "quotes", "motivation", "motivational", "healing", "heartbreak",
        "aesthetic", "peaceful", "wisdom", "lessons", "thoughts", "life quotes",
        "deep quotes", "sad quotes", "love quotes",
    },
    "shorts": {
        "youtube shorts", "viral shorts", "aesthetic shorts",
    },
}

# Format words: a weak prior used only to break ties when no subject word is
# present. They never outvote a real subject.
_FORMAT_HINTS: dict[str, str] = {
    "tutorial": "education", "course": "education", "lesson": "education",
    "explained": "education", "basics": "education", "concept": "education",
    "learn": "education", "review": "tech", "unboxing": "tech",
    "shorts": "shorts", "short": "shorts", "reels": "shorts",
}
_FORMAT_HINT_WEIGHT = 0.4

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
# Only multi-word phrases that promise in-game exploits (a real YouTube policy
# risk) are rewritten. Single words such as "hack", "cheat" and "scam" were
# rewritten globally before, which changed what the creator said: "kitchen
# hacks" became "kitchen tricks", "cheat sheet" became "trick sheet", and "how
# to avoid a scam" became "how to avoid a real methods". The script is the
# source of truth and must reach analysis intact.
RISK_TERMS: dict[str, str] = {
    # phrase priority — longest match wins (sorted by length at apply-time)
    "unlimited free diamonds": "ways to earn diamonds",
    "unlimited free diamond":  "ways to earn diamonds",
    "free fire hack":          "free fire tricks",
    "free fire hacks":         "free fire tricks",
    "unlimited diamonds":      "earn diamonds",
    "unlimited money":         "money tips",
    "free diamonds":           "earn diamonds",
    "free diamond":            "earn diamonds",
    "mod apk":                 "official method",
    "hack apk":                "official method",
    "aimbot hack":             "aim training",
    "wallhack":                "map awareness",
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
    # Platform/distribution filler is not a subject tag. ``shorts`` is kept
    # separately when the creator actually supplied a Short.
    "youtube", "yt", "viral", "trending", "youtube shorts", "viral shorts",
    "trending shorts", "short video", "fyp",
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
_TAMIL_CHAR_RE = re.compile(r"[஀-௿]")


def _whole_word_in(term: str, lowered: str) -> bool:
    """Word-boundary check so 'tax' doesn't match 'syntax', 'app' doesn't match 'apply'.

    Tamil is agglutinative ("பிரியாணியை" is "biryani" with a case ending) and
    Python's ``\\b`` treats Tamil vowel signs as non-word characters, so Tamil
    terms match as a prefix of a Tamil word instead.
    """
    if _TAMIL_CHAR_RE.search(term):
        return re.search(r"(?<![஀-௿])" + re.escape(term), lowered) is not None
    return re.search(r"\b" + re.escape(term) + r"\b", lowered) is not None


def category_scores(text: str) -> dict[str, float]:
    """Subject-word evidence per category, with format words as a weak tie-breaker."""

    lowered = (text or "").casefold()
    scores: dict[str, float] = {cat: 0.0 for cat in CATEGORY_KEYWORDS}
    if not lowered:
        return scores
    for cat, terms in CATEGORY_KEYWORDS.items():
        for term in terms:
            if _whole_word_in(term, lowered):
                # A multi-word subject ("stock market") is stronger evidence
                # than a single ambiguous word.
                scores[cat] += 1.5 if " " in term else 1.0
    for word, cat in _FORMAT_HINTS.items():
        if _whole_word_in(word, lowered):
            scores[cat] = scores.get(cat, 0.0) + _FORMAT_HINT_WEIGHT
    return scores


def infer_category(text: str, hint: str | None = None) -> str:
    """Infer the subject category; a format word alone never decides it."""
    if hint and hint.lower() in CATEGORY_KEYWORDS:
        return hint.lower()
    scores = category_scores(text)
    if not scores:
        return "general"
    best_cat, best_score = max(scores.items(), key=lambda kv: kv[1])
    # A tie is ambiguous; dictionary order must not pick the category.
    if sum(1 for score in scores.values() if score == best_score) > 1:
        return "general"
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
        # A non-Latin script (Tamil) has no [A-Za-z] words. This used to return
        # the literal placeholder "deep quote", which then leaked into Tamil
        # packages as #DeepQuote. Use the source's own leading phrase instead.
        return source_lead_phrase(clean_text or text, max_words=6)

    top_words = [pair[0] for pair in Counter(words).most_common(3)]
    return " ".join(top_words)


# ---------------------------------------------------------------------------
# Source lead phrase — a contiguous, grammatical span of the creator's words
# ---------------------------------------------------------------------------
# Spoken openers that carry no topic. Stripped repeatedly from the start.
_LEAD_IN_PATTERNS = (
    re.compile(r"^(?:hi|hey|hello|vanakkam)(?:\s+(?:guys|everyone|friends|all|there|makkale|nanbargale))?[\s,!.:-]+", re.IGNORECASE),
    re.compile(r"^welcome(?:\s+back)?(?:\s+to\s+(?:my|the|our)\s+channel)?[\s,!.:-]+", re.IGNORECASE),
    re.compile(r"^(?:so|okay|ok|alright|now|well)[\s,]+", re.IGNORECASE),
    re.compile(r"^in\s+(?:this|today'?s|the|my)\s+(?:video|short|episode|tutorial|vlog|reel)[\s,:-]*", re.IGNORECASE),
    re.compile(r"^today[\s,]+", re.IGNORECASE),
    re.compile(
        r"^(?:i|we)(?:\s+(?:will|am|are|'m|'re|want|wanna|going|gonna|to|'ll|am going to))*\s+"
        r"(?:show|teach|tell|walk)\s+(?:you|u|everyone)\s+(?:through\s+)?",
        re.IGNORECASE,
    ),
    re.compile(r"^(?:let'?s|let\s+us)\s+(?:see|learn|talk\s+about|look\s+at|discuss)\s+", re.IGNORECASE),
    re.compile(r"^(?:indha|intha|inda)\s+(?:video|vdo)\s*(?:la|le|la\s+naama|la\s+nama)?[\s,]+", re.IGNORECASE),
    re.compile(r"^இந்த\s+(?:வீடியோவில்|வீடியோவுல|வீடியோ\s*ல|காணொளியில்)[\s,]*"),
    re.compile(r"^(?:வணக்கம்|ஹாய்)[^\s]*[\s,!.]*"),
)
_LEADING_DETERMINERS = {"a", "an", "the", "this", "my", "our"}
_TRAILING_FUNCTION_WORDS = {
    "a", "an", "the", "and", "or", "but", "with", "without", "from", "about", "to",
    "for", "of", "after", "before", "into", "than", "at", "in", "on", "by", "any",
    "your", "my", "our", "their", "is", "are", "was", "were", "that", "which",
    "என்று", "பற்றி", "மற்றும்",
}
_SPAN_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’-]*|[஀-௿]+")


def strip_lead_in(text: str) -> str:
    """Remove spoken openers ("In this video I show you") from the start."""

    value = re.sub(r"\s+", " ", str(text or "")).strip()
    for _ in range(6):
        before = value
        for pattern in _LEAD_IN_PATTERNS:
            value = pattern.sub("", value, count=1).strip()
        if value == before:
            break
    return value


def source_lead_phrase(text: str, max_words: int = 12) -> str:
    """First clause of the source as a contiguous phrase, never a word bag.

    Deleting stopwords from a sentence and joining what is left produced
    unreadable topics such as "you how make cold brew coffee home without".
    Keeping a contiguous span keeps the creator's grammar intact.
    """

    body = strip_lead_in(text)
    clause = next(
        (part.strip() for part in re.split(r"[.!?\n:;|]+|\s[-–—]\s", body) if part.strip()),
        "",
    )
    words = _SPAN_WORD_RE.findall(clause)
    while words and words[0].casefold() in _LEADING_DETERMINERS:
        words = words[1:]
    words = words[:max_words]
    while words and words[-1].casefold() in _TRAILING_FUNCTION_WORDS:
        words = words[:-1]
    return " ".join(words).casefold()


# ---------------------------------------------------------------------------
# Fix 4 — idea-mode expansion
# ---------------------------------------------------------------------------
def is_short_idea(text: str, threshold: int = 20) -> bool:
    return len((text or "").split()) < threshold


def expand_idea_to_script(idea: str) -> str:
    """Return a short idea unchanged.

    This used to append invented sentences to any input under twenty words —
    "we walk through ... the real methods that work ... share practical tips,
    and break down the steps" or "featuring deep quote reflections, an
    aesthetic visual mood". The model was then told to treat that text as the
    only source of facts, so the tool manufactured the very claims its own
    fidelity rules forbid. A short idea is a short source; the prompt and the
    quality gate already handle sparse input honestly.
    """
    return (idea or "").strip()


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
                        max_tags: int = 12, min_before_fallback: int = 6,
                        context: str | Iterable[str] | None = None) -> list[str]:
    """Drop junk tags, ensure the real topic is first, and preserve model tags.

    Generic category filler is intentionally not added. A Short keeps only the
    useful format tag ``shorts``; every other tag must describe the actual video.
    """
    pinned = {"shorts"}
    generic_format_tags = {
        "yt", "youtube", "viral", "trending", "youtube shorts", "viral shorts",
        "trending shorts", "short video", "video", "fyp",
    }
    context_text = context if isinstance(context, str) else " ".join(str(item) for item in (context or []))
    context_words = set(re.findall(r"[a-z0-9]+", (" ".join([topic or "", context_text])).casefold()))
    required = list(dict.fromkeys(
        str(tag).strip().lower()
        for tag in (tags or [])
        if str(tag).strip().lower() in pinned
    ))
    out: list[str] = []
    seen: set[str] = set()
    reserved = min(len(required), max_tags)
    # The final package quality gate accepts one focused phrase per tag and
    # rejects tags longer than eight words. Creator topics can legitimately be
    # longer (especially when inferred from an exact quote), so do not let the
    # topic-lock post-process make an otherwise valid provider package fail its
    # own final validation.
    topic_words = str(topic or "").strip().lower().split()
    # A full on-screen quote can exceed the one-tag contract.  Keep the first
    # focused words rather than an arbitrary closing fragment: the opening
    # phrase names the topic naturally and remains understandable on its own.
    topic_tag = " ".join(topic_words[:8])
    if topic_tag and not _is_junk_tag(topic_tag) and max_tags > reserved:
        out.append(topic_tag)
        seen.add(topic_tag)
    # If a quote needs truncating, retain its concise closing thought as a
    # second specific tag.  This avoids losing the actual emotional resolution
    # while still keeping every individual tag within the quality contract.
    closing_tag = " ".join(topic_words[-5:]) if len(topic_words) > 8 else ""
    if (
        closing_tag
        and closing_tag not in seen
        and not _is_junk_tag(closing_tag)
        and len(out) < max_tags - reserved
    ):
        out.append(closing_tag)
        seen.add(closing_tag)
    for raw in tags or []:
        t = (raw or "").strip().lower()
        if t in pinned or t in generic_format_tags or not t or t in seen or _is_junk_tag(t) or len(t.split()) > 8 or len(out) >= max_tags - reserved:
            continue
        if context is not None:
            tag_words = set(re.findall(r"[a-z0-9]+", t))
            if tag_words and not (tag_words & context_words):
                continue
        if len(out) >= max_tags - reserved:
            continue
        out.append(t)
        seen.add(t)
    for tag in required:
        if tag not in seen and len(out) < max_tags:
            out.append(tag)
            seen.add(tag)
    return out[:max_tags]


_HASHTAG_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "for", "in", "on", "at", "with",
    "how", "my", "your", "is", "are", "you", "i",
}
# Placeholders that must never reach an upload.
_PLACEHOLDER_TOPICS = {"deep quote", "this topic", "the video topic", "video topic", "aesthetic quote"}
# Letters and digits in any script, plus Indic vowel signs, which Python's \w
# does not treat as word characters.
_HASHTAG_PIECE_RE = re.compile(r"(?:[^\W_]|[ऀ-෿])+")


# A Latin word or model code standing alone: "don" in "don't" is not a token.
_CASING_TOKEN_RE = re.compile(r"(?<![\w'’])[A-Za-z0-9]*[A-Za-z][A-Za-z0-9]*(?![\w'’])")
# Ordinary words a script may capitalise for emphasis or as a code name
# ("GET endpoint", "IF formula", "this is SO good"). Lifting them would turn
# "if you want" into "IF you want", so their casing is never copied.
_CASING_COMMON_WORDS = frozenset("""
a an the and or but if so as at by for from in into of on onto to up down out over under with
without about after before again all any are be been being can could did do does done each few
get gets got had has have he her here him his how is it its just like may me might more most
much must my no nor not now off old once one only other our out own per same she should some
such than that their them then there these they this those through too until very was we were
what when where which while who why will would yes yet you your go goes going new top best
free live win use used set run let put see way big hot cold easy full fast post posts show
shows home part step steps day days time life love good great real true make watch look
""".split())
_CASING_BREAK_RE = re.compile(r"(?<=[.!?:;])\s+|[\n\"“”|]+|\s[-–—]\s")


def source_casing_map(*sources: str) -> dict[str, str]:
    """Casefolded word -> the creator's casing, for words the source always
    capitalises mid-sentence ("Galaxy", "S25", "iPhone", "VLOOKUP").

    Sentence-initial words and Title Case heading lines say nothing about a
    word's own casing, so they are not evidence; a word the source also writes
    in lowercase is left out.
    """

    forms: dict[str, set[str]] = {}
    for source in sources:
        for segment in _CASING_BREAK_RE.split(str(source or "")):
            matches = list(_CASING_TOKEN_RE.finditer(segment))
            # A Title Case heading capitalises every major word; a sentence
            # that merely names "Samsung Galaxy S25 Ultra" still has lowercase ones.
            major = [match.group(0) for match in matches if len(match.group(0)) >= 4]
            if len(major) >= 3 and all(token[:1].isupper() for token in major):
                continue
            for match in matches:
                token = match.group(0)
                if len(token) < 2:
                    continue
                # Only a word that truly opens the sentence is ambiguous; in
                # "இந்த வீடியோவில் ChatGPT ..." the first Latin word is mid-sentence,
                # and "ChatGPT"/"VLOOKUP" are names wherever they stand.
                opens_sentence = not re.search(r"\w", segment[:match.start()])
                if opens_sentence and token[1:] == token[1:].lower():
                    continue
                forms.setdefault(token.casefold(), set()).add(token)
    return {
        key: next(iter(variants))
        for key, variants in forms.items()
        if len(variants) == 1 and next(iter(variants)) != key and key not in _CASING_COMMON_WORDS
    }


def restore_source_casing(text: str, casing: dict[str, str]) -> str:
    """Re-apply the creator's casing to words a writer lowercased.

    Search phrases are lowercase, so a title built from one reads "Samsung
    galaxy s25 ultra review". Only plain lowercase or sentence-case words are
    lifted; deliberate capitals in the text are kept.
    """

    if not text or not casing:
        return text

    def _lift(match: re.Match[str]) -> str:
        word = match.group(0)
        target = casing.get(word.casefold())
        if not target or word == target:
            return word
        if word.islower() or word == word[:1].upper() + word[1:].lower():
            return target
        return word

    return _CASING_TOKEN_RE.sub(_lift, text)


def normalize_hashtag(raw: str) -> str:
    """Return a single-token hashtag, or "" when nothing usable remains.

    A hashtag ends at the first space, so the model's "#cold brew" would
    publish as #cold with a stray "brew" in the description. Multi-word input
    is joined in CamelCase ("#ColdBrew"); one-word input keeps its casing.
    """

    pieces = _HASHTAG_PIECE_RE.findall(str(raw or ""))
    if not pieces:
        return ""
    if len(pieces) == 1:
        return "#" + pieces[0]
    return "#" + "".join(
        piece if any(char.isupper() for char in piece[1:]) else piece[:1].upper() + piece[1:]
        for piece in pieces
    )


def hashtag_from_phrase(phrase: str, max_words: int = 3) -> str:
    """CamelCase hashtag from a short phrase, or "" if it would be unreadable."""

    words = [
        part for part in re.findall(r"[A-Za-z0-9]+", str(phrase or ""))
        if part.casefold() not in _HASHTAG_STOPWORDS
    ]
    if not words or len(words) > max_words:
        return ""
    tag = "#" + "".join(word if word.isupper() else word[:1].upper() + word[1:] for word in words)
    return tag if len(tag) <= 30 else ""


def force_hashtags(existing: list[str] | None, topic: str, category: str,
                   count: int = 3, tags: Iterable[str] | None = None,
                   casing: dict[str, str] | None = None) -> list[str]:
    """Prefer LLM-generated hashtags; top up only from what the video is about.

    The gap used to be filled from a per-category preset list, so a cooking
    tutorial misclassified as education shipped with #StudyTips
    #ExamPreparation. The top-up now comes from the video's own validated
    subject tags. When nothing specific is available, fewer hashtags are
    returned — YouTube does not reward a padded set, and a wrong hashtag shows
    above the title.
    """
    out: list[str] = []
    seen: set[str] = set()

    def _push(tag: str) -> None:
        key = tag.casefold().lstrip("#")
        # Skip exact and prefix duplicates (#ColdBrew / #ColdBrewCoffee): the
        # three slots should cover different subjects.
        overlaps = any(key == other or key.startswith(other) or other.startswith(key) for other in seen)
        if tag and not overlaps and len(out) < count:
            out.append(tag)
            seen.add(key)

    for raw in existing or []:
        tag = normalize_hashtag(restore_source_casing(str(raw or ""), casing or {}))
        body = tag.lstrip("#")
        if not body or len(tag) > 30 or _is_junk_tag(body):
            continue
        _push(tag)
        if len(out) >= count:
            return out[:count]

    clean_topic = str(topic or "").strip()
    if clean_topic and clean_topic.casefold() not in _PLACEHOLDER_TOPICS:
        _push(hashtag_from_phrase(restore_source_casing(clean_topic, casing or {})))

    # Strongest subject tags first; generic platform tags never qualify.
    # Tags are lowercase, so names take the creator's casing: "#GTA5Comparison".
    for tag in tags or []:
        if len(out) >= count:
            break
        text = str(tag or "").strip()
        if not text or text.casefold() in {"yt", "shorts", "youtube", "video"} or _is_junk_tag(text):
            continue
        _push(hashtag_from_phrase(restore_source_casing(text, casing or {})))

    return out[:count]
