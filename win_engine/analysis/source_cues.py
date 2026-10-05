"""What the creator's source says about the video: its format, its quote, its visuals.

One reading of each cue, shared by the brief, research, generation and the
quality gate. The copies that used to live in each module disagreed: "short
ribs" or "in short" made a tutorial a Short in one place and not in another,
the gate demanded quotes of 6-11 characters that the writer never inserted,
and "In this Visual Studio Code tutorial" became a visual requirement.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from win_engine.analysis.numbers import optional_number
from win_engine.analysis.text_tokens import normalize_unicode, unicode_words

# YouTube accepts Shorts of up to three minutes.
SHORTS_MAX_SECONDS = 180

# Stored format spellings (history_store.FORMAT_VALUES) that decide the question.
# "quote" is a Short there too; "other" says nothing about length.
_SHORT_FORMATS = frozenset({"youtube_shorts", "quote"})
_LONG_FORM_FORMATS = frozenset({"long_form", "talking_head", "tutorial", "vlog", "review", "story", "challenge"})
_FORMAT_ALIASES = {
    "short": "youtube_shorts", "shorts": "youtube_shorts", "youtube_short": "youtube_shorts",
    "yt_short": "youtube_shorts", "yt_shorts": "youtube_shorts", "reel": "youtube_shorts",
    "reels": "youtube_shorts", "short_form": "youtube_shorts", "shortform": "youtube_shorts",
    "quote_short": "youtube_shorts", "quote_shorts": "youtube_shorts", "longform": "long_form",
}
# The platform's own words for the format. A bare "short" is not one: "short
# ribs", "in short" and "a short guide" describe long videos.
_SHORT_CUE_RE = re.compile(
    r"(?<![\w#])#shorts?\b|\b(?:youtube|yt)[\s_-]*shorts?\b|\bshort[\s_-]?form\b|\breels?\b|\bquote[\s_-]+shorts?\b",
    re.IGNORECASE,
)

# Strong signals that a short line is an emotional quote, and weaker ones that
# count only alongside a described background visual.
_STRONG_QUOTE_WORDS = re.compile(
    r"\b(?:love[sd]?|loving|heart\w*|pain(?:ful)?|hurts?|hurting|cry|crying|tears?|miss(?:es|ing|ed)?|alone|lonely|"
    r"loneliness|silence|silent|trust|betray\w*|soul|broken|forgive\w*|regrets?|memories|sad(?:ness)?|"
    r"happiness|heal\w*|goodbye|forget|forgotten|deserve[sd]?)\b",
    re.IGNORECASE,
)
_WEAK_QUOTE_WORDS = re.compile(
    r"\b(?:never|forever|always|nothing|everything|someone|people|life|hope|dreams?|peace|strong|strength|"
    r"destiny|fate|karma|respect|feel(?:ings?)?|world)\b",
    re.IGNORECASE,
)
# Video narration, not a quote. "We accept the love we think we deserve" is a
# quote; "we hiked to Top Station" is a vlog, so only narrated past actions count.
_NARRATION_CUES = re.compile(
    r"\b(?:in this (?:video|short|vlog|episode)|today i|i will|we will|let me|i'?m going to|subscribe|how to|"
    r"step|steps|tutorial|recipe|ingredients|review|unboxing|price|buy|download|link in|watch till|"
    r"we\s+(?:\w+ed|went|made|had|tried|got|took|spent|did|bought|found|saw|came))\b",
    re.IGNORECASE,
)
# Words that make the text around a quoted span an instruction: in a tutorial
# or review, `click "Save changes"` names a button, not a line to reproduce.
_INSTRUCTIONAL_CUES = re.compile(
    r"\b(?:how\s+to|how2|tutorial|step[- ]by[- ]step|steps?|guide|setup|review|unboxing|click)\b",
    re.IGNORECASE,
)

# One threshold for every reader of a quote: a gate that demanded 6-character
# quotes while the writer inserted only 12-character ones could never pass.
MIN_QUOTE_CHARS = 6
_DOUBLE_QUOTED_RE = re.compile(r'["“]([^"“”\n]{%d,})["”]' % MIN_QUOTE_CHARS)
# Straight or curly single quotes. An apostrophe between two letters ("you're")
# belongs to the quote; only a mark with no letter after it can close one.
_SINGLE_QUOTED_RE = re.compile(
    r"(?<![A-Za-z])['‘]((?:[^'‘’\n]|(?<=[A-Za-z])['’](?=[A-Za-z])){%d,})['’](?![A-Za-z])" % MIN_QUOTE_CHARS
)
# "the quote is- ...", "Quote on screen: ...", "On-screen text: ...".
_QUOTE_LABEL = (
    r"\b(?:the\s+)?(?:exact\s+)?(?:quote|on[- ]screen\s+(?:text|quote)|screen\s+text)"
    r"(?:\s+(?:shown\s+)?(?:on|in)\s+(?:the\s+)?(?:screen|reel|video))?"
)
_QUOTE_LABEL_RE = re.compile(rf"(?is){_QUOTE_LABEL}\s*(?:is|reads?|says)?\s*[:\-–—]+\s*(.+)")
# The same label with no punctuation after it: "the quote on the screen is
# And why is it always ..." was read as no quote at all. Without a dash or a
# colon the quote must open with a capital letter or a quotation mark, so
# "the quote is the emotional focus" stays a sentence about the video.
_UNPUNCTUATED_QUOTE_LABEL_RE = re.compile(
    rf"(?is){_QUOTE_LABEL}\s+(?:is|reads?|says)\s+(?=[\"“'‘]|(?-i:[A-Z]))(.+)"
)
# Where production notes take over from a labelled quote, including "and the
# video background is ..." and a note glued to the quote's full stop
# ("... stay kind.and video is ..."), which were left inside the quote.
_QUOTE_NOTES_RE = re.compile(
    r"(?is)(?:\s+|(?<=[.!?]))(?:and\s+)?(?:the\s+)?(?:(?:video\s+)?background(?:\s+of\s+the\s+video)?|"
    r"background\s+visuals?|visuals?|format|voice[- ]?over|video\s+(?:is|shows?|has))\s*(?:is|are|:|\-)?\s*"
)
# "Background:", "Background video:", "Visuals:", "B-roll:" opening a line or a
# sentence. Prose that merely contains the word ("In this Visual Studio Code
# tutorial", "This video is about budgeting") is not a visual note.
_VISUAL_LABEL_RE = re.compile(
    r"(?im)(?:^|(?<=[.!?;]))[ \t]*(?:the\s+)?"
    r"(?:background(?:\s+(?:of\s+the\s+video|video|visuals?|footage|scene))?|visuals?(?:\s+requirements?)?|b[\s-]?roll)"
    r"[ \t]*(?::|[–—-](?=\s))\s*([^\n]+)"
)
_VISUAL_END_RE = re.compile(r"[.;](?:\s|$)|\s+(?:and|with)\s+(?=.*\b(?:quote|text|screen)\b)", re.IGNORECASE)
# A stripped line that opens with a timestamp: "0:00 Intro", "01:30 - Mixing",
# "1:02:15 Taste test". Matched on the stripped line with a greedy title: a lazy
# title before optional trailing space backtracked quadratically on long lines.
_TIMESTAMP_LINE_RE = re.compile(r"[\[(]?((?:\d{1,2}:)?\d{1,2}:\d{2})[\])]?\s*[-–—:|.]?\s*(\S.*)")


def format_key(value: Any) -> str:
    """The stored spelling of a format ("Short" -> "youtube_shorts"), else the cleaned text."""

    key = re.sub(r"[\s-]+", "_", normalize_unicode(value).casefold()).strip("_")
    key = _FORMAT_ALIASES.get(key, key)
    # Free text that starts with the platform's name: "YouTube Short quote video".
    return "youtube_shorts" if re.match(r"youtube_shorts?(?:_|$)", key) else key


def has_short_cue(text: Any) -> bool:
    """True when the text uses the platform's own words for a Short."""

    return bool(_SHORT_CUE_RE.search(normalize_unicode(text)))


