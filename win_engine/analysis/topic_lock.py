"""Rule-based topic, category, tag and safety helpers around the SEO generator.

Pure Python with no model calls: category inference, the main-topic phrase,
tag and hashtag clean-up, and the policy-risk wording check on generated text.
"""

from __future__ import annotations

import re
from collections import Counter
from functools import lru_cache
from typing import Iterable, List

from win_engine.analysis.source_cues import source_quote
from win_engine.analysis.text_tokens import is_word_character, strip_stray_joiners, unicode_words

# ---------------------------------------------------------------------------
# Category awareness: keyword sets per category
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
# Risk wording: exploit promises -> safer alternatives, in generated text only
# ---------------------------------------------------------------------------
# Only multi-word phrases that promise in-game exploits (a real YouTube policy
# risk) are listed; single words are ordinary copy ("kitchen hacks", "cheat
# sheet", "how to avoid a scam"). The creator's own script is never rewritten:
# "never install a mod apk: malware explained" became "never install a
# official method", and "GTA 5 unlimited money glitch patched" became "GTA 5
# money tips glitch patched". Generated copy may not *add* one of these
# phrases; a phrase the creator used is their subject and stays.
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
# Title patterns, used only when a generated title is missing or unusable
# ---------------------------------------------------------------------------
# A fallback knows the topic and nothing else. The old templates promised a
# year ("(2026 Guide)"), results ("Real Methods That Work"), trust ("(No Scam)")
# and a personal story ("How I Improved...") that no creator had claimed.
TITLE_PATTERNS: List[str] = ["{topic}"]

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "i",
    "if", "in", "into", "is", "it", "my", "of", "on", "or", "our", "that", "the",
    "their", "this", "to", "was", "we", "with", "you", "your", "what", "why",
    "when", "video", "about", "just", "really", "actually", "today", "going",
}


# ---------------------------------------------------------------------------
# Risk wording
# ---------------------------------------------------------------------------
def _risk_pattern(phrase: str) -> re.Pattern[str]:
    return re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE)


def _risk_readable(text: str) -> str:
    # "#FreeFireHack" reads as "Free Fire Hack", so hashtags are checked too.
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", str(text or "").replace("#", " "))


_RISK_HASHTAG_RE = re.compile(r"#[^\s#]+")


def _squashed(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text or "").casefold())


# The creator's source is read once per generated title, tag and hashtag.
@lru_cache(maxsize=256)
def _risk_phrases(text: str) -> frozenset[str]:
    """Risk phrases a text uses, in prose or in a hashtag of any casing.

    "#UNLIMITEDDIAMONDS" has no case change to split at, so a hashtag is also
    compared with its letters run together. Prose is not: "it's free. Diamonds
    are..." does not say "free diamonds".
    """

    readable = _risk_readable(text)
    hashtags = [_squashed(tag) for tag in _RISK_HASHTAG_RE.findall(str(text or ""))]
    return frozenset(
        risky for risky in RISK_TERMS
        if _risk_pattern(risky).search(readable) or any(_squashed(risky) in tag for tag in hashtags)
    )


def unsupported_risk_terms(text: str, source: str = "") -> list[str]:
    """Risk phrases in generated text that the creator's source never uses.

    The source is read the same way as the text: a creator's own
    "#FreeFireHack" is the subject of the video.
    """

    found = _risk_phrases(text) - _risk_phrases(source)
    return [risky for risky in sorted(RISK_TERMS, key=len, reverse=True) if risky in found]


def normalize_risk_terms(text: str, source: str = "") -> str:
    """Replace risk phrases with safer alternatives, except those in ``source``.

    Meant for generated copy. ``source`` is the creator's own material: a
    phrase it uses is the subject of the video ("never install a mod apk")
    and is left alone.
    """
    if not text:
        return text
    supported = _risk_phrases(source)
    # A hashtag cannot be reworded in place, so one that adds a risk phrase is
    # dropped, as an offending tag is.
    out = re.sub(
        r"#[^\s#]+[ \t]*",
        lambda match: "" if _risk_phrases(match.group(0)) - supported else match.group(0),
        text,
    )
    if out != text:
        out = re.sub(r"[ \t]+(?=\n|$)", "", out)
    # longest first so multi-word terms win over single-word ones
    for risky, safe in sorted(RISK_TERMS.items(), key=lambda kv: -len(kv[0])):
        if risky not in supported:
            out = _risk_pattern(risky).sub(safe, out)
    return out


