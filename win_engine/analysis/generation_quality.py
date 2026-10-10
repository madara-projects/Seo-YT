"""Deterministic Phase 4 generation quality and diversity checks.

The gate is deliberately provider-independent. It accepts a generated package,
checks it against the creator's source material and recent title history, and
returns structured reasons that can be stored and rendered without claiming a
performance prediction.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from itertools import pairwise
from os.path import commonprefix
from typing import Any, Iterable

from win_engine.analysis.source_cues import (
    QUOTE_PHRASE_STARTS,
    affirmed_feeling_words,
    feeling_words,
    is_negator,
    is_short_video,
    quote_punchline,
    quote_title,
    source_quote,
    timestamp_line,
)
from win_engine.analysis.text_tokens import normalize_unicode, unicode_words, word_spans
from win_engine.analysis.topic_lock import normalize_hashtag
from win_engine.analysis.transliteration import phonetic_key, phonetic_keys, phonetic_match


_TAMIL_RANGE = re.compile(r"[\u0B80-\u0BFF]")
_GENERIC_TITLE_PATTERNS = (
    re.compile(r"^the honest truth about\b", re.IGNORECASE),
    re.compile(r"^what .+ really means\b", re.IGNORECASE),
    re.compile(r"^.+: what you need to know\b", re.IGNORECASE),
    re.compile(r"^a different way to see\b", re.IGNORECASE),
    re.compile(r"^the most useful lesson from\b", re.IGNORECASE),
    re.compile(r"^a quiet reminder about\b", re.IGNORECASE),
    re.compile(r"^(?:how .+ works in practice|the practical side of|a closer look at|what to know about)\b", re.IGNORECASE),
    re.compile(r"^(?:best .+ tips|complete guide to|everything you need to know|learn how to|methods for|ways to|common questions about)\b", re.IGNORECASE),
    re.compile(r"^(?:a quiet look at|a moment about|reflecting on)\s*(?:your|the)?\s*(?:topic|video|story)?\s*$", re.IGNORECASE),
)
_UNSUPPORTED_CLAIMS = (
    ("relationship_event", re.compile(r"\b(?:they|he|she) (?:left|cheated|lied|returned|came back|walked away)\b", re.IGNORECASE)),
    ("invented_loss_event", re.compile(
        r"\b(?:(?:someone|somebody|a person|they|he|she) (?:is |was |are |were |has |have )?(?:gone|dead|deceased|no longer here)"
        r"|after (?:someone|somebody|a person) (?:leaves|left|is gone))\b",
        re.IGNORECASE,
    )),
    ("invented_outcome", re.compile(r"\b(?:guaranteed|proven to|will make you|will get you|100%|go viral)\b", re.IGNORECASE)),
    ("invented_evidence", re.compile(r"\b(?:studies show|research proves|scientists found|data proves)\b", re.IGNORECASE)),
    ("invented_relationship", re.compile(r"\b(?:breakup|toxic relationship|one-sided relationship|just an option)\b", re.IGNORECASE)),
    ("invented_causality", re.compile(r"\b(?:leads? to|causes?|results? in)\b", re.IGNORECASE)),
)
# Platform-format words are not subject evidence. ``yt`` and ``shorts`` may be
# retained separately as an explicit creator strategy preference for Shorts.
_PLATFORM_TAGS = {
    "short", "shorts", "yt", "youtube", "youtube shorts", "viral", "viral shorts",
    "trending", "trending shorts", "short video", "video", "fyp",
}
_PREFERRED_SHORT_TAGS = {"yt", "shorts"}
_SHORTS_TITLE_RE = re.compile(r"(?<![\w#])#shorts(?!\w)", re.IGNORECASE)
_TITLE_EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]")
_GENERIC_FORMAT_TAGS = {
    "shorts", "yt", "youtube", "youtube shorts", "viral", "viral shorts",
    "trending", "trending shorts", "short video", "video", "fyp",
}
# Context a description must never invent. The list was applied to every video,
# but most of it only makes sense for reflective quote/story content: there,
# "night", "healing", "boyfriend" or "love" invents a scene or relationship the
# creator never described. For a recipe, review, or tutorial the same words are
# ordinary copy ("you'll love this", "get the ratio right", "great for the
# family", "steep for 12 hours"), and rejecting them sent good AI output to the
# broken fallback. Clinical claims stay banned everywhere.
_CLINICAL_CONTEXT_TERMS = {
    "therapy", "therapist", "clinical", "diagnosis", "depression", "anxiety", "trauma",
}
# Words the quote's own feeling supports: a quote about loving or missing
# someone may be packaged as love, and one about healing as peace or
# comfort. They were banned outright, which rejected this channel's ordinary
# vocabulary; "right" and "wrong" are not a scene. A quote about silence or
# loneliness still cannot be sold as comfort, nor any quote as a night scene.
_LOVE_CONTEXT_TERMS = {"love", "lover", "romance", "romantic", "unrequited"}
_COMFORT_CONTEXT_TERMS = {"peace", "peaceful", "comfort", "comforting", "healing"}
_LOVE_FEELING_KEYS = {"lov", "hear", "miss"}
_COMFORT_FEELING_KEYS = {"heal"}
_REFLECTIVE_CONTEXT_TERMS = {
    "childhood", "workplace", "partner", "boyfriend", "girlfriend", "husband", "wife", "product",
    "review", "comparison", "customer", "office", "school", "family",
    "night", "nighttime", "midnight", "dark", "darkness", "empty", "deserted",
    "room", "rooms", "hour", "hours",
} | _LOVE_CONTEXT_TERMS | _COMFORT_CONTEXT_TERMS
_UNSUPPORTED_CONTEXT_TERMS = _CLINICAL_CONTEXT_TERMS | _REFLECTIVE_CONTEXT_TERMS
# Formats that cannot be inferred from what the video contains; only the
# creator can say a video is one ("In this vlog" on a talking-head script).
_SUPPLIED_ONLY_FORMATS = {"vlog", "podcast", "interview", "livestream"}
# Production terms describe the shoot, not what a viewer gets from the video.
_PRODUCTION_JARGON_RE = re.compile(r"\btalking[\s_-]*heads?\b|\bb[\s-]?roll\b", re.IGNORECASE)
# The writer's fidelity rules, narrated back to the viewer: "...honoring the
# exact emotional weight ... without adding external stories or invented
# outcomes". Legitimate copy never describes what it chose not to invent.
_PROCESS_NARRATION_RE = re.compile(
    # Not "without any context": "no context" clips are a genre of their own.
    r"\bwithout\s+(?:adding|inventing|making\s+up)\b[^.!?\n]{0,40}?"
    r"\b(?:stor(?:y|ies)|assumptions?|details?|outcomes?|events?|facts?|context|claims?|embellishments?|narratives?)\b"
    r"|\binvented\s+(?:outcomes?|stor(?:y|ies)|details?|events?|facts?|context|claims?)\b"
    r"|\b(?:external|outside)\s+(?:stor(?:y|ies)|assumptions?|narratives?|context)\b"
    r"|\b(?:exact|original)\s+emotional\s+(?:idea|weight|meaning)\b"
    # Not "source material" or "true to the original": adaptations and covers
    # use those legitimately.
    r"|\bcreator(?:['’]s)?\s+(?:source|intent|words)\b|\bsource\s+fidelity\b"
    r"|\b(?:stays?|staying|remains?|remaining)\s+(?:true|faithful)\s+to\s+the\s+(?:quote|source|creator)\b"
    r"|\bno\s+(?:invented|added|made[\s-]up)\s+(?:details?|stor(?:y|ies)|facts?|events?)\b",
    re.IGNORECASE,
)


def description_prose(value: Any) -> str:
    """A description without its chapter list and its hashtag line.

    The timestamp lines are the creator's own, pasted for YouTube's chapters;
    judged as copy they read as a repeated keyword list and pushed a full
    description past its word band. The hashtags are judged as hashtags:
    read as words, "#LiveStream" called a tutorial a livestream, and a
    hashtag diluted a quote-only Short's description score.
    """

    lines = [
        line for line in normalize_unicode(value).splitlines()
        if not timestamp_line(line) and not re.fullmatch(r"\s*(?:#[^\s#]+\s*)+", line)
    ]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def narrates_process(text: Any) -> bool:
    """True when copy describes the writing rules instead of the video."""

    return bool(_PROCESS_NARRATION_RE.search(normalize_unicode(text)))


def strip_process_narration(text: str) -> str:
    """Cut rule-narrating clauses out of copy, keeping the rest of each sentence.

    "...set against a rainy road, honoring the exact emotional weight ...
    without adding external stories." keeps "...set against a rainy road."
    A sentence with nothing viewer-facing left is dropped.
    """

    kept_paragraphs: list[str] = []
    for paragraph in re.split(r"\n\s*\n", str(text or "")):
        sentences = re.split(r"(?<=[.!?])\s+", paragraph.strip())
        kept: list[str] = []
        for sentence in sentences:
            match = _PROCESS_NARRATION_RE.search(sentence)
            if not match:
                kept.append(sentence)
                continue
            head = sentence[:match.start()]
            comma = head.rfind(",")
            if comma != -1:
                head = head[:comma]
            head = re.sub(r"\s+(?:and|while|by|through|with|as|all)\s*$", "", head.rstrip(" ,;:-–—"), flags=re.IGNORECASE)
            trailing = re.findall(r"\s*[\U0001F300-\U0001FAFF☀-➿]+\s*$", sentence)
            if len(re.findall(r"[^\W\d_]+", head)) >= 4:
                kept.append(head.rstrip() + "." + (" " + trailing[0].strip() if trailing else ""))
        if kept:
            kept_paragraphs.append(" ".join(kept))
    return "\n\n".join(kept_paragraphs).strip()


# How a Short was made, which its viewers are already watching: "This video
# features a person walking alone ... in slow motion, accompanied by the exact
# on-screen text: ..." was a live Short's whole description.
_PRODUCTION_NOTE_RE = re.compile(
    r"\b(?:this|the)\s+(?:video|short|clip|reel)\s+(?:features|shows|captures|follows|opens\s+(?:on|with))\b"
    r"|\bthe\s+(?:video|clip|reel)\s+is\b"
    r"|\bon[\s-]?screen\s+(?:text|quote|caption|words?)\b|\btext\s+overlay\b"
    r"|\bthe\s+(?:video\s+)?background\s+(?:is|shows|features|has)\b"
    r"|\bslow[\s-]?motion\b|\baccompanied\s+by\b",
    re.IGNORECASE,
)


def _line_sentences(line: str) -> list[str]:
    return [part for part in re.split(r"(?<=[.!?…])\s+", line.strip()) if part]


def _is_production_note(sentence: str, subject: str) -> bool:
    # A phrase the creator's own subject uses ("slow motion lightning") is the
    # video's topic, not a note on how it was made.
    return any(match.group(0).casefold() not in subject
               for match in _PRODUCTION_NOTE_RE.finditer(normalize_unicode(sentence)))


def production_note_sentences(text: Any, subject: Any = "") -> list[str]:
    """Sentences of a description that describe the production, not what the video means."""

    folded = normalize_unicode(subject).casefold()
    return [sentence for line in str(text or "").splitlines() for sentence in _line_sentences(line)
            if _is_production_note(sentence, folded)]


def strip_production_notes(text: Any, subject: Any = "") -> str:
    """A Short's description without its production-note sentences; "" when nothing else is left."""

    folded = normalize_unicode(subject).casefold()
    lines: list[str] = []
    for line in str(text or "").splitlines():
        sentences = _line_sentences(line)
        kept = [sentence for sentence in sentences if not _is_production_note(sentence, folded)]
        if len(kept) == len(sentences):
            lines.append(line)
        elif kept:
            lines.append(" ".join(kept))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