def looks_like_standalone_quote(text: Any, visual_requirements: Any = "") -> bool:
    """A short emotional line with no video narration: the text of a quote Short."""

    value = str(text or "")
    words = unicode_words(value, min_length=1)
    sentences = [part for part in re.split(r"(?<=[.!?])\s+", value.strip()) if part]
    if not 5 <= len(words) <= 45 or len(sentences) > 3 or _NARRATION_CUES.search(value):
        return False
    if _STRONG_QUOTE_WORDS.search(value):
        return True
    return bool(str(visual_requirements or "").strip()) and bool(_WEAK_QUOTE_WORDS.search(value))


def feeling_words(text: Any) -> list[str]:
    """The strong emotional words of a text ("betrayal", "hurts"): the feeling a quote carries."""

    return [match.group(0).casefold() for match in _STRONG_QUOTE_WORDS.finditer(normalize_unicode(text))]


# Words that turn a verb around. "nothing" and "nobody" are subjects, not a
# negation of the verb ("nothing hurts more than ...").
NEGATORS = frozenset({"never", "not", "no", "without", "cannot", "neither", "nor"})


def is_negator(word: str) -> bool:
    """"never", "not", "don't", "can’t": a word that turns the verb after it around."""

    return word in NEGATORS or word.endswith(("n't", "n’t"))


