"""What the creator's source says about the video: its format, its quote, its visuals.

One reading of each cue, shared by the brief, research, generation and the
quality gate. The copies that used to live in each module disagreed: "short
ribs" or "in short" made a tutorial a Short in one place and not in another,
the gate demanded quotes of 6-11 characters that the writer never inserted,
and "In this Visual Studio Code tutorial" became a visual requirement.
"""

from __future__ import annotations

import re
from typing import Any

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
    r"\b(?:love[sd]?|loving|heart\w*|pain(?:ful)?|hurts?|hurting|cry|crying|tears?|miss(?:ing|ed)?|alone|lonely|"
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
_SINGLE_QUOTED_RE = re.compile(r"(?<![A-Za-z])'([^'\n]{%d,})'(?![A-Za-z])" % MIN_QUOTE_CHARS)
# "the quote is- ...", "Quote on screen: ...", "On-screen text: ...".
_QUOTE_LABEL_RE = re.compile(
    r"(?is)\b(?:the\s+)?(?:quote|on[- ]screen\s+text|screen\s+text)(?:\s+(?:on|in)\s+(?:the\s+)?(?:screen|reel|video))?"
    r"\s*(?:is|reads?)?\s*[:\-–—]+\s*(.+)"
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


def labelled_visual(text: Any) -> str:
    """The visual note after an explicit label ("Background: rainy road"), or ""."""

    match = _VISUAL_LABEL_RE.search(str(text or ""))
    if not match:
        return ""
    value = _VISUAL_END_RE.split(match.group(1), maxsplit=1)[0]
    return re.sub(r"\s+", " ", value).strip(" .")