_MOVED_ON_PERSON_RE = re.compile(
    r"\b(?:(?:the|that|other|another|a)\s+)?(?:person|someone|somebody|they)\s+(?:who\s+)?(?:has\s+|have\s+)?moved\s+on(?:\s+from\s+your\s+life)?\b",
    re.IGNORECASE,
)
_DESCRIPTION_BOILERPLATE = (
    re.compile(r"\b(?:this (?:video|short) focuses on|this (?:video|short) explores|experience a brief moment of)\b", re.IGNORECASE),
    re.compile(r"\b(?:perfect for anyone who|take a moment to breathe and process)\b", re.IGNORECASE),
)
_INSTRUCTIONAL_SOURCE_RE = re.compile(
    r"\b(?:tutorial|walkthrough|step[- ]by[- ]step|practical tips?|guide|"
    r"we (?:explain|cover|break down|show)|here are|demonstrat(?:e|ion)|instructions?)\b",
    re.IGNORECASE,
)
_UNSUPPORTED_INSTRUCTIONAL_RE = re.compile(
    r"\b(?:coping with|dealing with|overcome|practical (?:tips?|ways?)|advice|"
    r"common questions?|signs (?:it is|you|of)|tips and tricks|q\s*&\s*a|tutorial|explain(?:s|ing)?|break(?:ing)? down|"
    r"step[- ]by[- ]step|beginner(?:-friendly)? guide|complete guide|guide to|lessons?|"
    r"how to (?:cope|deal|fix|make|clean|improve|handle|recover|move on)|how you can handle|"
    r"walk(?:s|ing)? through|explor(?:e|ing) (?:how|the)|"
    r"understanding (?:grief|loss|absence|silence|emotions?|feelings?))\b",
    re.IGNORECASE,
)
_INSTRUCTIONAL_CONTEXT_RE = re.compile(
    r"\b(?:tutorial|how[- ]to|walkthrough|guide|educational|explainer|comparison|review|demonstration)\b",
    re.IGNORECASE,
)
_PROCEDURAL_ACTION_RE = re.compile(
    r"\b(?:check|inspect|adjust|reduce|lower|use|remove|blow|clean|try|reposition)\b",
    re.IGNORECASE,
)


def title_similarity(left: Any, right: Any) -> float:
    """Combine Unicode sequence and token overlap similarity."""

    left_text = " ".join(unicode_words(left))
    right_text = " ".join(unicode_words(right))
    if not left_text or not right_text:
        return 0.0
    sequence = SequenceMatcher(None, left_text, right_text).ratio()
    left_tokens, right_tokens = set(left_text.split()), set(right_text.split())
    overlap = len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)
    return round(max(sequence, overlap), 4)


def title_copies_quote(value: Any, exact_quote: Any) -> bool:
    """Catch full and truncated quote copies after hashtags/emoji are removed."""

    title_words = [word for word in unicode_words(value) if word != "shorts"]
    quote_words = unicode_words(exact_quote)
    if not title_words or not quote_words:
        return False
    if title_similarity(" ".join(title_words), " ".join(quote_words)) >= 0.86:
        return True
    title_set, quote_set = set(title_words), set(quote_words)
    return len(title_words) >= 5 and len(title_set & quote_set) / len(title_set) >= 0.9


# "Alone quotes for when people misunderstand you", "Heart touching sad pain
# quotes for missing someone": a search phrase with a format word, where the
# title should carry the quote's feeling. "lines" counts only near the start
# ("Deep lines for ..."); later it is ordinary ("the lines on your hands").
_KEYWORD_QUOTES_TITLE_RE = re.compile(
    r"\b(?:quotes?|status|shayari|captions?)\s+(?:for|about|on|when|that|to)\b"
    r"|^\W*(?:[^\W\d_]+[\s-]+){0,3}lines\s+(?:for|about|on|when|that|to)\b",
    re.IGNORECASE,
)
# Curly and straight marks are one character to a reader: a title typed with
# "it's" copies a quote written with "it’s".
_STRAIGHT_MARKS = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"'})


def _fold_marks(text: Any) -> str:
    return normalize_unicode(text).translate(_STRAIGHT_MARKS)


def _keyword_quotes_title(body: str, quote: Any) -> bool:
    """A "<keyword> quotes for ..." construction the quote's own words do not contain."""

    match = _KEYWORD_QUOTES_TITLE_RE.search(body)
    return bool(match) and match.group(0).casefold() not in _fold_marks(quote).casefold()
# The title voices the feeling or speaks to the viewer.
_VOICE_RE = re.compile(r"\b(?:you|your|yourself|you['’](?:re|ve|ll)|i|i['’]m|me|my|myself|we|us|our)\b", re.IGNORECASE)
# Labels in a creator's notes ("the quote is-", "the video is-"), not the scene.
_NOTE_LABEL_WORDS = {"quote", "video", "background", "visual", "visuals", "text", "screen", "reel", "short", "format"}


def _shares_root(word: str, roots: set[str]) -> bool:
    """Same root, or the same long stem ("misunderstood" and "misunderstand")."""

    root = _quality_root(word)
    return root in roots or any(
        len(commonprefix([root, other])) >= max(5, min(len(root), len(other)) - 3) for other in roots
    )


def _feeling_keys(text: Any) -> set[str]:
    # "betrayal" and "betrayed", "love" and "loving" name one feeling.
    return {_quality_root(word)[:4] for word in feeling_words(text)}


def title_body(title: Any) -> str:
    """A title as the viewer reads it: without #shorts, emoji and their joiners."""

    body = _TITLE_EMOJI_RE.sub(" ", _SHORTS_TITLE_RE.sub(" ", normalize_unicode(title)))
    return re.sub(r"\s+", " ", body.replace("‍", "").replace("️", "")).strip(" -|")


def _quote_tokens(text: Any) -> list[tuple[str, int, int]]:
    """(word, start, end) of each word of ``_fold_marks(text)``, so the punctuation between two words can be read.

    Words are read as unicode_words reads them: a Tamil or Hindi vowel sign
    is part of its word, not a break inside it.
    """

    return word_spans(_fold_marks(text))


def title_cuts_quote(title: Any, quote: Any) -> bool:
    """True when the title is a run of the quote's words that stops mid-phrase.

    "But it's more about who makes you seen felt heard" stops inside its
    list; "The heart has a strange habit of missing people" stops where a new
    phrase begins. A title in its own words is not judged here.
    """

    body = title_body(title)
    if "…" in body or "..." in body:
        return True
    flat_quote = _fold_marks(quote)
    tokens = _quote_tokens(flat_quote)
    run = _quote_run(body, flat_quote)
    if not run or run[1] - run[0] < 4 or run[1] - run[0] >= len(tokens):
        return False
    end = run[1]
    if end >= len(tokens):
        return False
    gap = flat_quote[tokens[end - 1][2]:tokens[end][1]]
    return not (re.search(r"[.,;:!?…—–-]", gap) or tokens[end][0] in QUOTE_PHRASE_STARTS)


def _quote_run(title: Any, quote: Any) -> tuple[int, int] | None:
    """Where a title made of the quote's own words sits in it: (first, past-last) word index, or None."""

    words = unicode_words(_fold_marks(title_body(title)), min_length=1)
    quote_words = [word for word, _, _ in _quote_tokens(quote)]
    if not words:
        return None
    for start in range(len(quote_words) - len(words) + 1):
        if quote_words[start:start + len(words)] == words:
            return start, start + len(words)
    return None


def title_stops_before_payoff(title: Any, quote: Any) -> bool:
    """True when a title made of the quote's words carries only its setup.

    "Some people keep you close enough to need you" loses "but never close
    enough to choose you". A title in new words is not judged: it may carry
    the point without the quote's own words.
    """

    flat_quote = _fold_marks(quote)
    punchline = quote_punchline(flat_quote)
    if not punchline:
        return False
    cut = flat_quote.casefold().rfind(punchline.casefold()[:40])
    # A run of the quote's own words that ends before the punchline begins
    # stops before it, whatever words the punchline uses ("For some reason, I
    # never thought there would be an after you" | "But there was, and I was in it").
    run = _quote_run(title, flat_quote)
    if run and cut > 0:
        return run[1] <= len(_quote_tokens(flat_quote[:cut]))
    setup_roots = {_quality_root(word) for word in _meaningful_words(flat_quote[:cut] if cut > 0 else "")}
    payoff_roots = {_quality_root(word) for word in _meaningful_words(punchline)} - setup_roots
    if not setup_roots or not payoff_roots:
        return False
    title_roots = [_quality_root(word) for word in _meaningful_words(_fold_marks(title_body(title)))]
    hits = [root for root in title_roots if root in setup_roots or root in payoff_roots]
    if len(hits) < 2 or len(hits) / max(len(title_roots), 1) < 0.5:
        return False
    return not any(root in payoff_roots for root in title_roots)


# A wish or a hope states what is not so; its title may say so plainly. Only
# the verb does: "Never give up hope" denies giving up, and a title may not
# drop its "never".
_COUNTERFACTUAL_RE = re.compile(
    r"\b(?:i|we)\s+(?:(?:still|just|really|only|always|so|truly)\s+)?(?:wish(?:ed)?|hoped?)\b"
    r"|^\W*wish(?:ed)?\b|\b(?:wishing|hoping|if only)\b",
    re.IGNORECASE,
)


def _has_negator(tokens: list[str]) -> bool:
    return any(is_negator(token) for token in tokens)


def _negated_at(tokens: list[str], position: int) -> bool:
    return _has_negator(tokens[max(0, position - 2):position])


def _asserts_denied_words(title_tokens: list[str], quote: str) -> bool:
    """Whether the title states, without a negation, three or more words a clause of the quote denies.

    "Because you stopped caring, you lose them ..." keeps "because you
    stopped caring" from "You don't lose people because you stopped caring"
    and drops its "don't". Words the quote also affirms elsewhere are its own.
    """

    clauses = [unicode_words(part, min_length=1) for part in re.split(r"[,.;:!?]+|\s[-–—]\s", quote)]
    affirmed = [f" {' '.join(words)} " for words in clauses if not _has_negator(words)]
    title_text = f" {' '.join(title_tokens)} "
    for words in clauses:
        denied_at = next((index for index, word in enumerate(words) if is_negator(word)), None)
        predicate = words[denied_at + 1:] if denied_at is not None else []
        for size in range(len(predicate), 2, -1):
            for start in range(len(predicate) - size + 1):
                phrase = " ".join(predicate[start:start + size])
                if (
                    f" {phrase} " in title_text and len(_meaningful_words(phrase)) >= 2
                    and not any(f" {phrase} " in other for other in affirmed)
                ):
                    return True
    return False


def title_reverses_quote(title: Any, quote: Any) -> bool:
    """True when the title negates, or un-negates, a verb or claim it shares with the quote.

    "Why I finally stopped loving you" reverses "I never stopped loving
    you"; "Giving up on someone never happens overnight" keeps "You don't
    give up overnight on someone", its negation carried by another word.
    A word the quote both denies and affirms ("it's not about who knows you
    ... it's more about who makes you seen") is not reversed by either use.
    A question may rephrase a question ("Did I deserve the bare minimum?"
    for "didn't I deserve ...?"), and a wish may be stated plainly.
    """

    body = _fold_marks(title_body(title))
    flat_quote = _fold_marks(quote)
    if ("?" in body and "?" in flat_quote) or _COUNTERFACTUAL_RE.search(flat_quote):
        return False
    quote_tokens = unicode_words(flat_quote, min_length=1)
    title_tokens = unicode_words(body, min_length=1)
    quote_negates = _has_negator(quote_tokens)
    title_negates = _has_negator(title_tokens)
    if not title_negates and _asserts_denied_words(title_tokens, flat_quote):
        return True
    meaningful = set(_meaningful_words(flat_quote)) & set(_meaningful_words(body))
    for word in meaningful:
        root = _quality_root(word)
        quote_uses = [_negated_at(quote_tokens, i) for i, token in enumerate(quote_tokens) if _quality_root(token) == root]
        title_uses = [_negated_at(title_tokens, i) for i, token in enumerate(title_tokens) if _quality_root(token) == root]
        if not quote_uses or not title_uses:
            continue
        if all(quote_uses) and not any(title_uses) and not title_negates:
            return True
        if all(title_uses) and not any(quote_uses) and not quote_negates:
            return True
    return False


def quote_title_issues(title: Any, quote: Any, *, index: int | None = None) -> list[dict[str, Any]]:
    """The pass/fail checks of a quote Short's title.

    The quote itself, its punchline clause, and a title in new words all
    pass. A title fails when it cuts the quote mid-phrase or ends in "…",
    stops before the quote's turn, reverses the quote's meaning, or is a
    "<keyword> quotes for ..." search construction. Its length is judged on
    the package (30-70 characters for a GREEN verdict); YouTube's own
    100-character limit rejects a title outright.
    """

    issues: list[dict[str, Any]] = []
    body = title_body(title)
    if title_cuts_quote(body, quote):
        issues.append(_issue(
            "quote_title_cut", "title",
            "Title cuts the quote mid-phrase or ends in an ellipsis; use the whole quote, its punchline clause, or new words.",
            index=index,
        ))
    if title_stops_before_payoff(body, quote):
        issues.append(_issue(
            "missing_quote_payoff", "title",
            "Title stops before the quote's turn; keep the idea after it.", index=index,
        ))
    if title_reverses_quote(body, quote):
        issues.append(_issue(
            "reversed_quote_meaning", "title",
            "Title reverses the quote's meaning by negating, or dropping the negation of, a claim it shares with the quote.",
            index=index,
        ))
    if _keyword_quotes_title(body, quote):
        issues.append(_issue(
            "keyword_quotes_title", "title",
            "A quote Short's title carries the quote's feeling, not a '<keyword> quotes for ...' search phrase.",
            index=index,
        ))
    return issues