def affirmed_feeling_words(text: Any) -> list[str]:
    """The feeling words a text does not deny: "Don't cry because it's over" names no sadness."""

    flat = normalize_unicode(text)
    return [
        match.group(0).casefold() for match in _STRONG_QUOTE_WORDS.finditer(flat)
        if not any(is_negator(word) for word in unicode_words(flat[:match.start()], min_length=1)[-2:])
    ]


def _stated_duration(brief: dict[str, Any]) -> float | None:
    seconds = optional_number(brief.get("duration_seconds"))
    if seconds is None or seconds <= 0:
        return None
    source = ((brief.get("field_provenance") or {}).get("duration_seconds") or {}).get("source")
    # A number read out of the script ("microwave it for 90 seconds") is not the video's length.
    return seconds if source in (None, "creator_supplied") else None


def is_short_video(script: Any = "", creator_brief: dict[str, Any] | None = None) -> bool:
    """Decide Short versus long-form, the one way every module decides it.

    A known format decides first: a tutorial, review, story or vlog is never a
    Short, whatever its text says. Otherwise a stated length of three minutes or
    less is a Short and a longer one is not. Otherwise only the platform's own
    words ("YouTube Short", "#shorts", "short-form", "reels", "quote short") or
    a script that is itself a standalone emotional quote make a Short. A topic
    category ("quotes") never does.
    """

    brief = creator_brief or {}
    key = format_key(brief.get("video_format"))
    if key in _SHORT_FORMATS:
        return True
    if key in _LONG_FORM_FORMATS:
        return False
    seconds = _stated_duration(brief)
    if seconds is not None:
        return seconds <= SHORTS_MAX_SECONDS
    source = normalize_unicode(brief.get("content") or script)
    if has_short_cue(f"{normalize_unicode(brief.get('video_format'))}\n{source}"):
        return True
    return looks_like_standalone_quote(source, brief.get("visual_requirements"))


def is_short_duration(seconds: Any) -> bool | None:
    """Whether a measured length is a Short's; None when the length is unknown."""

    value = optional_number(seconds)
    return None if value is None or value <= 0 else value <= SHORTS_MAX_SECONDS


def quoted_spans(text: Any) -> list[str]:
    """Quoted spans, longest first. A closing mark is the most reliable end of a quote."""

    value = str(text or "")
    matches = _DOUBLE_QUOTED_RE.findall(value) or _SINGLE_QUOTED_RE.findall(value)
    cleaned = [re.sub(r"\s+", " ", item).strip(" .,;:-") for item in matches]
    return sorted((item for item in cleaned if len(item) >= MIN_QUOTE_CHARS), key=len, reverse=True)


def _labelled_quote(text: str) -> str:
    match = _QUOTE_LABEL_RE.search(text)
    # A label with nothing but "is" after it names a quote only when what
    # follows is long enough to be one, not a stray capitalised phrase
    # ("the quote is Preserved exactly as written").
    min_words = 1
    if not match:
        match = _UNPUNCTUATED_QUOTE_LABEL_RE.search(text)
        min_words = 5
    if not match:
        return ""
    # A quoted line after the label is the quote itself; otherwise the label's
    # value runs to the production notes, not to the end of the text.
    inner = quoted_spans(match.group(1))
    if inner:
        return inner[0]
    value = _QUOTE_NOTES_RE.split(match.group(1), maxsplit=1)[0]
    value = re.sub(r"\s+", " ", value).strip(" \t\r\n\"'.,;:-")
    if value.count('"') % 2:
        value = value.replace('"', "")
    if len(unicode_words(value, min_length=1)) < min_words:
        return ""
    return value if len(value) >= MIN_QUOTE_CHARS else ""


def extract_quote(text: Any, *, short: bool = False) -> str:
    """The on-screen quote a creator's source gives, or "".

    A labelled quote ("the quote is- ...", "On-screen text: ...") is the
    creator's own statement and always counts. Any other quoted span counts
    only in a Short whose other text gives no instructions: in a tutorial or a
    review, `click "Save changes"` names a button, not a line to reproduce.
    """

    value = str(text or "")
    labelled = _labelled_quote(value)
    if labelled or not short:
        return labelled
    spans = quoted_spans(value)
    if not spans:
        return ""
    unquoted = _SINGLE_QUOTED_RE.sub(" ", _DOUBLE_QUOTED_RE.sub(" ", value))
    return "" if _INSTRUCTIONAL_CUES.search(unquoted) else spans[0]