# ---------------------------------------------------------------------------
# Category inference
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
# Main topic extraction
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

    # A labelled quote or a quote Short's quoted line; in a tutorial,
    # `click "Save changes"` names a button and is not the topic.
    quote_body = source_quote(text)
    if quote_body:
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
# Junk tags
# ---------------------------------------------------------------------------
def _is_tag_character(char: str) -> bool:
    # Emoji variation selectors are not tag text; a joiner inside a word is.
    return char in " -'’" or char.isspace() or is_word_character(char)


def is_junk_tag(tag: str) -> bool:
    """A tag is junk if it contains symbols (#, |, etc.), is empty,
    or every meaningful word is in STOP_TAGS.

    Letters and vowel signs of every script are ordinary tag text; an
    ASCII-only test threw away every Tamil and accented tag and hashtag.
    """
    if not tag:
        return True
    if not all(_is_tag_character(char) for char in tag) or strip_stray_joiners(tag) != tag:
        return True
    # A standalone contraction stem is a reliable sign that an LLM or keyword
    # tokenizer destroyed the original phrase ("didn't" -> "didn"). Do not
    # expose that word salad as an upload tag.
    if re.search(
        r"\b(?:didn|doesn|isn|wasn|weren|couldn|wouldn|shouldn|haven|hasn|hadn)(?!['’]t)\b",
        tag.lower(),
    ):
        return True
    words = [word for word in unicode_words(tag) if any(char.isalpha() for char in word)]
    if len(words) > 12:
        return True
    return not words or all(w in STOP_TAGS for w in words)


# ---------------------------------------------------------------------------
# Topic-lock validators / regenerators
# ---------------------------------------------------------------------------
def _title_is_broken(title: str) -> bool:
    """A title is broken only if empty or under 6 characters.
    AI generated titles (whether for Vlogs, Music, Gaming, Quotes, or Tutorials)
    are respected and preserved untouched."""
    if not title:
        return True
    cleaned = title.strip()
    return len(cleaned) < 6


# A Short's title carries #Shorts exactly once. A fixed 💔, "The Hardest
# Truth", "Watch Until The End..." and "What They Never Told You" (which also
# dropped #Shorts) told viewers things about the video no one had said.
QUOTE_TITLE_PATTERNS: List[str] = ["{topic} #Shorts"]


def force_topic_in_title(title: str, topic: str, category: str = "general",
                         variant_index: int = 0, *, short_form: bool = False) -> str:
    """Regenerate ONLY when the LLM title is missing or unusable.

    ``short_form`` is the caller's Short decision (source_cues.is_short_video);
    a category or a topic word ("sunset", "betrayal") never makes a Short.
    """
    cleaned = (title or "").strip()
    if not _title_is_broken(cleaned):
        return cleaned

    pretty = (topic or "").strip().title()
    if not pretty:
        # Nothing to name. A placeholder ("General Guide", "Aesthetic Quote")
        # is not a title; the quality gate reports the missing one instead.
        return cleaned
    patterns = QUOTE_TITLE_PATTERNS if short_form else TITLE_PATTERNS
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
    text = (topic or "").strip()
    if not text:
        return ""
    # Only what the input says. "— a practical walkthrough" claimed an
    # instructional video, and title() cased "iPhone" as "Iphone".
    return text[:1].upper() + text[1:] + ("" if text.endswith((".", "!", "?")) else ".")


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
        if not body or len(tag) > 30 or is_junk_tag(body):
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
        if not text or text.casefold() in {"yt", "shorts", "youtube", "video"} or is_junk_tag(text):
            continue
        _push(hashtag_from_phrase(restore_source_casing(text, casing or {})))

    return out[:count]