def safe_quote_title(quote: Any) -> str:
    """The quote as a title that passes this gate's own title checks.

    Whole when it fits, else its best complete span (source_cues.quote_title),
    chosen with the checks a quote Short's title is judged by here, so a
    fallback never ships a title the gate would reject as cut, stopped before
    its turn, reversed, ungrammatical or too vague.
    """

    flat = normalize_unicode(quote)
    brief = {"exact_quote": flat, "video_format": "youtube_shorts"}
    feelings = _feeling_keys(flat)

    def passes(title: str) -> bool:
        return not (
            quote_title_issues(title, flat)
            or title_fluency_issues(title, quote=flat)
            or _title_usefulness_issues(
                title, flat, brief, True, [], index=0, source_overlap_supported=True, feelings=feelings,
            )
            or (len(unicode_words(title)) < 2 and not _is_whole_quote(title, flat))
        )

    return quote_title(flat, accept=passes)


def _is_whole_quote(title: Any, quote: Any) -> bool:
    """Whether a title is the complete quote, emoji, #shorts and punctuation aside ("Breathe" for "Breathe.")."""

    words = unicode_words(_fold_marks(title_body(title)), min_length=1)
    return bool(words) and words == unicode_words(_fold_marks(quote), min_length=1)


def short_title_fit(title: Any, quote: Any, source: Any = "") -> int:
    """How well a quote Short's title carries the quote, 0-100. Deterministic.

    A Short is found in the feed more than in search, so its titles are ranked
    by hook, clarity and emotional fit: faithful to the quote's meaning (two of
    its words are enough), keeping the feeling it names, voicing it or
    speaking to the viewer, 30-70 characters. Words only the scene supplies
    ("A rainy night walk"), "<keyword> quotes for ..." constructions, titles
    that cut the quote or stop before its turn rank lower; one that reverses
    it ranks lowest. The whole quote, or its punchline clause, is a full
    title. Search phrases only break ties, in the caller.
    """

    body = title_body(title)
    words = _meaningful_words(body)
    quote_roots = {_quality_root(word) for word in _meaningful_words(quote)}
    if not words or not quote_roots:
        return 0
    scene_roots = {
        _quality_root(word) for word in _meaningful_words(source)
        if word not in _NOTE_LABEL_WORDS and not _shares_root(word, quote_roots)
    }
    quote_hits = sum(1 for word in words if _shares_root(word, quote_roots))
    scene_hits = sum(1 for word in words if not _shares_root(word, quote_roots) and _quality_root(word) in scene_roots)
    quote_feelings = _feeling_keys(quote)
    score = 30 * min(quote_hits / 2, 1.0)
    score += 20 if not quote_feelings or quote_feelings & _feeling_keys(body) else 0
    score += 10 if _VOICE_RE.search(body) else 0
    score += 20 if 30 <= len(body) <= 70 else 10 if 20 <= len(body) <= 80 else 0
    score += 0 if title_cuts_quote(body, quote) else 20
    score -= 15 * min(scene_hits, 2)
    score -= 25 if _keyword_quotes_title(body, quote) else 0
    score -= 20 if title_stops_before_payoff(body, quote) else 0
    # Faithfulness is a gate, not one part of the sum: a well-made title about
    # something else ("Why you should never text your ex again") is not this quote's.
    if not quote_hits:
        score = min(score, 30)
    if title_reverses_quote(body, quote):
        score = min(score, 20)
    return int(round(max(0.0, min(100.0, score))))


def candidate_mechanism(title: str) -> str:
    """Describe a title mechanism without pretending it predicts performance."""

    lowered = normalize_unicode(title).casefold()
    if re.search(r"\bhow (?:to|i)\b|\bguide\b|\bsteps?\b|\btips?\b", lowered):
        return "practical utility"
    if "?" in title or re.search(r"\bwhy\b|\bwhat\b|\bhow\b", lowered):
        return "explanation"
    if re.search(r"\bvs\.?\b|\bcompared?\b|\bbetter\b", lowered):
        return "comparison"
    if re.search(r"\bmistake\b|\bwrong\b|\bmyth\b|\bmisconception\b", lowered):
        return "misconception correction"
    if re.search(r"\bafter\b|\bbefore\b|\bbecame\b|\bchanged\b|\bfrom .+ to\b", lowered):
        return "transformation"
    if re.search(r"\btruth\b|\bsecret\b|\bhidden\b|\bnobody\b", lowered):
        return "hidden mechanism"
    if re.search(r"\bdeserve\b|\bhurts?\b|\bsilence\b|\bheart\b|\bfeel\b", lowered):
        return "emotional tension"
    return "direct topic framing"


def is_short_content(script: str, creator_brief: dict[str, Any] | None = None) -> bool:
    """Whether the video is a Short; see source_cues.is_short_video, the one resolver."""

    # The structured brief preserves the creator's original source; the caller's
    # `script` can be an expanded research query.
    return is_short_video(script, creator_brief)


def is_silent_quote_only_short(script: str, creator_brief: dict[str, Any] | None = None) -> bool:
    """Identify a quote-led Short that does not supply instructional content."""

    brief = creator_brief or {}
    # Prefer the creator's preserved source to the expanded request/query text.
    # The latter is a research aid, not evidence that the video teaches anything.
    source = normalize_unicode(brief.get("content") or script)
    quote = normalize_unicode(brief.get("exact_quote") or brief.get("on_screen_text")) or source_quote(source, brief)
    return bool(
        quote
        and normalize_unicode(brief.get("voice_over")).casefold() == "none"
        and is_short_content(source, brief)
        and not source_supports_instructional_framing(source, brief)
    )


def source_supports_instructional_framing(script: str, creator_brief: dict[str, Any] | None = None) -> bool:
    """Return whether the creator source actually supports teaching/advice framing."""

    brief = creator_brief or {}
    source = normalize_unicode(brief.get("content") or script)
    quote = normalize_unicode(brief.get("exact_quote") or brief.get("on_screen_text"))
    if quote and quote.casefold() == source.casefold():
        return False
    context = " ".join(normalize_unicode(brief.get(field)) for field in (
        "video_format", "creator_intent", "content_constraints", "viewer_promise",
    ))
    if _INSTRUCTIONAL_CONTEXT_RE.search(context) or _INSTRUCTIONAL_SOURCE_RE.search(source):
        return True
    # A procedural source can be instructional even when the creator labels it
    # as a Short rather than a tutorial (for example, check/inspect/adjust).
    actions = _PROCEDURAL_ACTION_RE.findall(source)
    return len(actions) >= 2 and bool(re.search(r"\b(?:if|then|to)\b", source, re.IGNORECASE))


def source_requires_noninstructional_framing(script: str, creator_brief: dict[str, Any] | None = None) -> bool:
    """Identify source-bound silent, story, and reflection content that cannot become a guide."""

    brief = creator_brief or {}
    if is_silent_quote_only_short(script, brief):
        return True
    if (
        normalize_unicode(brief.get("exact_quote") or brief.get("on_screen_text"))
        and not source_supports_instructional_framing(script, brief)
    ):
        return True
    context = " ".join(normalize_unicode(brief.get(field)) for field in (
        "creator_intent", "content_constraints", "visual_requirements",
    ))
    return bool(
        re.search(r"\b(?:story|storytelling|reflection|reflective|minimal|cinematic|narrative)\b", context, re.IGNORECASE)
        or re.search(r"\bnot\s+(?:a\s+)?(?:tutorial|guide|advice|therapy)\b", context, re.IGNORECASE)
    ) and not source_supports_instructional_framing(script, brief)


def source_withholds_message_content(script: str, creator_brief: dict[str, Any] | None = None) -> bool:
    """Identify story sources that mention an unread message but do not supply its words."""

    brief = creator_brief or {}
    source = normalize_unicode(brief.get("content") or script)
    mentions_short_message = bool(re.search(
        r"\bmessage\b.*?\b(?:only|just)?\s*(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+words?\b",
        source,
        re.IGNORECASE,
    ))
    quoted_content = bool(re.search(r'["\u201c][^"\u201d]{1,80}["\u201d]', source))
    return mentions_short_message and not quoted_content


def has_unsupported_instructional_framing(value: Any, source: Any = "") -> bool:
    """Return whether text promises instruction a silent quote does not contain.

    Wording carried over from the creator source is reproduction, not an added claim.
    The guard matches bare verbs such as "explain", so a quote like "easier than
    explaining why I'm sad" would otherwise be rejected for containing its own words
    while the silent-quote rules simultaneously require reproducing it verbatim.
    Mirrors the source check already used by _unsupported_claims.
    """

    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", normalize_unicode(value).replace("#", " "))
    matches = _UNSUPPORTED_INSTRUCTIONAL_RE.findall(text)
    if not matches:
        return False
    source_text = normalize_unicode(source).casefold()
    if not source_text:
        return True
    return any(match.casefold() not in source_text for match in matches)


def filter_source_hashtags(
    hashtags: Iterable[str], script: str, creator_brief: dict[str, Any] | None = None,
) -> list[str]:
    """Drop instructional hashtags when the creator source is non-instructional."""

    values = [normalize_unicode(item) for item in hashtags if normalize_unicode(item)]
    if not source_requires_noninstructional_framing(script, creator_brief):
        return values
    return [item for item in values if not has_unsupported_instructional_framing(item, script)]


# Platform words carry no subject; "quotes" and "sad" are the niche's own
# established hashtags (#quotes, #SadLoveQuotes) and are kept.
_SHORT_HASHTAG_GENERIC = {"short", "shorts", "yt", "youtube", "video", "viral", "trending", "fyp"}
# Search intent reads badly at the front of a hashtag, and a trailing context
# phrase adds nothing: "#HowToMakeMangoIceCream" says less than "#MangoIceCream".
_HASHTAG_LEADING_INTENT = {"how", "to", "make", "making", "easy", "instant", "best", "simple", "quick"}
_HASHTAG_CONNECTIVES = {"of", "the", "a", "an", "and", "in", "for", "with", "at", "to", "on", "my", "your"}
# The hashtag viewers of the quote niche follow for a feeling, by the root of
# the quote's own feeling word; longer roots first so "forgiv" is not "forg".
# A heart is not a broken one: "A grateful heart is a happy heart" and "Follow
# your heart" were tagged #heartbreak.
_FEELING_HASHTAGS = (
    ("heartbr", "#heartbreak"), ("heartach", "#heartbreak"), ("broken", "#heartbreak"), ("forgiv", "#forgiveness"),
    ("lov", "#love"), ("miss", "#missingyou"), ("alon", "#loneliness"),
    ("lone", "#loneliness"), ("sile", "#silence"), ("trus", "#trust"), ("betr", "#betrayal"),
    ("heal", "#healing"), ("forg", "#memories"), ("memo", "#memories"), ("good", "#goodbye"),
    ("dese", "#selfworth"), ("regr", "#regret"), ("sad", "#sadquotes"), ("cry", "#sadquotes"),
    ("tear", "#sadquotes"), ("pain", "#sadquotes"), ("hurt", "#sadquotes"), ("soul", "#deepquotes"),
    ("happ", "#happiness"),
)


def feeling_hashtag(quote: Any) -> str:
    """The established hashtag for the first feeling a quote names and does not deny ("Don't cry"), or ""."""

    for word in affirmed_feeling_words(quote):
        root = _quality_root(word)
        for prefix, hashtag in _FEELING_HASHTAGS:
            # The word as written too: "missing" has the root "mis".
            if root.startswith(prefix) or word.startswith(prefix):
                return hashtag
    return ""


def _hashtag_words(hashtag: str) -> list[str]:
    """The words of "#SadLoveQuotes" or "#heartbreak"; a PascalCase hashtag is read at its capitals."""

    body = str(hashtag or "").lstrip("#")
    return re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+", body) or ([body] if body else [])


# A lowercase hashtag cannot be read at its capitals. A single word longer than
# this is a coined phrase ("#lettinggoofthewrongperson"), not a word such as
# "#forgiveness" or "#heartbreak".
_LONGEST_HASHTAG_WORD = 14