def source_quote(script: Any = "", creator_brief: dict[str, Any] | None = None) -> str:
    """The exact quote a package must reproduce.

    A built brief has already decided (its ``exact_quote``, possibly empty);
    without one the source is read the same way the brief reads it.
    """

    brief = creator_brief or {}
    if "exact_quote" in brief:
        return normalize_unicode(brief.get("exact_quote"))
    text = str(brief.get("content") or script or "")
    return normalize_unicode(extract_quote(text, short=is_short_video(text, brief)))


# Where a quote turns: the idea after its last turn is the payoff a title
# keeps ("..., but never close enough to choose you", "..., not kept",
# "... is now setting boundaries").
_QUOTE_TURN_RE = re.compile(
    r"(?<=[\w.!?…])[\s,;]+(?:but|yet|however|instead)\b|(?<=\w)\s*,\s*(?=not\b)|(?<=\w)\s+(?:is|are|am)\s+now\b",
    re.IGNORECASE,
)
# A leading clause that sets the scene before the main one: "In a world where
# people always want something from you, | pay attention to the ones who just
# want you", "As you get older, | you notice how ...".
_LEADING_CLAUSE_RE = re.compile(
    r"(?i)^(?:in a world where|when(?:ever)?|if|as|while|because|since|after|before|once|"
    r"the (?:older|more|longer|less))\b[^,]*,\s*"
)
# Sentence ends inside a quote, including the "..." and the dash a quote
# uses as a pause before its last thought.
_QUOTE_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\s*\.{2,}\s*|\s*[;—–]\s*|\s+-\s+")
# Clause starts inside one sentence: a comma, or a word that opens a clause.
_CLAUSE_BOUNDARY_RE = re.compile(
    r"\s*,\s*|\s+(?P<word>who|which|where|that|than|if|when|while|because|so|and|or|&)\s+",
    re.IGNORECASE,
)
# A condition or a reason on its own is a fragment ("if you can't run to them").
_CLAUSE_FRAGMENT_WORDS = {"if", "when", "because", "so"}
# A span may not end on these: "...about being human is knowing" is cut.
_INCOMPLETE_ENDINGS = {
    "is", "are", "was", "were", "be", "being", "been", "am",
    "know", "knows", "knowing", "realize", "realise", "realizing", "realising", "notice", "noticing",
    "think", "thinking", "feel", "feels", "feeling", "wonder", "wondering", "remember", "remembering",
    "understand", "understanding", "learn", "learning", "learned", "learnt", "say", "says", "said",
    "mean", "means", "meant", "want", "wants", "wanted", "need", "needs", "needed", "hope", "hoping",
    "wish", "wishing", "than", "that", "which", "who", "whom", "if", "when", "while", "because",
    "so", "and", "but", "or", "to", "of", "for", "with", "from", "in", "on", "at", "by", "the",
    "a", "an", "my", "your", "our", "their", "his", "her", "its", "not", "never", "always", "very",
    # "..., especially | when ..." leans on the clause it opens.
    "especially", "even",
    # "...how rare it is to have someone" waits for its "who ..." clause.
    "someone", "somebody", "something", "anyone", "anybody", "anything", "everyone", "nothing",
}
# A quote's spoken opener, dropped only when the whole quote is too long for a title.
_QUOTE_LEAD_IN_RE = re.compile(
    r"^(?:perhaps|maybe|sometimes|honestly|in the end|the truth is|i think|i guess)\s*,?\s+", re.IGNORECASE,
)
# A main clause follows the comma: "if someone offers me a flower, I offer
# them my entire garden" is complete; "when something ends, while still
# wishing it wouldn't" is not.
_CLAUSE_SUBJECTS = {
    "i", "you", "we", "they", "he", "she", "it", "people", "someone", "somebody", "nobody", "everyone",
    "there", "that's", "it's", "they're", "you're", "we're", "i'm", "your", "my", "the", "a", "an", "some",
}
# A word that opens a new phrase in the quote: a title may stop right before
# it. Not "and" ("seen, felt, heard and loved" stops inside its list), and not
# "than", "that", "who" or "which": the comparison or the clause they open is
# what the words before them are about ("nothing more painful | than ...",
# "the ones | who just want you").
QUOTE_PHRASE_STARTS = {"the", "a", "an", "when", "while", "because", "if", "where", "yet", "so", "not"}
# The noun a relative clause describes, kept with it in a title: "someone who
# has seen every version of you", "the ones who just want you".
_ANTECEDENTS = {
    "someone", "somebody", "anyone", "anybody", "everyone", "everybody", "something", "anything",
    "everything", "nothing", "people", "person", "one", "ones", "those", "thing", "things",
}
_ANTECEDENT_DETERMINERS = {"the", "a", "an", "those", "these", "some", "my", "your", "our", "their"}
# A clause these open is a condition or a reason of the clause before it: when
# that clause is denied, the reason is what it denies ("You don't lose people
# | because you stopped caring").
_SUBORDINATE_OPENERS = {"because", "when", "if", "while"}
# Grammar words, which say nothing about how much of a quote a span keeps.
_COVERAGE_STOP = {
    "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "at", "for", "with", "from", "by",
    "is", "are", "was", "were", "be", "been", "am", "it", "its", "it's", "you", "me", "my", "your",
    "we", "our", "they", "them", "their", "he", "she", "his", "her", "this", "that", "these", "those",
    "there", "what", "when", "where", "which", "who", "whom", "why", "how", "if", "so", "than", "then",
    "as", "not", "no", "do", "does", "did", "have", "has", "had", "will", "would", "can", "could",
    "should", "just", "all",
}
# A creator who pastes keywords after the line ("..., quotes about ego and
# pride, aesthetic night shorts, shorts, yt, viral shorts") is not quoting them.
_KEYWORD_PIECE_RE = re.compile(r"(?i)#|\b(?:quotes?|shorts?|yt|youtube|viral|trending|fyp|reels?|status|aesthetic)\b")
_PLATFORM_PIECE_RE = re.compile(r"(?i)#|\b(?:shorts?|yt|youtube|viral|trending|fyp|reels?)\b")


def strip_keyword_tail(text: Any) -> str:
    """A standalone quote without the comma-separated keyword list pasted after it."""

    value = str(text or "")
    pieces = value.split(",")
    for index in range(1, len(pieces)):
        tail = [piece.strip() for piece in pieces[index:] if piece.strip()]
        if (
            len(tail) >= 2 and all(len(piece.split()) <= 5 for piece in tail)
            and _KEYWORD_PIECE_RE.search(pieces[index])
            and any(_PLATFORM_PIECE_RE.search(piece) for piece in tail)
        ):
            return ",".join(pieces[:index]).strip(" ,")
    return value


def _flat_quote(quote: Any) -> str:
    text = re.sub(r"\s+", " ", normalize_unicode(quote)).strip()
    # A decoration at the end ("... and loved ♡") is not part of the words.
    return re.sub(r"[\s♡♥❤️✨🤍💔]+$", "", text).strip()


def quote_punchline(quote: Any) -> str:
    """The clause after a quote's turn, or its last sentence; "" when it has neither.

    "Some people keep you close enough to need you, but never close enough
    to choose you" turns at "but": a title that stops before it names the
    setup and loses the point. A denied clause turns at its comma too (see
    _splice_turn).
    """

    text = _flat_quote(quote)
    if not text:
        return ""
    # A turn word that ends the quote ("..., you gave me excuses instead.") turns nothing.
    turns = [match.end() for match in _QUOTE_TURN_RE.finditer(text) if unicode_words(text[match.end():], min_length=1)]
    turn = max([*turns, _splice_turn(text)])
    if turn >= 0:
        return text[turn:].strip(" ,;")
    sentences = [part.strip() for part in _QUOTE_SENTENCE_RE.split(text) if part and part.strip(" .,;:!?")]
    if len(sentences) >= 2:
        return sentences[-1]
    # One sentence that sets a scene first: the main clause after it is the point.
    lead = _LEADING_CLAUSE_RE.match(text)
    if lead and len(unicode_words(text[lead.end():], min_length=1)) >= 3:
        return text[lead.end():].strip(" ,;")
    return ""


def _denies(text: str) -> bool:
    return any(is_negator(word) for word in unicode_words(text, min_length=1))


def _has_main_clause(pieces: list[tuple[str, str, str]]) -> bool:
    """Whether a clause after a comma has its own subject: "if someone offers me a flower, | I offer ..."."""

    return any(
        boundary == "," and next(iter(unicode_words(piece, min_length=1)), "") in _CLAUSE_SUBJECTS
        for boundary, piece, _ in pieces
    )