def _hashtag_length(hashtag: str) -> int:
    """Words in a hashtag, numbers aside: "#2IngredientIceCream" has three, "#WaitingOnAnEmptyRoad" five.

    An unreadable run of lowercase letters is counted at about seven letters a
    word: "#relationshipquotes" is a compound, "#lettinggoofthewrongperson" too long.
    """

    words = [word for word in _hashtag_words(hashtag) if not word.isdigit()]
    if len(words) == 1 and words[0].isascii() and len(words[0]) > _LONGEST_HASHTAG_WORD:
        return -(-len(words[0]) // 7)
    return len(words)


def focused_short_hashtags(
    tags: Iterable[str], casing: dict[str, str] | None = None, *, quote: Any = "", proposed: Iterable[str] = (),
) -> list[str]:
    """#shorts, then at most two hashtags viewers actually follow.

    For a quote Short that is #quotes and the quote's feeling (#heartbreak,
    #selfworth), or the writer's proposal when it is a real word. A compound
    coined from a tag ("#VulnerabilityHangover", "#HowToKnowIfSomeoneValuesYou")
    is one nobody follows: at most one compound is used, never longer than
    three words, and only when no established hashtag fills the slot.
    """

    result = ["#shorts"]
    compound_used = False

    def push(hashtag: str) -> None:
        nonlocal compound_used
        hashtag = normalize_hashtag(hashtag)
        words = _hashtag_words(hashtag)
        if not hashtag or not words or len(hashtag) > 30 or len(result) >= 3:
            return
        if any(word.casefold() in _SHORT_HASHTAG_GENERIC for word in words):
            return
        length = _hashtag_length(hashtag)
        if length > 3 or (length > 1 and compound_used):
            return
        if any(_hashtag_overlaps(hashtag, item) for item in result):
            return
        result.append(hashtag)
        compound_used = compound_used or length > 1

    proposals = [str(item) for item in proposed if str(item or "").strip()]
    quote_text = normalize_unicode(quote)
    if quote_text:
        push("#quotes")
        # A writer's proposal names a feeling the quote must carry: "#Heartbreak"
        # on "Didn't I deserve the bare minimum?" is a theme nobody chose.
        quote_stems = {word[:4] for word in unicode_words(quote_text) if len(word) >= 3}
        proposals = [
            item for item in proposals
            if any(word.casefold()[:4] in quote_stems for word in _hashtag_words(item) if len(word) >= 3)
        ]
    # The feeling the quote names first (#selfworth, #heartbreak), then a single
    # real word the writer proposed, then its compound, then one from a validated tag.
    push(feeling_hashtag(quote))
    for item in proposals:
        if _hashtag_length(item) == 1:
            push(item)
    for item in proposals:
        push(item)
    for tag in tags:
        words = [word for word in re.findall(r"[A-Za-z0-9]+", str(tag)) if word.casefold() not in _SHORT_HASHTAG_GENERIC]
        while words and words[0].casefold() in _HASHTAG_LEADING_INTENT:
            words = words[1:]
        if len(words) >= 3 and words[-2].casefold() in {"at", "in", "for", "with"}:
            words = words[:-2]  # "... at home", "... in tamil"
        # A phrase of more than three words is skipped, not truncated
        # ("#LettingGoOfTheWrongPerson" is coined; cutting "2 ingredient ice
        # cream" would give #2IngredientIce). push() applies the limit.
        content_words = [word for word in words if word.casefold() not in _HASHTAG_CONNECTIVES]
        if not content_words:
            continue
        words = [(casing or {}).get(word.casefold(), word) for word in words]
        push("#" + "".join(word if word[:1].isupper() or word[:1].isdigit() else word[:1].upper() + word[1:] for word in words))
    return result


def _hashtag_overlaps(left: str, right: str) -> bool:
    a, b = left.casefold().lstrip("#"), right.casefold().lstrip("#")
    return a == b or a.startswith(b) or b.startswith(a)


def title_emojis(value: Any) -> list[str]:
    """Return visible emoji bases for deterministic count/template checks."""

    return _TITLE_EMOJI_RE.findall(normalize_unicode(value))


def evaluate_package_quality(
    package: dict[str, Any],
    *,
    script: str,
    creator_brief: dict[str, Any] | None = None,
    language: str = "english",
    recent_titles: Iterable[str] | None = None,
    published_titles: Iterable[str] | None = None,
    tag_context: Any = None,
    tag_evidence: dict[str, Any] | None = None,
    competitor_titles: Iterable[str] | None = None,
    enforce_final_tag_rules: bool = True,
) -> dict[str, Any]:
    """Return a structured, deterministic quality decision for one package."""

    brief = creator_brief or {}
    source = normalize_unicode(script or brief.get("content"))
    exact_quote = source_quote(source, brief)
    is_short = is_short_content(source, brief)
    silent_quote_only = is_silent_quote_only_short(source, brief)
    non_instructional = source_requires_noninstructional_framing(source, brief)
    # An emoji is optional; when one is used it matches the feeling the quote
    # names, not the footage ("🚦" for a road), so only a named feeling
    # recommends one.
    emoji_recommended = is_short and bool(feeling_words(exact_quote or source))
    quote_feelings = _feeling_keys(exact_quote or source)
    requested_language = normalize_unicode(language).casefold() or "english"

    title_values = [package.get("title"), *(package.get("variants") or [])]
    titles = _unique([normalize_unicode(item) for item in title_values if normalize_unicode(item)])
    recent = [normalize_unicode(item) for item in (recent_titles or []) if normalize_unicode(item)]
    published = [normalize_unicode(item) for item in (published_titles or []) if normalize_unicode(item)]
    competitors = [normalize_unicode(item) for item in (competitor_titles or []) if normalize_unicode(item)]

    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for index, title in enumerate(titles):
        reasons: list[dict[str, Any]] = []
        shorts_count = len(_SHORTS_TITLE_RE.findall(title))
        emojis = title_emojis(title)
        # YouTube detects a Short by its format: #shorts in the title is
        # optional, never required and never injected.
        if shorts_count > 1:
            reasons.append(_issue("duplicate_shorts_title_hashtag", "title", "The title contains #shorts more than once.", index=index))
        elif not is_short and shorts_count:
            reasons.append(_issue("unexpected_shorts_title_hashtag", "title", "A non-Short title must not be labelled #shorts.", index=index))
        if len(title) > 100:
            reasons.append(_issue("title_too_long", "title", "The upload-ready title exceeds YouTube's 100-character limit.", index=index))
        if len(emojis) > 2:
            reasons.append(_issue("excessive_title_emojis", "title", "Use no more than two relevant emojis in a title.", index=index))
        if any(left == right for left, right in pairwise(emojis)):
            reasons.append(_issue("repeated_title_emoji", "title", "The title repeats the same emoji in sequence.", index=index))
        if emoji_recommended and not emojis:
            warnings.append(_issue(
                "missing_contextual_title_emoji", "title",
                "An emoji matching the quote's feeling is optional; it is not required for a source-faithful title.",
                severity="warning", index=index,
            ))
        if exact_quote and is_short:
            reasons.extend(quote_title_issues(title, exact_quote, index=index))
        signature = "".join(emojis)
        recent_signatures = ["".join(title_emojis(old)) for old in recent[-3:]]
        if signature and len(recent_signatures) == 3 and all(item == signature for item in recent_signatures):
            reasons.append(_issue("repeated_emoji_template", "title", "The emoji pattern repeats across the three most recent generated titles.", index=index))
        if any(pattern.search(title) for pattern in _GENERIC_TITLE_PATTERNS):
            reasons.append(_issue("generic_template", "title", "Title uses a repeatedly generic template.", index=index))
        reasons.extend(_title_usefulness_issues(
            title, source, brief, non_instructional, competitors, index=index,
            source_overlap_supported=requested_language not in {"tamil", "tanglish", "hindi"},
            feelings=quote_feelings,
        ))
        reasons.extend(title_fluency_issues(title, index=index, quote=exact_quote))
        reasons.extend(title_duration_issues(title, source, index=index))
        unsupported = _unsupported_claims(title, source)
        reasons.extend(_issue(code, "title", "Title introduces a claim not supported by the creator source.", index=index) for code in unsupported)
        if non_instructional and has_unsupported_instructional_framing(title, source):
            reasons.append(_issue("unsupported_instructional_framing", "title", "A non-instructional source must not be framed as advice, a guide, or instruction.", index=index))
        duplicate_index = next(
            (other for other, item in enumerate(accepted) if title_similarity(title, item["title"]) >= 0.82),
            None,
        )
        if duplicate_index is not None:
            reasons.append(_issue("semantic_duplicate", "title", f"Title is too similar to accepted candidate {duplicate_index + 1}.", index=index))
        if any(title_similarity(title, old) >= 0.88 for old in [*recent, *published]):
            reasons.append(_issue("recent_title_repetition", "title", "Title repeats a recent generated or published title pattern.", index=index))
        if requested_language == "tamil" and not _TAMIL_RANGE.search(title):
            reasons.append(_issue("language_mismatch", "title", "Tamil output title does not contain Tamil script.", index=index))
        if requested_language == "tanglish" and not _has_latin_or_tamil(title):
            reasons.append(_issue("language_mismatch", "title", "Tanglish title has no usable Roman or Tamil text.", index=index))
        # A one-word quote ("Breathe.") is its own complete title.
        if len(unicode_words(title)) < 2 and not (exact_quote and _is_whole_quote(title, exact_quote)):
            reasons.append(_issue("title_too_vague", "title", "Title does not contain enough meaningful text.", index=index))
        if reasons:
            rejected.append({"title": title, "issues": reasons})
        else:
            accepted.append({
                "title": title,
                "mechanism": candidate_mechanism(title),
                "source": "generated_suggestion",
            })

    description = description_prose(package.get("description"))
    if not description:
        issues.append(_issue("missing_description", "description", "Description is empty."))
    else:
        if re.search(r"(?i)\ba\s+(?:one|a|an|the)\s+(?:person|man|woman|boy|girl)\b", description):
            issues.append(_issue("broken_description_grammar", "description", "Description contains a duplicated article or production-note fragment."))
        exact_quote_text = re.sub(r"\s+", " ", exact_quote).strip()
        normalized_description = re.sub(r"\s+", " ", description).strip()
        if exact_quote and exact_quote_text not in normalized_description:
            issues.append(_issue("quote_fidelity", "description", "Description does not preserve the exact on-screen quote."))
        for code in _unsupported_claims(description, source):
            issues.append(_issue(code, "description", "Description introduces a claim not supported by the creator source."))
        if non_instructional and has_unsupported_instructional_framing(description, source):
            issues.append(_issue("unsupported_instructional_framing", "description", "A non-instructional source must not claim tips, advice, explanations, or instructional content absent from the source."))
        if _looks_like_tag_list(description):
            issues.append(_issue("tag_list_contamination", "description", "Description reads like a repeated SEO tag list."))
        if is_short and production_note_sentences(description, f"{exact_quote} {normalize_unicode(brief.get('topic'))}"):
            issues.append(_issue(
                "production_notes", "description",
                "A Short's description speaks to its viewers; remove production notes such as "
                "\"This video features ...\", \"on-screen text\", \"accompanied by\" or \"slow motion\".",
            ))
        issues.extend(_description_usefulness_issues(
            description, source, brief, non_instructional,
            source_overlap_supported=requested_language not in {"tamil", "tanglish", "hindi"},
            feelings=quote_feelings,
            # A short quote ("Keep going.") is a short description, not a vague one.
            carries_quote=bool(exact_quote and is_short and _carries_quote(description, exact_quote)),
        ))
        if normalize_unicode(brief.get("voice_over")).casefold() == "none" and re.search(
            r"\b(?:listen to|hear (?:me|the)|voice[- ]?over|narrat(?:e|ed|ion))\b", description, re.IGNORECASE
        ):
            issues.append(_issue("voice_over_contradiction", "description", "Description claims narration although the brief says no voice-over."))
        if requested_language == "tamil" and not _TAMIL_RANGE.search(description):
            issues.append(_issue("language_mismatch", "description", "Tamil output description does not contain Tamil script."))
        if requested_language == "tanglish" and not _has_latin_or_tamil(description):
            issues.append(_issue("language_mismatch", "description", "Tanglish description has no usable Roman or Tamil text."))

    # Tags play a minimal role in discovery (support.google.com/youtube/answer/146402)
    # and are advisory here: a bad tag is reported with its text and dropped
    # by apply_quality_gate, never a reason to repair or replace the package.
    tags = _unique([normalize_unicode(tag).casefold().lstrip("#") for tag in (package.get("tags") or [])])
    for tag in tags:
        if len(unicode_words(tag)) > 8 or "," in tag:
            warnings.append(_tag_note("tag_list_contamination", f"Tag is not one focused phrase: {tag}", tag=tag))
        if non_instructional and has_unsupported_instructional_framing(tag, source):
            warnings.append(_tag_note("unsupported_instructional_framing", f"Tag implies instruction not present in this source: {tag}", tag=tag))
        preferred_short_tag = is_short and tag in _PREFERRED_SHORT_TAGS
        if tag in _PLATFORM_TAGS and not preferred_short_tag:
            warnings.append(_tag_note("platform_tag_filler", f"Platform-format filler is not a useful video tag: {tag}", tag=tag))
    context_text = " ".join(normalize_unicode(item) for item in tag_context) if isinstance(tag_context, (list, tuple, set)) else normalize_unicode(tag_context)
    source_tokens = set(unicode_words(" ".join([
        source,
        *(normalize_unicode(brief.get(field)) for field in (
            "content", "exact_quote", "on_screen_text", "visual_requirements",
            "viewer_promise", "unique_angle", "topic", "creator_intent", "content_constraints",
        )),
    ]))) | set(unicode_words(context_text))
    source_tokens |= set(unicode_words(" ".join(
        str(item) for item in (brief.get("seo_research_targets") or []) if str(item).strip()
    )))
    selected_tag_evidence = {
        normalize_unicode(item.get("keyword")).casefold(): item
        for item in (tag_evidence or {}).get("selected_keywords", [])
        if isinstance(item, dict) and normalize_unicode(item.get("keyword"))
    }

    # A Latin search tag ("chettinad chicken biryani") is grounded in a Tamil
    # script (செட்டிநாடு சிக்கன் பிரியாணி) when it sounds the same. Literal
    # comparison made every English tag "unrelated" for Tamil sources, while the
    # prompt told the model to write English tags: Tamil videos could never pass.
    source_phonetic_keys = phonetic_keys([
        source, context_text,
        *(normalize_unicode(brief.get(field)) for field in ("content", "exact_quote", "on_screen_text", "topic")),
    ])

    def _tag_has_grounding(tag: str) -> bool:
        tag_words = set(unicode_words(tag))
        if tag_words & source_tokens:
            return True
        if any(phonetic_match(word, source_phonetic_keys) for word in tag_words):
            return True
        row = selected_tag_evidence.get(normalize_unicode(tag).casefold())
        return bool(row and int(row.get("source_support_score") or 0) >= 70)

    for tag in tags:
        if tag not in _GENERIC_FORMAT_TAGS and not _tag_has_grounding(tag):
            warnings.append(_tag_note("unrelated_tag", f"Tag is not grounded in the supplied topic: {tag}", tag=tag))
    if enforce_final_tag_rules:
        warnings.extend(_tag_provenance_issues(tags, tag_evidence))
    # What is left once the noted tags are dropped (apply_quality_gate).
    dropped_tags = {item.get("tag") for item in warnings if item.get("field") == "tags" and item.get("code") in _DROPPED_TAG_CODES}
    contextual_tags = [
        tag for tag in tags
        if tag not in _GENERIC_FORMAT_TAGS and tag not in dropped_tags and _tag_has_grounding(tag)
    ]
    if tags and not contextual_tags:
        # Sparse, not unsafe: the package is usable, but not a GREEN one.
        warnings.append(_issue(
            "non_contextual_tags", "tags",
            "No useful subject tag survived; creator-preferred platform tags do not substitute for topic evidence.",
            severity="warning",
        ))
    generic_count = sum(
        1 for tag in tags
        if tag in _GENERIC_FORMAT_TAGS and not (is_short and tag in _PREFERRED_SHORT_TAGS)
    )
    if generic_count and generic_count >= max(2, len(contextual_tags) + 1):
        warnings.append(_issue(
            "generic_tag_filler", "tags",
            "Generic platform tags outnumber subject-specific tags; the filler is dropped rather than the package padded.",
            severity="warning",
        ))

    # Hashtags are rebuilt from the validated tags and the quote's feeling for
    # a Short (focused_short_hashtags); a faulty one is dropped, not repaired.
    hashtags = [normalize_unicode(item) for item in (package.get("hashtags") or []) if normalize_unicode(item)]
    normalized_hashtags = [item.casefold().lstrip("#") for item in hashtags]
    if len(normalized_hashtags) != len(set(normalized_hashtags)):
        warnings.append(_issue("duplicate_hashtag", "hashtags", "Hashtags contain duplicates.", severity="warning"))
    if len(hashtags) > 3:
        warnings.append(_issue("excessive_hashtags", "hashtags", "Use no more than three focused hashtags.", severity="warning"))
    # A Short's hashtags are labels viewers follow (focused_short_hashtags).
    hashtag_word_limit = 3 if is_short else 4
    for hashtag in hashtags:
        if non_instructional and has_unsupported_instructional_framing(hashtag, source):
            warnings.append(_issue(
                "unsupported_instructional_framing", "hashtags",
                f"Hashtag implies instruction not present in this source: {hashtag}", severity="warning", hashtag=hashtag,
            ))
        if _hashtag_length(hashtag) > hashtag_word_limit:
            warnings.append(_issue(
                "hashtag_too_long", "hashtags",
                f"A hashtag is a short label viewers follow, never a coined phrase of more than {hashtag_word_limit} words: {hashtag}",
                severity="warning", hashtag=hashtag,
            ))

    if not accepted:
        issues.append(_issue("no_acceptable_title", "titles", "No title candidate passed the local quality gate."))
    elif len(accepted) < 3:
        warnings.append(_issue(
            "fewer_legitimate_alternatives",
            "titles",
            f"Only {len(accepted)} materially distinct title alternative(s) passed; the result was not padded.",
            severity="warning",
        ))

    semantic_quality = _final_semantic_quality(
        package=package,
        accepted=accepted,
        tags=tags,
        source=source,
        brief=brief,
        tag_evidence=tag_evidence,
        competitors=competitors,
        source_overlap_supported=requested_language not in {"tamil", "tanglish", "hindi"},
    )
    issues.extend(semantic_quality["critical_issues"])
    warnings.extend(semantic_quality["warnings"])

    all_errors = [*issues, *(reason for item in rejected for reason in item["issues"])]
    passed = not issues and bool(accepted)
    # RED is unsafe; YELLOW is usable but weak or sparse. Advisory notes (a
    # dropped tag, an optional emoji) decide nothing; a package left without
    # any subject tag is sparse.
    limited = any(item.get("code") in _LIMITING_WARNINGS and item.get("severity") == "warning" for item in warnings)
    verdict = (
        "RED" if not passed or semantic_quality["verdict"] == "RED"
        else "YELLOW" if semantic_quality["verdict"] == "YELLOW" or limited
        else "GREEN"
    )
    return {
        "status": "pass" if passed else "fail",
        "passed": passed,
        "repairable": bool(all_errors),
        "issues": issues,
        "warnings": warnings,
        "rejected_candidates": rejected,
        "accepted_candidates": accepted,
        "candidate_count": len(accepted),
        "requested_language": requested_language,
        "exact_quote_checked": bool(exact_quote),
        "required_shorts_tags_checked": False,
        "short_title_contract_checked": True,
        "emoji_context_recommended": emoji_recommended,
        "silent_quote_only_checked": silent_quote_only,
        "final_seo_quality": {**semantic_quality, "verdict": verdict},
        "verdict": verdict,
        "rules_version": "phase2g-v1",
    }


# Gate-level warnings that keep a passing package from GREEN.
_LIMITING_WARNINGS = {"non_contextual_tags"}
# Tag notes whose tag is dropped from the package rather than repaired.
_DROPPED_TAG_CODES = {
    "tag_list_contamination", "unsupported_instructional_framing", "platform_tag_filler", "unrelated_tag",
    "missing_tag_provenance", "invalid_tag_provenance", "weak_research_tag_support", "weak_combined_tag_support",
    "missing_tag_support",
}


def apply_quality_gate(package: dict[str, Any], gate: dict[str, Any]) -> dict[str, Any]:
    """Apply accepted candidates and drop the tags and hashtags the gate noted.

    Nothing is manufactured in their place: a package with fewer tags is
    better than one repaired or replaced over a tag.
    """

    cleaned = dict(package)
    accepted = [item["title"] for item in gate.get("accepted_candidates", []) if item.get("title")]
    if accepted:
        cleaned["title"] = accepted[0]
        cleaned["variants"] = accepted
    notes = [item for item in gate.get("warnings") or [] if isinstance(item, dict)]
    dropped_tags = {
        str(item.get("tag")) for item in notes if item.get("field") == "tags" and item.get("code") in _DROPPED_TAG_CODES and item.get("tag")
    }
    if dropped_tags:
        cleaned["tags"] = [
            tag for tag in (package.get("tags") or [])
            if normalize_unicode(tag).casefold().lstrip("#") not in dropped_tags
        ]
    dropped_hashtags = {
        str(item.get("hashtag")).casefold() for item in notes if item.get("field") == "hashtags" and item.get("hashtag")
    }
    hashtags: list[str] = []
    seen: set[str] = set()
    for item in package.get("hashtags") or []:
        value = normalize_unicode(item)
        key = value.casefold()
        if not value or key in seen or key in dropped_hashtags:
            continue
        seen.add(key)
        hashtags.append(value)
    if hashtags != list(package.get("hashtags") or []) or len(hashtags) > 3:
        cleaned["hashtags"] = hashtags[:3]
    cleaned["quality_gate"] = gate
    return cleaned


def _title_usefulness_issues(
    title: str,
    source: str,
    brief: dict[str, Any],
    non_instructional: bool,
    competitors: Iterable[str],
    *,
    index: int,
    source_overlap_supported: bool,
    feelings: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Reject valid-looking titles that do not describe this actual video."""

    issues: list[dict[str, Any]] = []
    clean = re.sub(r"(?<![\w#])#shorts(?!\w)", "", normalize_unicode(title), flags=re.IGNORECASE)
    words = _meaningful_words(clean)
    source_words = _source_words(source, brief)
    sparse_source = len(_meaningful_words(source)) <= 2
    if re.search(r"(?i)^\s*(?:how\s+to\s+)?(?:the\s+)?(?:quote\s+)?is\s*[-:]", clean):
        issues.append(_issue("malformed_title_fragment", "title", "Title starts with a creator-input marker instead of natural viewer-facing language.", index=index))
    if re.search(r"(?i)\b(?:used\s+talk\s+every\s+then|quote\s+on\s+(?:the\s+)?(?:reel|screen)|background\s+(?:of\s+the\s+video\s+)?is)\b", clean):
        issues.append(_issue("creator_instruction_leakage", "title", "Title contains parsed input instructions or an unnatural keyword fragment.", index=index))
    if len(words) < 3 and not (sparse_source and words):
        issues.append(_issue("title_too_vague", "title", "Title is too short to identify a useful topic.", index=index))
    if words and words[0] in {"and", "but", "or", "with", "from", "about", "the"}:
        issues.append(_issue("title_fragment", "title", "Title starts like a sentence fragment.", index=index))
    if words and words[-1] in {"and", "but", "or", "with", "from", "about", "to", "for"}:
        issues.append(_issue("title_fragment", "title", "Title ends like a sentence fragment.", index=index))
    invented = _invented_context_terms(
        words, source_words, reflective=_is_reflective_source(brief, non_instructional), feelings=feelings,
    )
    if invented:
        issues.append(_issue(
            "unsupported_context", "title",
            f"Title adds context the creator source never mentions: {', '.join(invented)}.",
            index=index,
        ))
    if _MOVED_ON_PERSON_RE.search(clean) and not re.search(r"\b(?:move|moves|moved|moving) on\b", source, re.IGNORECASE):
        issues.append(_issue("invented_story_detail", "title", "Title invents that another person moved on.", index=index))
    if re.search(r"\b(?:prompt|creator instruction|video concept|without inventing|do not invent)\b", clean, re.IGNORECASE) or narrates_process(clean):
        issues.append(_issue("creator_instruction_leakage", "title", "Title exposes internal creator instructions.", index=index))
    if re.search(r"\bthinking out loud\b", clean, re.IGNORECASE) and not re.search(r"\bthinking out loud\b", source, re.IGNORECASE):
        issues.append(_issue("unsupported_action", "title", "Title invents spoken thoughts that are not supplied by the creator.", index=index))
    if re.search(r"\bheavy comfort\b", clean, re.IGNORECASE):
        issues.append(_issue("unnatural_title_phrase", "title", "Title uses an unnatural emotional phrase.", index=index))
    if re.search(r"\bheart and soul friendship\b", clean, re.IGNORECASE):
        issues.append(_issue("unnatural_title_phrase", "title", "Title combines an idiom and topic into an unnatural phrase.", index=index))
    # Another form of a source word anchors a title too ("explanation" for
    # "explaining"), as short_title_fit reads it.
    source_roots = {_quality_root(word) for word in source_words}
    if source_overlap_supported and words and source_words and not any(_shares_root(word, source_roots) for word in words):
        issues.append(_issue("title_not_source_specific", "title", "Title has no meaningful anchor in the creator source.", index=index))
    for competitor in competitors:
        if title_similarity(clean, competitor) >= 0.94:
            issues.append(_issue("competitor_title_copy", "title", "Title is too close to a researched YouTube result.", index=index))
            break
    # The source's own words are reproduction, not added framing: "people who
    # had no clue how to hold you" is a quote, not a how-to.
    framing = re.findall(r"\b(?:how to|tips?|methods?|guide|learn|complete)\b", clean, re.IGNORECASE)
    if non_instructional and any(term.casefold() not in normalize_unicode(source).casefold() for term in framing):
        issues.append(_issue("unsupported_instructional_framing", "title", "Title applies instructional framing unsupported by this source.", index=index))
    return issues


def _description_usefulness_issues(
    description: str,
    source: str,
    brief: dict[str, Any],
    non_instructional: bool,
    *,
    source_overlap_supported: bool,
    feelings: set[str] | None = None,
    carries_quote: bool = False,
) -> list[dict[str, Any]]:
    """Require a concise, source-faithful description rather than harmless filler."""

    issues: list[dict[str, Any]] = []
    words = _meaningful_words(description)
    source_words = _source_words(source, brief)
    overlap = set(words) & source_words
    if re.search(
        r"(?i)\b(?:the\s+)?(?:quote|background|visuals?)\s+(?:on\s+(?:the\s+)?(?:reel|screen)\s+)?is\s*[-:]",
        description,
    ):
        issues.append(_issue("creator_instruction_leakage", "description", "Description exposes creator-facing input labels instead of audience-facing copy."))
    if narrates_process(description):
        issues.append(_issue(
            "creator_instruction_leakage", "description",
            "Description narrates the writing rules ('without adding stories', 'the exact emotional idea'); describe the video instead.",
        ))
    if len(words) < 3 and not carries_quote:
        issues.append(_issue("description_too_thin", "description", "Description does not identify the actual video."))
    if source_overlap_supported and words and source_words and not overlap:
        issues.append(_issue("description_not_source_specific", "description", "Description has no meaningful anchor in the creator source."))
    invented = _invented_context_terms(
        words, source_words, reflective=_is_reflective_source(brief, non_instructional), feelings=feelings,
    )
    if invented:
        issues.append(_issue(
            "unsupported_context", "description",
            f"Description adds context the creator source never mentions: {', '.join(invented)}. Remove or rephrase those words.",
        ))
    # A format the tool guessed is not one the creator declared.
    format_source = ((brief.get("field_provenance") or {}).get("video_format") or {}).get("source")
    declared_format = brief.get("video_format") if format_source in (None, "creator_supplied") else ""
    declared = source_words | set(_meaningful_words(declared_format))
    invented_formats = sorted(term for term in _SUPPLIED_ONLY_FORMATS if term in words and term not in declared)
    if invented_formats:
        issues.append(_issue(
            "invented_format", "description",
            f"Description calls the video a {', '.join(invented_formats)}, which the creator never said. Describe the content instead.",
        ))
    if _PRODUCTION_JARGON_RE.search(description):
        issues.append(_issue(
            "production_jargon", "description",
            "Description describes how the video was shot ('talking head', 'b-roll'); say what the viewer gets instead.",
        ))
    if _MOVED_ON_PERSON_RE.search(description) and not re.search(r"\b(?:move|moves|moved|moving) on\b", source, re.IGNORECASE):
        issues.append(_issue("invented_story_detail", "description", "Description invents that another person moved on."))
    if re.search(r"\b(?:the (?:creator|speaker) shares|my personal experience|our relationship story)\b", description, re.IGNORECASE):
        source_folded = normalize_unicode(source).casefold()
        if not any(phrase in source_folded for phrase in ("my personal experience", "our relationship", "the speaker", "the creator shares")):
            issues.append(_issue("invented_story_detail", "description", "Description invents a personal story or relationship detail."))
    if any(pattern.search(description) for pattern in _DESCRIPTION_BOILERPLATE):
        issues.append(_issue("generic_description_filler", "description", "Description uses generic AI-style framing instead of direct audience-facing copy."))
    if re.search(r"\bone[- ]sided\b", description, re.IGNORECASE) and not re.search(r"\b(?:one[- ]sided|bare minimum)\b", source, re.IGNORECASE):
        issues.append(_issue("invented_relationship_dynamic", "description", "Description invents a one-sided dynamic not stated by the creator."))
    if non_instructional and re.search(r"\b(?:this (?:video|short) (?:teaches|explains|breaks down)|learn how|here are \d+|tips? for)\b", description, re.IGNORECASE):
        issues.append(_issue("unsupported_instructional_framing", "description", "Description claims instruction the source does not provide."))
    return issues


def _tag_provenance_issues(tags: list[str], evidence: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Ensure final tags can be explained without trusting model/result text."""

    if evidence is None:
        return []
    selected = {
        normalize_unicode(item.get("keyword")).casefold(): item
        for item in evidence.get("selected_keywords", [])
        if isinstance(item, dict) and normalize_unicode(item.get("keyword"))
    }
    issues: list[dict[str, Any]] = []
    allowed = {"script_derived", "combined", "research_discovered", "creator_strategy"}
    for tag in tags:
        row = selected.get(normalize_unicode(tag).casefold())
        if not row:
            issues.append(_tag_note("missing_tag_provenance", f"Tag has no deterministic selection provenance: {tag}", tag=tag))
            continue
        provenance = str(row.get("source_classification") or "")
        if provenance not in allowed:
            issues.append(_tag_note("invalid_tag_provenance", f"Tag has unsupported provenance: {tag}", tag=tag))
        if provenance == "research_discovered" and int(row.get("source_support_score") or 0) < 70:
            issues.append(_tag_note("weak_research_tag_support", f"Research-derived tag lacks strong creator-source support: {tag}", tag=tag))
        if provenance == "combined" and int(row.get("source_support_score") or 0) < 50:
            issues.append(_tag_note("weak_combined_tag_support", f"Combined tag lacks sufficient creator-source support: {tag}", tag=tag))
        if not str(row.get("source_support") or "").strip():
            issues.append(_tag_note("missing_tag_support", f"Tag has no recorded source support: {tag}", tag=tag))
    return issues


# Words a quote Short's reflective line and soft call to action may add.
_SHORT_REFLECTION_WORDS = 10


def _carries_quote(text: str, quote: str) -> bool:
    """Whether the text contains the quote word for word (case, spacing and end punctuation aside)."""
    def flat(value: str) -> str:
        return " ".join(unicode_words(value, min_length=1)).casefold()

    return bool(flat(quote)) and f" {flat(quote)} " in f" {flat(text)} "


def _final_semantic_quality(
    *,
    package: dict[str, Any],
    accepted: list[dict[str, Any]],
    tags: list[str],
    source: str,
    brief: dict[str, Any],
    tag_evidence: dict[str, Any] | None,
    competitors: list[str],
    source_overlap_supported: bool,
) -> dict[str, Any]:
    """Score usefulness separately from structural validity.

    The score is a local quality explanation, not a CTR/ranking prediction.  A
    RED verdict represents a safety/usefulness failure; YELLOW means a usable
    but conservative package with a non-critical limitation.
    """

    title = str((accepted[0] if accepted else {}).get("title") or package.get("title") or "")
    description = description_prose(package.get("description"))
    source_words = _source_words(source, brief)
    title_words = set(_meaningful_words(title))
    description_words = set(_meaningful_words(description))
    source_roots = {_quality_root(word) for word in source_words}
    # Validated final tags are semantic bridges produced from the creator
    # source. Their terms let a natural paraphrase such as "emotional pain"
    # score as grounded even when the quote says "worst feeling" verbatim.
    # Platform tags and weakly supported rows never contribute.
    selected_tag_rows = [
        item for item in (tag_evidence or {}).get("selected_keywords", [])
        if isinstance(item, dict)
        and item.get("classification") != "platform_format"
        and int(item.get("source_support_score") or 0) >= 70
    ]
    source_roots |= {
        _quality_root(word) for item in selected_tag_rows
        for word in _meaningful_words(item.get("keyword"))
    }
    supported_title_words = {word for word in title_words if _quality_root(word) in source_roots}
    # A concise title needs room for one natural hook/modifier (for example
    # "weight" in "the emotional weight of being forgotten"). Unsupported
    # contexts are rejected above; treating one editorial word as missing
    # subject evidence made otherwise strong titles fail by 1-2 points.
    title_overlap = min(1.0, len(supported_title_words) / max(len(title_words) - 1, 1))
    description_overlap = len({word for word in description_words if _quality_root(word) in source_roots}) / max(min(len(description_words), 12), 1)
    title_score = _bounded_score(
        35 + title_overlap * 45 + (10 if 3 <= len(title_words) <= 12 else 0)
        + (10 if not any(title_similarity(title, item) >= 0.94 for item in competitors) else 0)
    )
    quote = normalize_unicode(brief.get("exact_quote") or brief.get("on_screen_text")) or source_quote(source, brief)
    short = is_short_content(source, brief)
    if quote and short:
        # A quote Short's title passes or fails the gate's checks (the quote
        # kept whole or to its punchline, no cut, no reversed meaning) and is
        # scored by how it carries the quote. Word overlap with the brief's
        # prose is not that measure: a brief phrase ("Deep emotional resonance
        # relatable truth and life") scored 100 while the quote itself scored 68.
        scene = " ".join([source, normalize_unicode(brief.get("visual_requirements"))])
        title_score = _bounded_score(60 + short_title_fit(title, quote, scene) * 0.4)
    if quote and short and _carries_quote(description, quote):
        # A quote Short's description is the exact quote and a line of
        # reflection for viewers, in new words by design: the verbatim quote
        # grounds it (production notes and unsupported claims are checked
        # apart). A longer passage in new words is still judged by overlap.
        reflection = description_words - set(_meaningful_words(quote))
        if len(reflection) <= _SHORT_REFLECTION_WORDS:
            description_overlap = 1.0
    description_score = _bounded_score(
        35 + min(description_overlap * 55, 45) + (10 if 4 <= len(description_words) <= 120 else 0)
    )
    # A score the local word-overlap matcher cannot measure is reported as not
    # measured, with the reason. It used to be raised to 70 (60 for a sparse
    # source) and shown as if it had been measured.
    not_measured: dict[str, str] = {}
    if not source_overlap_supported:
        reason = "The local word-overlap check reads English word forms and cannot judge this language."
        not_measured["title_score"] = not_measured["description_score"] = reason
    elif len(source_words) <= 1 and description_words:
        not_measured["description_score"] = "The source has too few words to check the description against."
    # Overlap alone cannot tell a sentence from word salad built out of the
    # same words, so a title with broken word order is capped regardless.
    fluency_issues = title_fluency_issues(title, quote=quote) if title else []
    duration_issues = title_duration_issues(title, source) if title else []
    if fluency_issues or duration_issues:
        title_score = min(title_score, 35.0)
    # Search usefulness: the strongest validated search phrase should appear in
    # the title, ideally in its first few words where it is never truncated.
    primary_phrase = primary_search_phrase(tag_evidence)
    placement = keyword_placement(title, primary_phrase)
    if placement in {"missing", "late"}:
        # "SIP vs lump sum: ..." leads with a real search that names the
        # subject; it is not missing its keyword because the single chosen
        # phrase was "nifty 50 index fund returns".
        if any(keyword_placement(title, phrase) == "front" for phrase in strong_search_phrases(tag_evidence)):
            placement = "front"
    # A quote Short is found in the feed more than in search: its title carries
    # the quote's feeling, and a search phrase is only a secondary factor.
    # Tags play a minimal role in a Short's discovery
    # (support.google.com/youtube/answer/146402). Both are still reported, as
    # notes that do not decide a Short's verdict.
    keyword_severity = "info" if short and quote else "warning"
    tag_severity = "info" if short else "warning"
    if keyword_severity == "warning":
        # The most specific truthful title wins: one that names the subject in
        # its own words loses little for leaving out the main search phrase,
        # and nothing for placing it late. The old -12/-4 made "Download and
        # install OBS Studio for YouTube live streaming" (a 90-second section)
        # outrank "My exact OBS settings for streaming smoothly on YouTube".
        title_score -= 6 if placement == "missing" else 0
    title_score = _bounded_score(title_score)
    tag_keys = {normalize_unicode(tag).casefold() for tag in tags}
    selected_rows = [
        item for item in (tag_evidence or {}).get("selected_keywords", [])
        if isinstance(item, dict) and normalize_unicode(item.get("keyword")).casefold() in tag_keys
    ]
    topic_rows = [item for item in selected_rows if item.get("classification") != "platform_format"]
    # The measured relevance of each subject tag. A tag viewers search is
    # reported as such in the keyword research; raising its score to 90 here
    # reported a number that was never measured.
    tag_scores = [float(item.get("keyword_relevance_score") or 0) for item in topic_rows]
    tag_score = round(sum(tag_scores) / len(tag_scores), 1) if tag_scores else None
    if tag_score is None:
        not_measured["tag_score"] = "No subject tag was selected, so there is no tag to score."
    title_description_agree = bool(
        {_quality_root(word) for word in title_words} & {_quality_root(word) for word in description_words}
    ) or not title_words or not description_words
    supported_tags = all(int(item.get("source_support_score") or 0) >= 50 for item in selected_rows)
    # Tags are advisory: a weakly supported tag is noted, not a package failure.
    consistency = title_description_agree
    critical: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not supported_tags:
        warnings.append(_issue(
            "weak_tag_support", "tags",
            "A selected tag has weak creator-source support; tags play a minimal role, so it is noted here only.",
            severity=tag_severity,
        ))
    if quote and short and title:
        # A quote Short's title passes or fails its checks above; these two
        # keep a passing package from GREEN without making it unsafe.
        body_length = len(title_body(title))
        if not 30 <= body_length <= 70:
            warnings.append(_issue(
                "title_length_outside_band", "title",
                f"A quote Short's title reads best at 30-70 characters; this one has {body_length}.",
                severity="warning",
            ))
        if accepted and all(title_copies_quote(item.get("title"), quote) for item in accepted):
            # The quote may lead (option 1), but titles that only repeat what
            # the viewer reads on screen are a conservative package.
            warnings.append(_issue(
                "title_duplicates_on_screen_quote", "title",
                "Every title repeats the on-screen quote; add one in new words that carries its feeling.",
                severity="warning",
            ))
    if fluency_issues:
        critical.append(_issue(
            "broken_title_grammar", "title",
            f"The title is not a readable sentence: {fluency_issues[0]['message']}",
        ))
    if duration_issues:
        critical.append(_issue(duration_issues[0]["code"], "title", duration_issues[0]["message"]))
    if accepted and "title_score" not in not_measured and title_score < 55:
        critical.append(_issue("low_title_usefulness", "title", "Title is too weakly anchored to the supplied source."))
    if placement == "missing":
        warnings.append(_issue(
            "primary_keyword_missing_from_title", "title",
            f"The title does not contain the main search phrase “{primary_phrase}”.",
            severity=keyword_severity,
        ))
    if _source_is_topicless(source, brief):
        warnings.append(_issue(
            "topic_not_identified", "package",
            "The script never names its subject, so no title or tag can target a real search. "
            "Add what the video is about (the product, dish, skill, or idea) and generate again.",
            severity="warning",
        ))
    if description and not short:
        source_count = len(unicode_words(source))
        description_count = len(unicode_words(re.sub(r"#[^\s#]+", " ", description)))
        floor = min(120, max(50, int(source_count * 0.8)))
        if source_count >= 40 and description_count < floor:
            warnings.append(_issue(
                "description_too_short", "description",
                f"The description has {description_count} words; with this much source detail it should reach "
                f"about {floor} words that cover what the video actually delivers.",
                severity="warning",
            ))
    if description and "description_score" not in not_measured and description_score < 55:
        critical.append(_issue("low_description_usefulness", "description", "Description is too weakly anchored to the supplied source."))
    if not consistency:
        critical.append(_issue("package_consistency_failure", "package", "Title, description, and tags do not agree on the source-supported topic."))
    if tags and not topic_rows:
        warnings.append(_issue(
            "weak_tag_usefulness", "tags",
            "No useful subject tag survived; yt/shorts tags are retained only as the creator's format strategy.",
            severity=tag_severity,
        ))
    elif topic_rows and tag_score is not None and tag_score < 72:
        warnings.append(_issue(
            "weak_tag_usefulness", "tags",
            ("Subject-tag coverage is limited; this informational Shorts note does not determine the package verdict."
             if short else "Average subject-tag quality is below the 72-point threshold required for a GREEN package."),
            severity=tag_severity,
        ))
    rich_quote_context = bool(
        quote
        and normalize_unicode(brief.get("visual_requirements"))
        and normalize_unicode(brief.get("creator_intent"))
    )
    # Do not reward padding. Two strong, independently supported subject tags
    # are better than three tags where the third is generic or speculative.
    strong_topic_rows = [
        row for row in topic_rows
        if float(row.get("keyword_relevance_score") or 0) >= 90 and float(row.get("source_support_score") or 0) >= 70
    ]
    if short and rich_quote_context and len(topic_rows) < 2 and not strong_topic_rows:
        warnings.append(_issue(
            "sparse_tag_set", "tags",
            f"Only {len(topic_rows)} useful subject tag(s) survived without strong support; yt/shorts format tags do not count as subject tags.",
            severity=tag_severity,
        ))
    # An "info" note is reported but does not decide the verdict.
    verdict = "RED" if critical else ("YELLOW" if any(item["severity"] == "warning" for item in warnings) else "GREEN")
    return {
        "title_score": None if "title_score" in not_measured else round(title_score, 1),
        "description_score": None if "description_score" in not_measured else round(description_score, 1),
        "tag_score": tag_score,
        # Why a score above is None: not measured, which is not a low score.
        "not_measured": not_measured,
        "tag_count": len(tags),
        "package_consistency": consistency,
        "critical_issues": critical,
        "warnings": warnings,
        "verdict": verdict,
        "policy": "source fidelity + natural language + specificity + grounded search usefulness; not a performance prediction",
    }


# Talk that carries no subject: "the thing everyone gets wrong ... why it matters".
_GENERIC_TALK_WORDS = {
    "today", "want", "talk", "thing", "things", "something", "everything", "everyone",
    "everybody", "people", "gets", "get", "got", "wrong", "right", "honestly", "matters",
    "matter", "way", "more", "less", "think", "stay", "till", "until", "end", "really",
    "actually", "about", "just", "guys", "video", "watch", "let", "going", "gonna",
    "important", "thought", "thoughts", "stuff", "much", "many", "very", "know", "tell",
    "you", "your", "they", "them", "this", "that", "these", "those", "here", "there",
}


def _source_is_topicless(source: str, brief: dict[str, Any]) -> bool:
    """True when neither the script nor the brief names a concrete subject."""

    values = [source, *(normalize_unicode(brief.get(field)) for field in (
        "topic", "exact_quote", "on_screen_text", "viewer_promise", "unique_angle", "target_audience",
    ))]
    specific = {
        word for value in values for word in _meaningful_words(value)
        if word not in _GENERIC_TALK_WORDS
    }
    return len(specific) < 2


def primary_search_phrase(tag_evidence: dict[str, Any] | None) -> str:
    """The strongest selected subject tag, preferring one real searchers type."""

    rows = [
        row for row in (tag_evidence or {}).get("selected_keywords", [])
        if isinstance(row, dict) and row.get("keyword") and row.get("classification") != "platform_format"
    ]
    if not rows:
        return ""
    demand_backed = [row for row in rows if row.get("demand_validated")] or rows
    # Among real searches, the one naming the most of the video's subject is
    # the main phrase: "chatgpt for excel", not the generic "if function".
    subjects = {str(term).casefold() for term in (tag_evidence or {}).get("subject_terms") or []}
    if subjects:
        def subject_weight(row: dict[str, Any]) -> int:
            return len({word.casefold() for word in unicode_words(row.get("keyword"))} & subjects)
        best = max(subject_weight(row) for row in demand_backed)
        if best:
            demand_backed = [row for row in demand_backed if subject_weight(row) == best]
    return str(demand_backed[0]["keyword"])


def strong_search_phrases(tag_evidence: dict[str, Any] | None) -> list[str]:
    """Selected phrases viewers really type that name at least two subject words."""

    subjects = {str(term).casefold() for term in (tag_evidence or {}).get("subject_terms") or []}
    return [
        str(row["keyword"]) for row in (tag_evidence or {}).get("selected_keywords", [])
        if isinstance(row, dict) and row.get("keyword") and row.get("demand_validated")
        and len({word.casefold() for word in unicode_words(row["keyword"])} & subjects) >= 2
    ]


_PLACEMENT_FORMAT_WORDS = {"quote", "quotes", "status", "video", "videos"}


def keyword_placement(title: str, phrase: str) -> str:
    """"front", "late", "missing", or "unknown" for a search phrase in a title.

    Matching is by word root and, for Tamil or bilingual titles, by sound, so
    "செட்டிநாடு சிக்கன் பிரியாணி" satisfies "chettinad chicken biryani".
    """

    # "betrayal quotes" is searched, but a quote Short's title carries the
    # theme, not the word "quotes"; format words are not part of the match.
    phrase_words = [word for word in _meaningful_words(phrase) if word not in _PLACEMENT_FORMAT_WORDS]
    title_tokens = unicode_words(_SHORTS_TITLE_RE.sub(" ", normalize_unicode(title)))
    if not phrase_words or not title_tokens:
        return "unknown"
    title_roots = [_quality_root(token) for token in title_tokens]
    title_keys = [phonetic_key(token) for token in title_tokens]
    positions: list[int] = []
    for word in phrase_words:
        root = _quality_root(word)
        position = next((i for i, value in enumerate(title_roots) if value == root), None)
        if position is None:
            key = phonetic_key(word)
            if len(key) >= 3:
                position = next((i for i, value in enumerate(title_keys) if value == key), None)
        if position is not None:
            positions.append(position)
    if len(positions) / len(phrase_words) < 0.6:
        return "missing"
    return "front" if min(positions) <= 5 else "late"


def _source_words(source: str, brief: dict[str, Any]) -> set[str]:
    values = [source]
    values.extend(brief.get(field) for field in (
        "content", "topic", "exact_quote", "on_screen_text", "viewer_promise", "unique_angle", "factual_claims",
        "visual_requirements", "creator_intent", "content_constraints", "target_audience", "proof",
    ))
    return {word for value in values for word in _meaningful_words(value)}


def _meaningful_words(value: Any) -> list[str]:
    return [word for word in unicode_words(value) if len(word) > 2 and word not in _NOT_MEANINGFUL]


# Grammar words, including modal and auxiliary verbs: "Why you should stop
# explaining yourself" names no topic with "should".
_NOT_MEANINGFUL = frozenset({
    "a", "an", "and", "are", "as", "at", "after", "before", "be", "but", "by", "for", "from", "how", "i", "in",
    "into", "is", "it", "my", "of", "on", "or", "our", "that", "the", "this", "to", "was", "we", "what", "when",
    "where", "which", "who", "whom", "why", "with", "you", "your", "shorts",
    "can", "could", "should", "would", "will", "must", "might", "may", "have", "has", "had", "been", "were",
    "does", "did",
})


def _bounded_score(value: float) -> float:
    return max(0.0, min(100.0, value))


def _quality_root(value: str) -> str:
    word = str(value or "").casefold()
    irregular = {"chosen": "choose", "gave": "give", "given": "give"}
    if word in irregular:
        # Same trailing-"e" rule as below, or "chosen" -> "choose" stops
        # matching "choose" -> "choos".
        word = irregular[word]
        return word[:-1] if len(word) > 3 and word.endswith("e") and not word.endswith("ee") else word
    if len(word) > 5 and word.endswith("ing"):
        word = word[:-3]
        if len(word) > 2 and word[-1:] == word[-2:-1]:
            word = word[:-1]
    elif len(word) > 4 and word.endswith("ied"):
        word = word[:-3] + "y"
    elif len(word) > 4 and word.endswith("ed"):
        word = word[:-1] if word[-2:-1] == "e" else word[:-2]
    elif len(word) > 4 and word.endswith("s") and not word.endswith("ss"):
        word = word[:-1]
    # "loving" loses "ing" but "love" keeps its "e"; without this the two never
    # matched and a title opening "Loving..." missed the keyword "love quotes".
    if len(word) > 3 and word.endswith("e") and not word.endswith("ee"):
        word = word[:-1]
    return word


def evidence_trace(channel_learning: dict[str, Any] | None) -> dict[str, Any]:
    """Expose only evidence-policy output used for personalization."""

    learning = channel_learning or {}
    cohort = learning.get("cohort") if isinstance(learning.get("cohort"), dict) else {}
    allowed = bool(cohort.get("learning_allowed"))
    return {
        "status": "mature_evidence_used" if allowed else "insufficient_evidence",
        "learning_allowed": allowed,
        "confidence": cohort.get("confidence_label") or learning.get("confidence_label") or "Collecting evidence",
        "sample_size": int(cohort.get("sample_size") or 0),
        "window": cohort.get("snapshot_window") or "24h",
        "evidence_source": "comparable_owned_video_cohort" if allowed else "none",
        "message": (
            "Mature comparable channel evidence was available to the generation prompt."
            if allowed else
            "Insufficient mature comparable evidence; no creator winning pattern was applied."
        ),
    }


def _issue(
    code: str, field: str, message: str, *, severity: str = "error", index: int | None = None, **extra: Any,
) -> dict[str, Any]:
    result: dict[str, Any] = {"code": code, "field": field, "severity": severity, "message": message}
    if index is not None:
        result["candidate_index"] = index
    result.update(extra)
    return result


def _tag_note(code: str, message: str, *, tag: str) -> dict[str, Any]:
    """An advisory note on one tag, which apply_quality_gate drops from the package."""

    return _issue(code, "tags", message, severity="warning", tag=tag)


def _unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = " ".join(unicode_words(value))
        if key and key not in seen:
            seen.add(key)
            result.append(value)
    return result


_EXPLANATORY_SOURCE_RE = re.compile(
    r"\b(?:why|because|explain\w*|reasons?|compar\w*|difference|versus|vs)\b", re.IGNORECASE,
)


def _unsupported_claims(text: str, source_text: str) -> list[str]:
    source = normalize_unicode(source_text).casefold()
    codes = [code for code, pattern in _UNSUPPORTED_CLAIMS if pattern.search(text) and not pattern.search(source)]
    # "results in / leads to" is invented causality only when the source makes
    # no explanatory promise. A script that says it will "explain why cold brew
    # tastes smoother" legitimately produces "the long steep results in a
    # smoother cup".
    if "invented_causality" in codes and _EXPLANATORY_SOURCE_RE.search(source):
        codes.remove("invented_causality")
    if source_withholds_message_content(source_text) and re.search(
        r"\b(?:exact (?:text|message)|what those words reveal|find out what)\b",
        text,
        re.IGNORECASE,
    ):
        codes.append("invented_message_content")
    return codes


def _is_reflective_source(brief: dict[str, Any], non_instructional: bool) -> bool:
    """Quote, story, and reflection content, where invented context is the main risk."""

    return non_instructional or bool(normalize_unicode(brief.get("exact_quote") or brief.get("on_screen_text")))


def _invented_context_terms(
    words: Iterable[str], source_words: set[str], *, reflective: bool, feelings: set[str] | None = None,
) -> list[str]:
    """Context words the output adds that the creator never used, per content type.

    ``feelings`` are the quote's own feeling keys (see _feeling_keys): a
    quote about love or missing someone supports "love", and one about
    healing supports "comfort", "peace" and "healing".
    """

    banned = set(_UNSUPPORTED_CONTEXT_TERMS) if reflective else set(_CLINICAL_CONTEXT_TERMS)
    keys = set(feelings or ())
    if keys & _LOVE_FEELING_KEYS:
        banned -= _LOVE_CONTEXT_TERMS
    if keys & _COMFORT_FEELING_KEYS:
        banned -= _COMFORT_CONTEXT_TERMS
    present = set(words)
    return sorted(term for term in banned if term in present and term not in source_words)


# Units repeat in every ingredient or spec list ("1 cup rice, 1 cup dal, ...");
# they are not the repeated keyword that marks a tag dump.
_MEASURE_WORDS = {
    "cup", "cups", "tsp", "tbsp", "teaspoon", "teaspoons", "tablespoon", "tablespoons",
    "gram", "grams", "gms", "kg", "kgs", "litre", "liter", "litres", "liters", "pinch",
    "spoon", "spoons", "piece", "pieces", "inch", "inches", "mins", "minutes", "hours",
    "ounce", "ounces", "pound", "pounds", "gb", "tb", "mah", "hz", "watt", "watts",
}


def _looks_like_tag_list(description: str) -> bool:
    """Detect keyword stuffing, not ordinary lists.

    The old rule flagged any line with five or more commas. Every recipe that
    lists its ingredients and every review that lists specs tripped it, and an
    Indian price such as "Rs 1,29,999" alone supplied two of the five commas.
    A real tag dump is different: many short fragments that keep repeating the
    same keyword ("cold brew, cold brew coffee, cold brew recipe, ..."). An
    ingredient list is many short fragments that do *not* repeat.
    """

    lines = [line.strip() for line in description.splitlines() if line.strip()]
    for line in lines:
        cleaned = re.sub(r"(?<=\d),(?=\d)", "", line)  # digit grouping is not a separator
        segments = [seg.strip() for seg in re.split(r"[,|]", cleaned) if seg.strip()]
        if len(segments) < 5:
            continue
        short_segments = [seg for seg in segments if len(unicode_words(seg)) <= 4]
        if len(short_segments) / len(segments) < 0.8:
            continue
        counts: dict[str, int] = {}
        for segment in segments:
            for word in set(_meaningful_words(segment)) - _MEASURE_WORDS:
                counts[word] = counts.get(word, 0) + 1
        most_repeated = max(counts.values(), default=0)
        if most_repeated >= max(3, int(len(segments) * 0.4 + 0.999)):
            return True
    words = unicode_words(description)
    repeated_phrases = re.findall(r"\b([\w'’]+(?:\s+[\w'’]+){1,3})\b", description.casefold(), re.UNICODE)
    duplicates = len(repeated_phrases) - len(set(repeated_phrases))
    # Longer descriptions naturally repeat the subject; scale the allowance.
    return duplicates >= max(8, len(words) // 12)


# Grammar words that cannot end a title or follow "how to" as its verb.
_DANGLING_TITLE_ENDINGS = {
    "and", "but", "or", "with", "without", "from", "about", "to", "for", "of",
    "after", "before", "into", "than", "the", "a", "an", "your", "my", "our",
    "their", "his", "her", "its", "is", "are", "was", "were", "any", "especially",
}
_COPULAS = {"is", "are", "was", "were"}
_SUBJECT_PRONOUNS = {"i", "you", "we", "they", "he", "she", "it"}
# Only the words whose close repetition signals garbling ("How to you how
# make ..."). Articles repeat legitimately: "The Good, the Bad and the Ugly".
_REPEATABLE_FUNCTION_WORDS = {"how", "to"}
_COORDINATORS = {"and", "or", "vs", "versus", "but"}
_NOT_A_VERB_AFTER_HOW_TO = {
    "you", "i", "we", "they", "he", "she", "it", "my", "your", "our", "their",
    "the", "a", "an", "this", "that", "these", "those", "honest", "how", "to",
}


_TIME_UNITS = {
    "second": "second", "seconds": "second", "sec": "second", "secs": "second",
    "minute": "minute", "minutes": "minute", "min": "minute", "mins": "minute",
    "hour": "hour", "hours": "hour", "hr": "hour", "hrs": "hour",
    "day": "day", "days": "day", "week": "week", "weeks": "week",
    "month": "month", "months": "month", "year": "year", "years": "year",
}
_UNIT_PATTERN = "|".join(sorted(_TIME_UNITS, key=len, reverse=True))
# "after 30 days", "in minutes", "for 2 hours": a preposition, an optional
# number, then a time unit. "of the year" is not a duration claim.
_TITLE_DURATION_RE = re.compile(
    rf"\b(?:after|in|for|within|over|under)\s+(\d+(?:\.\d+)?\s*)?({_UNIT_PATTERN})\b", re.IGNORECASE,
)


def title_duration_issues(title: str, source: str, *, index: int | None = None) -> list[dict[str, Any]]:
    """A duration the source never gives, or one whose number was dropped.

    "Honest review of cold brew coffee after days" on a script that says
    "12 to 18 hours" invents a timescale; "... review after days" on a script
    that says "30 days" lost its number. Tamil sources write units in Tamil
    script, so only Latin-script sources can be judged this way.
    """

    source_text = normalize_unicode(source)
    if not source_text or _TAMIL_RANGE.search(source_text):
        return []
    source_units: set[str] = set()
    numbered_units: set[str] = set()
    for match in re.finditer(rf"(\d+(?:\.\d+)?\s*(?:(?:-|to)\s*\d+(?:\.\d+)?\s*)?)?\b({_UNIT_PATTERN})\b", source_text, re.IGNORECASE):
        unit = _TIME_UNITS[match.group(2).casefold()]
        source_units.add(unit)
        if match.group(1):
            numbered_units.add(unit)
    issues: list[dict[str, Any]] = []
    for match in _TITLE_DURATION_RE.finditer(normalize_unicode(title)):
        unit = _TIME_UNITS[match.group(2).casefold()]
        if unit not in source_units:
            issues.append(_issue(
                "invented_timescale", "title",
                f"Title claims a timescale in {unit}s ('{match.group(0)}'), which the creator source never gives.",
                index=index,
            ))
            break
        if not match.group(1) and unit in numbered_units:
            issues.append(_issue(
                "dropped_number", "title",
                f"Title says '{match.group(0)}' but the source gives the exact number; keep it.",
                index=index,
            ))
            break
    return issues


def title_fluency_issues(title: str, *, index: int | None = None, quote: Any = "") -> list[dict[str, Any]]:
    """Catch the word-salad signatures that the source-overlap score cannot see.

    Titles assembled from stopword-stripped fragments are made entirely of
    the creator's words, so every overlap-based check rated them highly —
    "How to you how make cold brew coffee home without" scored 100/100. These
    checks look at word order instead. A phrase the ``quote`` itself repeats
    ("close enough to need you, but never close enough to choose you") is
    its parallelism, not two search phrases stuck together.
    """

    clean = _SHORTS_TITLE_RE.sub(" ", normalize_unicode(title))
    clean = _TITLE_EMOJI_RE.sub(" ", clean)
    tokens = re.findall(r"[A-Za-z0-9]+(?:['’][A-Za-z]+)?", clean.casefold())
    if len(tokens) < 2:
        return []
    issues: list[dict[str, Any]] = []
    # "…decided who you are" ends a clause; "The reason people are" does not.
    ends_clause = tokens[-1] in _COPULAS and tokens[-2] in _SUBJECT_PRONOUNS
    if tokens[-1] in _DANGLING_TITLE_ENDINGS and not ends_clause:
        issues.append(_issue(
            "broken_title_grammar", "title",
            f"Title ends with the grammar word '{tokens[-1]}', so it reads as a cut-off phrase.",
            index=index,
        ))
    for position in range(len(tokens) - 2):
        if tokens[position] == "how" and tokens[position + 1] == "to" and tokens[position + 2] in _NOT_A_VERB_AFTER_HOW_TO:
            issues.append(_issue(
                "broken_title_grammar", "title",
                f"'how to' is followed by '{tokens[position + 2]}' instead of a verb.",
                index=index,
            ))
            break
    for position, token in enumerate(tokens):
        if token not in _REPEATABLE_FUNCTION_WORDS:
            continue
        window = tokens[position + 1:position + 4]
        if token not in window:
            continue
        between = tokens[position + 1:position + 1 + window.index(token)]
        # Coordination ("How to Cook and How to Store") is grammatical.
        if set(between) & _COORDINATORS:
            continue
        issues.append(_issue(
            "broken_title_grammar", "title",
            f"Title repeats '{token}' within a few words, which reads as garbled wording.",
            index=index,
        ))
        break
    # Two search phrases jammed together repeat their shared words:
    # "2 ingredient ice cream instant mango ice cream".
    content = [token for token in tokens if token not in _DANGLING_TITLE_ENDINGS and len(token) > 1]
    bigrams = list(pairwise(content))
    repeated = next((pair for position, pair in enumerate(bigrams) if pair in bigrams[position + 1:]), None)
    if repeated and quote:
        quoted = list(pairwise(
            token for token in re.findall(r"[A-Za-z0-9]+(?:['’][A-Za-z]+)?", normalize_unicode(quote).casefold())
            if token not in _DANGLING_TITLE_ENDINGS and len(token) > 1
        ))
        repeated = None if quoted.count(repeated) > 1 else repeated
    if repeated:
        issues.append(_issue(
            "keyword_stuffed_title", "title",
            f"Title repeats '{' '.join(repeated)}', which reads as two search phrases stuck together.",
            index=index,
        ))
    return issues


def _has_latin_or_tamil(text: str) -> bool:
    return bool(re.search(r"[A-Za-z\u0B80-\u0BFF]", text))