def _splice_turn(text: str) -> int:
    """Where a denied clause turns at a comma to the clause that corrects it, or -1.

    "You don't lose people because you stopped caring, | you lose them
    because they stopped trying" has no "but", yet its point is the clause
    after the comma: a new subject that answers the denial.
    """

    turn = -1
    for match in re.finditer(r",\s*", text):
        sentence = re.split(r"[.!?;]\s+", text[:match.start()])[-1]
        after = unicode_words(text[match.end():], min_length=1)
        if len(after) >= 3 and after[0] in _CLAUSE_SUBJECTS and _denies(sentence):
            turn = match.end()
    return turn


def _title_form(span: str, *, question: bool, ends_quote: bool, starts_quote: bool = False) -> str:
    """A span of the quote's words as a title: capitalised, one question mark, no trailing stop.

    A question's opening span ("What's the point of calling them your
    people") keeps its question mark; so does any span that ends the quote.
    """

    text = re.sub(r"\s+", " ", span).strip(" ,;:-")
    text = re.sub(r"[.!?]+$", "", text).rstrip(" ,;:-")
    text = re.sub(r"(?<!\S)i(?=['’\s])", "I", text)  # a lowercase "i" mid-quote
    if not text:
        return ""
    text = text[:1].upper() + text[1:]
    asks = question and (ends_quote or starts_quote or span.rstrip().endswith("?"))
    return text + ("?" if asks else "")


def _clause_pieces(sentence: str) -> list[tuple[str, str, str]]:
    """(boundary word before it or "" / ",", piece, the text joining it to the previous piece) per clause."""

    pieces: list[tuple[str, str, str]] = []
    position = 0
    boundary, separator = "", ""

    def add(piece: str) -> None:
        nonlocal boundary, separator
        # ", while my heart ..." opens with the word, not the comma.
        opener = re.match(r"(?i)(who|which|where|that|than|if|when|while|because|so|and|or|&)\s+", piece)
        if boundary == "," and opener:
            boundary, separator, piece = opener.group(1).casefold(), separator + piece[:opener.end()], piece[opener.end():]
        if piece:
            pieces.append((boundary, piece, separator))

    for match in _CLAUSE_BOUNDARY_RE.finditer(sentence):
        add(sentence[position:match.start()].strip())
        boundary = (match.group("word") or ",").casefold()
        separator = match.group(0)
        position = match.end()
    add(sentence[position:].strip())
    return pieces


def quote_title(
    quote: Any, max_chars: int = 70, *, whole_max_chars: int = 85, hard_max_chars: int = 100,
    accept: Callable[[str], bool] | None = None,
) -> str:
    """A quote as a title: whole when it fits, else its best complete span.

    Never cut mid-phrase and never ended with "…". The whole quote is kept
    up to ``whole_max_chars``: a few characters over the ideal beat a cut.
    A longer quote gives the span that keeps most of its meaning within
    ``max_chars`` (the clause after its turn, a whole sentence, a run of
    whole clauses, a relative clause with the noun it describes), or the
    whole quote within YouTube's ``hard_max_chars`` when no shorter span
    keeps its point. ``accept`` is the caller's own title check, the quality
    gate's: a span it rejects is never chosen while another passes. A spoken
    opener ("Perhaps", "In the end") is dropped only from a quote too long
    to keep whole.
    """

    text = _flat_quote(quote)
    if not text:
        return ""
    passes = accept or (lambda _title: True)
    question = text.endswith("?")
    trimmed = _QUOTE_LEAD_IN_RE.sub("", text)
    wholes = list(dict.fromkeys(
        _title_form(value, question=question, ends_quote=True) for value in (text, trimmed) if value
    ))
    for title in wholes:
        if len(title) <= whole_max_chars and passes(title):
            return title
    ranked = _ranked_quote_spans(trimmed, question, max_chars=max_chars, hard_max_chars=hard_max_chars)
    chosen = next((title for title in ranked if passes(title)), "")
    # Nothing passes the caller's check: the best span within the ideal
    # length, which the caller's gate then reports, never a cut with "…".
    return chosen or next((title for title in ranked if len(title) <= max_chars), "") or _leading_phrase(
        trimmed, question, max_chars,
    )


def _coverage_roots(text: str) -> set[str]:
    return {word[:5] for word in unicode_words(text, min_length=1) if len(word) > 2 and word not in _COVERAGE_STOP}


def _antecedent(piece: str) -> str:
    """The noun ending a clause that the next relative clause describes, with its determiner.

    "to have someone" -> "someone"; "you were the only thing" -> "the only
    thing", never a bare "thing".
    """

    words = piece.split()
    if not words or words[-1].casefold().strip(",.") not in _ANTECEDENTS:
        return ""
    # Back over its modifiers ("only", "most beautiful") to its determiner; a
    # grammar word ("to have someone") ends the noun phrase.
    for back in range(2, min(len(words), 4) + 1):
        word = words[-back].casefold()
        if word in _ANTECEDENT_DETERMINERS:
            return " ".join(words[-back:])
        if word in _COVERAGE_STOP:
            break
    return words[-1]


def _ranked_quote_spans(text: str, question: bool, *, max_chars: int, hard_max_chars: int) -> list[str]:
    """Complete spans of a quote as titles, best first; the whole quote competes within ``hard_max_chars``.

    A fragment (a condition or reason without its main clause, a span ending
    on a word that needs more) ranks after every complete span, whatever its
    length: "When the people around you have small ones and cannot understand
    it" ended the quote and outscored the complete clause before it.
    """

    roots = _coverage_roots(text)
    scored: dict[str, tuple[bool, float, int]] = {}

    def consider(span: str, bonus: float, *, ends_quote: bool, starts_quote: bool, order: int,
                 asks: bool | None = None, fragment: bool = False) -> None:
        title = _title_form(span, question=question if asks is None else asks,
                            ends_quote=ends_quote, starts_quote=starts_quote)
        words = unicode_words(title, min_length=1)
        if len(words) < 4 or len(title) > hard_max_chars:
            return
        # A quote's last words are its point and its first its hook; a span
        # keeping more of its words keeps more of its meaning. Past the ideal
        # length a title loses what a viewer reads before it is truncated.
        score = min(len(title), max_chars) + bonus
        score += 30 if ends_quote else 15 if starts_quote else 0
        score += 40 * len(_coverage_roots(title) & roots) / max(len(roots), 1)
        score -= 10 if len(title) < 30 else 0
        score -= 3 * max(0, len(title) - max_chars)
        if words[-1].rstrip("?") in _INCOMPLETE_ENDINGS:
            # The quote's own last word ("... the return trip will be") ends it.
            score, fragment = score - 25, fragment or not ends_quote
        if title not in scored or scored[title][1] < score:
            scored[title] = (fragment, score, order)

    consider(text, 0, ends_quote=True, starts_quote=False, order=-1)
    punchline = quote_punchline(text)
    if punchline:
        consider(punchline, 40, ends_quote=True, starts_quote=False, order=0)
        # "Yet, for a little while, ..." keeps the contrast word but reads as
        # a fragment, so it ranks below the clause itself.
        turns = list(_QUOTE_TURN_RE.finditer(text))
        if turns:
            turn_word = re.search(r"(?i)\b(?:but|yet)\b", turns[-1].group(0))
            if turn_word:
                consider(text[turns[-1].start() + turn_word.start():], 30, ends_quote=True, starts_quote=False, order=1)
    cuts = list(_QUOTE_SENTENCE_RE.finditer(text))
    starts = [0, *(match.end() for match in cuts)]
    sentences = [
        (text[start:stop].strip(), start)
        for start, stop in zip(starts, [*(match.start() for match in cuts), len(text)])
        if text[start:stop].strip(" .,;:!?")
    ]
    for index, (sentence, start_at) in enumerate(sentences):
        first_sentence, last = index == 0, index == len(sentences) - 1
        if len(sentences) > 1:
            consider(sentence, 10, ends_quote=last, starts_quote=first_sentence, order=2 + index)
            if index:
                # The quote's closing sentences together: "For some reason, I
                # never thought ... But there was, and I was in it".
                consider(text[start_at:], 10, ends_quote=True, starts_quote=False, order=20 + index)
        pieces = _clause_pieces(sentence)
        for start in range(len(pieces)):
            if start and pieces[start][0] in _SUBORDINATE_OPENERS and _denies(pieces[start - 1][1]):
                continue  # "Because you stopped caring, ..." asserts the reason the quote denies
            for end in range(start + 1, len(pieces) + 1):
                (opener, first, _), *rest = pieces[start:end]
                # The quote's own words and punctuation between its clauses.
                span = first + "".join(separator + piece for _, piece, separator in rest)
                bonus, asks, fragment = 0.0, None, False
                antecedent = _antecedent(pieces[start - 1][1]) if start else ""
                if opener in {"who", "which", "that"} and antecedent:
                    # "Someone who has seen every version of you and still
                    # stayed" names what the clause describes; it is not a question.
                    span, asks = f"{antecedent} {opener} {span}", False
                elif opener == "that":
                    pass  # "knowing that | if you didn't find out, ..." opens a statement
                elif opener in {"who", "which", "where"}:
                    span, bonus = f"{opener} {span}", -15.0
                elif opener == "while":
                    # "while my heart quietly imagined a life you never knew
                    # existed" stands on its own without its "while".
                    bonus = -5.0
                elif opener == "than":
                    # "nothing more painful than | to be in love with ..." :
                    # what the comparison names stands alone; "than" never does.
                    if not re.match(r"(?i)(?:to\s|\w+ing\b)", first):
                        continue
                    bonus = -10.0
                elif opener in _CLAUSE_FRAGMENT_WORDS:
                    # "If someone offers me a flower, I offer them my entire
                    # garden" is complete; "if you can't run to them when
                    # life gets heavy" is not.
                    bonus, fragment = (0.0, False) if _has_main_clause(rest) else (-25.0, True)
                    span = f"{opener} {span}"
                elif opener in {"and", "or", "&"}:
                    bonus = -15.0
                if len(first.split()) == 1 and rest and rest[0][0] in _CLAUSE_FRAGMENT_WORDS:
                    # ", especially | when ..." leans on the condition it opens.
                    fragment = fragment or not _has_main_clause(rest[1:])
                consider(span, bonus, ends_quote=last and end == len(pieces), asks=asks, fragment=fragment,
                         starts_quote=first_sentence and start == 0, order=100 + start * 10 + end)
    # What the quote says someone notices or realises: "you notice how |
    # people really do make time for the things they love & excuses for ...",
    # "the more I realise | how rare it is to have someone who ...".
    for match in re.finditer(
        r"(?i)\b(?:how|that|why)\s+(?=(?:people|you|i|we|they|he|she|it|someone|everyone|nobody)\b)", text,
    ):
        consider(text[match.end():], 0, ends_quote=True, starts_quote=False, order=300 + match.start())
    for match in re.finditer(r"(?i)\bhow\s+(?!to\b)(?=\w)", text):
        consider(text[match.start():], -5, ends_quote=True, starts_quote=False, order=600 + match.start())
    ranked = sorted(scored.items(), key=lambda item: (item[1][0], -item[1][1], item[1][2]))
    return [title for title, _ in ranked]


def _leading_phrase(text: str, question: bool, max_chars: int) -> str:
    """One long clause with no boundary: its opening run up to the word that starts a new phrase.

    "... of missing people | the mind already learned to forget".
    """

    words = text.split()
    best = ""
    for count in range(len(words) - 1, 3, -1):
        candidate = _title_form(" ".join(words[:count]), question=question, ends_quote=False, starts_quote=True)
        if len(candidate) > max_chars:
            continue
        if words[count].casefold().strip(",.;:") in QUOTE_PHRASE_STARTS and candidate.split()[-1].casefold() not in _INCOMPLETE_ENDINGS:
            return candidate
        if not best and candidate.split()[-1].casefold() not in _INCOMPLETE_ENDINGS:
            best = candidate
    return best


def timestamp_seconds(value: Any) -> int | None:
    """Seconds from the start of "1:30" or "1:02:15"; None for anything else, such as "0:75"."""

    if not re.fullmatch(r"(?:\d{1,2}:)?\d{1,2}:\d{2}", str(value or "")):
        return None
    *hours, minutes, seconds = (int(part) for part in str(value).split(":"))
    if minutes >= 60 or seconds >= 60:
        return None
    return (hours[0] if hours else 0) * 3600 + minutes * 60 + seconds


def timestamp_line(line: Any) -> tuple[int, str, str] | None:
    """(seconds, timestamp, title) of a line that opens with a timestamp, else None.

    One reading for the chapter list, the description it is pasted into, and
    the casing map, where "0:45 Download and install OBS" opens a sentence.
    """

    match = _TIMESTAMP_LINE_RE.fullmatch(str(line or "").strip())
    seconds = timestamp_seconds(match.group(1)) if match else None
    return None if seconds is None else (seconds, match.group(1), match.group(2))


def labelled_visual(text: Any) -> str:
    """The visual note after an explicit label ("Background: rainy road"), or ""."""

    match = _VISUAL_LABEL_RE.search(str(text or ""))
    if not match:
        return ""
    value = _VISUAL_END_RE.split(match.group(1), maxsplit=1)[0]
    return re.sub(r"\s+", " ", value).strip(" .")
