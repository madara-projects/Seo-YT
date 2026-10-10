"""The AI Shorts package's SEO: what the quote means, and the tags, hashtags and emoji that follow from it.

The Creator page researches a video on YouTube before it chooses tags; the AI
Shorts path makes no YouTube Data API call. Its tags come from the quote's
meaning instead: the Flow planner's reading (its tone, emotion and the phrases
viewers search the theme by) or, when the planner had no Gemini reply or the
plan predates that reading, a local reading of the quote's own words. Each
phrase is then checked against YouTube's search suggestions, which cost no API
quota, and a phrase nobody types is dropped. When the suggestions cannot be
reached, only phrases the reading grounds are kept, and the package says so.

A live package for "The best way to not get your heart broken is to pretend
that you don't have one." shipped the single subject tag "pretend", and any
quote with "heart" in it got 💔, even "My heart finally healed". Here the
emoji, the feeling hashtag and the tags all follow the quote's tone.

Only AI Shorts uses this module: the shared writer and generator call it from
their ``title_style.startswith("ai_shorts:")`` branches, so the Creator page's
packages never pass through it.
"""

from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from typing import Any, Iterable

from win_engine.analysis.generation_quality import (
    description_prose,
    feeling_hashtag,
    has_unsupported_instructional_framing,
    title_body,
    title_emojis,
)
from win_engine.analysis.keyword_research import (
    natural_tag_phrase,
    synchronize_tag_evidence,
)
from win_engine.analysis.source_cues import is_negator
from win_engine.analysis.text_tokens import normalize_unicode, unicode_words
from win_engine.ingestion.search_suggest import demand_rank, normalize_phrase, suggestion_index

logger = logging.getLogger(__name__)

# The planner's tone vocabulary (flow_prompts' creative direction).
TONES = (
    "sad", "heartbroken", "lonely", "numb", "bittersweet", "hopeful", "healing",
    "uplifting", "empowering", "romantic", "calm", "nostalgic", "anxious", "angry",
)
# The emojis that fit each tone, the default first. A title emoji Gemini wrote
# is kept only when it is one of its tone's; otherwise the default replaces it.
# Each one renders as an emoji without a variation selector, except ❤️.
TONE_EMOJIS: dict[str, tuple[str, ...]] = {
    "heartbroken": ("💔", "🥀", "😢"),
    "numb": ("🖤", "🧊", "😶"),
    "lonely": ("🌙", "🖤", "😔"),
    "sad": ("😔", "😢", "🥀"),
    "bittersweet": ("🥀", "🍂", "💭"),
    "hopeful": ("🌅", "🌱", "✨"),
    "healing": ("🌱", "🌿", "🌅", "🤍"),
    "uplifting": ("✨", "🌟", "😊"),
    "empowering": ("💪", "🔥", "👑"),
    "romantic": ("❤️", "💕", "🌹"),
    "calm": ("🍃", "🤍", "😌"),
    "nostalgic": ("🍂", "🌙", "💭"),
    "anxious": ("💭", "🌀", "😶"),
    "angry": ("🔥", "😤", "⚡"),
}
# A quote whose tone could not be read reflects; it does not grieve.
NEUTRAL_EMOJIS = ("💭", "🤍", "✨")
# The hashtag quote viewers follow for each feeling (#healing for a healing
# quote, never #heartbreak because the quote says "heart").
TONE_HASHTAGS = {
    "sad": "#sadquotes", "heartbroken": "#heartbreak", "lonely": "#loneliness", "numb": "#deepquotes",
    "bittersweet": "#lifequotes", "hopeful": "#hope", "healing": "#healing", "uplifting": "#positivity",
    "empowering": "#motivation", "romantic": "#love", "calm": "#peace", "nostalgic": "#memories",
    "anxious": "#overthinking", "angry": "#attitude",
}
_PAIN_TONES = {"sad", "heartbroken", "lonely", "numb", "bittersweet"}
# A quote about heartbreak, said or denied: "to not get your heart broken" is
# not heartbreak felt (no 💔), but heartbreak is still what it is about.
_HEARTBREAK = (r"\bheart ?break|\bheartbroken\b|\bbroken heart\b|\bheart(?:'s)? broken\b|"
               r"\bbreak(?:s|ing)? (?:my|your|a) heart\b")
# The tones a theme word may speak for. A word alone does not decide the
# feeling: "I'm tired of trying to make people stay" has "trying" in it and is
# not motivation. A theme that does not fit the tone gives way to the tone's
# own hashtag and searches. A quote whose tone could not be read has no tone
# to contradict, so its words decide.
_MOTIVATION_TONES = frozenset({"empowering", "hopeful", "uplifting"})
_HEALING_TONES = frozenset({"healing", "hopeful", "bittersweet"})
_WORTH_TONES = frozenset(TONES) - {"romantic", "uplifting"}
_LONELY_TONES = frozenset({"lonely", "sad", "numb"})
_OVERTHINKING_TONES = frozenset({"anxious", "sad"})
_SELF_LOVE_TONES = frozenset({"healing", "hopeful", "uplifting", "empowering", "calm"})
_NUMBNESS_TONES = frozenset({"numb", "sad", "heartbroken", "lonely", "bittersweet", "anxious"})
_MOVING_ON_TONES = frozenset({"healing", "hopeful", "bittersweet", "sad", "empowering", "heartbroken"})
_MISSING_TONES = frozenset({"sad", "lonely", "bittersweet", "nostalgic", "heartbroken"})
_LOVE_TONES = frozenset({"romantic", "bittersweet", "nostalgic", "healing", "hopeful", "calm"})
_DARK_TONES_FOR_THEMES = frozenset({"sad", "heartbroken", "lonely", "numb"})


def _fits(tone: str, tones: frozenset[str]) -> bool:
    return not tone or tone in tones


# The quote's own themes, read from its words. These tables are the fallback
# for a plan without the planner's reading (Gemini down, or an older plan):
# the planner's hashtag and emojis lead whenever they are valid.
_WORTH = (r"\b(?:only love you when|useful to them|use(?:d)? (?:me|you)|your worth|self[- ]?worth)\b")
_RESPECT = (r"\b(?:stop explaining|explain(?:ing)? yourself|self[- ]?respect)\b|\bmisunderst\w*|"
            r"\b(?:doesn'?t|don'?t|does not|do not) value\b|\bvalue (?:you|your)\b")
_MOTIVATION = r"\bdisciplin\w*|\bproud\b|\btrying\b|\bkeep going\b|\bgive up\b|\bwork(?:ing)? hard\b"
_MOVING_ON = r"\bbetter without\b|\b(?:moved|moving|move) on\b|\blet(?:ting)? go\b"
_MISSING = r"\bmiss(?:ing)? (?:you|someone|him|her|them)\b"
_LOVE = r"\bhome\b.*\bperson\b|\bperson\b.*\bhome\b|\bmy person\b|\bin love\b|\bi love you\b|\bsoulmate\b"
# The hashtag of the quote's own theme, before the tone's, when it fits the
# tone: a quote about being used is #selfworth, though the shared table reads
# "love" in it as #love.
_THEME_HASHTAGS: tuple[tuple[str, str, frozenset[str]], ...] = (
    (_WORTH, "#selfworth", _WORTH_TONES),
    (_RESPECT, "#selfrespect", _WORTH_TONES),
    (r"\bself[- ]?love\b|\blove yourself\b", "#selflove", _SELF_LOVE_TONES),
    (_MOTIVATION, "#motivation", _MOTIVATION_TONES),
    (r"\bheal(?:ed|ing|s)?\b", "#healing", _HEALING_TONES),
    (_MOVING_ON, "#movingon", _MOVING_ON_TONES),
    (_MISSING, "#missingyou", _MISSING_TONES),
    (_LOVE, "#love", _LOVE_TONES),
    (r"\b(?:alone|lonely|loneliness)\b", "#loneliness", _LONELY_TONES),
    (r"\boverthink\w*", "#overthinking", _OVERTHINKING_TONES),
    (r"\b(?:mother|mom|mum|maa|amma)\b", "#mother", frozenset(TONES)),
    (r"\bfriend(?:s|ship)?\b", "#friendship", frozenset(TONES)),
    (r"\bgrat(?:eful|itude)\b|\bthankful\b", "#gratitude", frozenset(TONES)),
    (r"\benerg(?:y|ies)\b|\bvibes?\b|\battract\w*", "#positivevibes", frozenset(TONES) - _DARK_TONES_FOR_THEMES),
    (r"\bfamily\b", "#family", frozenset(TONES)),
)
# The emoji of the quote's own theme comes before its tone's: a self-respect
# quote is 👑, not the wilted 🥀 of a sad tone; a discipline quote is 💪, not 🌅.
_THEME_EMOJIS: tuple[tuple[str, tuple[str, ...], frozenset[str]], ...] = (
    (_MOTIVATION, ("💪", "🔥"), _MOTIVATION_TONES),
    (f"{_WORTH}|{_RESPECT}", ("👑", "💯"), _WORTH_TONES),
    (r"\bsilen(?:ce|t)\b", ("🤫", "🤍"), frozenset(TONES)),
    (rf"\bheal(?:ed|ing|s)?\b|{_MOVING_ON}", ("🌱", "🌿"), _MOVING_ON_TONES),
    (_LOVE, ("❤️", "🤍"), _LOVE_TONES),
    (_HEARTBREAK, ("💔", "🥀"), _PAIN_TONES),
    (r"\b(?:alone|lonely|loneliness)\b", ("🌙", "🖤"), _LONELY_TONES),
    (r"\boverthink\w*", ("💭", "🌀"), _OVERTHINKING_TONES),
    (_MISSING, ("💭", "🥀"), _MISSING_TONES),
)
# What an emoji must never be: the footage or a literal object ("🛑" for
# "stop", "🌧" for a rainy scene), or a feeling against the tone (🥀 on a
# hopeful quote, 💪 on a heartbroken one).
_LITERAL_EMOJIS = {
    "🛑", "🌧", "🔍", "⚓", "🚦", "🚗", "🚶", "🏙", "🌃", "🌆", "🌇", "📱", "⏰", "⌛", "🕰", "🎥", "🎬",
    "📷", "🌫", "🚪", "🚂", "🚆", "🌉", "☔", "🌂",
}
_PAIN_EMOJIS = {"💔", "😢", "😔", "🥀", "😞", "😭", "🖤", "😿"}
_BRIGHT_EMOJIS = {"💪", "✨", "🌟", "😊", "👑", "🔥", "🌅", "🌈", "🎉", "☀", "🌞", "💯", "🚀", "😄", "😁"}
_BRIGHT_TONES = frozenset({"hopeful", "healing", "uplifting", "empowering", "romantic", "calm"})
_DARK_TONES = frozenset({"sad", "heartbroken", "lonely", "numb"})
# The tones a hashtag the planner proposes may speak for; one not listed here
# is the planner's own reading and is taken as written.
_HASHTAG_TONES: dict[str, frozenset[str]] = {
    "#motivation": _MOTIVATION_TONES, "#healing": _HEALING_TONES, "#selfworth": _WORTH_TONES,
    "#selfrespect": _WORTH_TONES, "#loneliness": _LONELY_TONES, "#overthinking": _OVERTHINKING_TONES,
    "#selflove": _SELF_LOVE_TONES, "#heartbreak": frozenset(_PAIN_TONES | {"angry"}),
    "#sadquotes": frozenset(_PAIN_TONES | {"anxious"}), "#hope": frozenset({"hopeful", "healing", "uplifting", "empowering"}),
    "#positivity": frozenset({"uplifting", "hopeful", "empowering", "calm"}), "#movingon": _MOVING_ON_TONES,
    "#missingyou": _MISSING_TONES, "#love": _LOVE_TONES,
}
_PLANNER_HASHTAG = re.compile(r"#[a-z0-9]{3,24}")
_NOT_A_FEELING_HASHTAG = {
    "#shorts", "#short", "#quotes", "#quote", "#viral", "#trending", "#fyp", "#foryou", "#foryoupage",
    "#youtube", "#yt", "#reels", "#tiktok", "#explore", "#explorepage", "#tamilquotes",
}
# Tamil and Tanglish viewers search quotes in English letters ("tamil sad quotes");
# Hindi and Hinglish viewers search shayari ("hindi shayari").
_LANGUAGE_NICHES = {"tamil": "tamil", "tanglish": "tamil", "hindi": "hindi", "hinglish": "hindi"}
_NICHE_HASHTAGS = {"tamil": "#tamilquotes", "hindi": "#hindiquotes"}
# The only emojis a planner may choose: feelings, not the footage's objects.
# A live review saw 🪵, 🌊 and 🏔️ (wood, waves, a mountain) on quote titles.
_FEELING_EMOJIS = {
    "❤", "🧡", "💛", "💚", "💙", "💜", "🖤", "🤍", "🤎", "💔", "💕", "💞", "💓", "💗", "💖", "💘", "💝", "❣",
    "😔", "😢", "😭", "😞", "😊", "🙂", "😌", "🥹", "🥺", "😶", "😤", "😡", "🫠", "😇", "🥲", "😍", "🥰", "🤗",
    "🤫", "🤐", "😐", "🙃", "😏", "😒", "😕", "🙁", "😣", "😩", "😪", "😓", "🫂", "🙏",
    "✨", "🌟", "⭐", "💫", "🌱", "🌿", "🍀", "🌸", "🌼", "🌻", "🌷", "🌹", "🥀", "🍂", "🍁", "🍃",
    "🌙", "🌅", "☀", "🌞", "🌈", "🕊", "💪", "🔥", "👑", "💯", "🛡", "⚡", "🚀", "🏆", "💭", "🌀", "🧊", "🎭",
}
# Hashtags quote viewers follow. A planner's hashtag outside this list is used
# only when the suggestion check shows viewers type its words ("#longing" when
# "longing quotes" is typed); a coined one ("#emotionalwall") never is.
_ESTABLISHED_HASHTAGS = {
    "#heartbreak", "#brokenheart", "#selfworth", "#selfrespect", "#selflove", "#movingon", "#healing",
    "#motivation", "#love", "#lovequotes", "#friendship", "#family", "#mother", "#father", "#gratitude",
    "#positivevibes", "#lawofattraction", "#attitude", "#loneliness", "#overthinking", "#hope", "#tamilquotes",
    "#hindiquotes", "#shayari", "#sadquotes", "#missingyou", "#deepquotes", "#positivity", "#peace", "#memories",
    "#inspiration", "#discipline", "#mindset", "#success", "#selfcare", "#trust", "#betrayal", "#karma",
    "#faith", "#strength", "#kindness", "#happiness", "#breakup", "#relationship", "#goodvibes",
}
# Searched last: true of nearly every reflective quote.
_LAST_RESORT_HASHTAG = "#lifequotes"
# The package follows the reading's tone. A love quote that hurts ("only love
# can kill and keep you alive to feel it") shipped "romantic quotes", #love
# and ❤️: a mood search, hashtag or emoji against the tone is dropped.
_PAIN_READING = frozenset({"heartbroken", "sad", "lonely", "numb", "bittersweet", "angry", "anxious"})
_BRIGHT_READING = frozenset({"uplifting", "hopeful", "healing", "romantic", "calm"})
_CHEERFUL_WORDS = {"romantic", "romance", "happy", "happiness", "positive", "positivity", "uplifting", "cute",
                   "joy", "joyful", "cheerful"}
_CHEERFUL_PHRASES = ("good vibes",)
_SORROW_WORDS = {"sad", "sadness", "heartbreak", "heartbroken"}
_SORROW_PHRASES = ("broken heart",)
_WARM_EMOJIS = {"❤", "💕", "💞", "💖", "💗", "💘", "💝", "🥰", "😍", "😘", "🌅", "😊", "✨", "🌈", "🌞", "☀",
                "🎉", "🌟", "😄", "😁"}
# What viewers search for love that hurts.
_PAINFUL_LOVE_THEMES = ("love hurts quotes", "painful love quotes", "sad love quotes", "deep love quotes",
                        "heartbreak quotes")
CONTRADICTS_TONE = "contradicts_tone"


def contradicts_tone(theme: Any, tone: str) -> bool:
    """A mood search against the reading's tone: "romantic quotes" on a heartbroken quote, "sad quotes" on a hopeful one."""
    phrase = normalize_phrase(theme)
    words = set(phrase.split())
    if tone in _PAIN_READING:
        return bool(words & _CHEERFUL_WORDS) or any(f" {item} " in f" {phrase} " for item in _CHEERFUL_PHRASES)
    if tone in _BRIGHT_READING:
        return bool(words & _SORROW_WORDS) or any(f" {item} " in f" {phrase} " for item in _SORROW_PHRASES)
    return False
# Broad searches every quote of a feeling shares: useful, but after the phrases
# that name this quote's own theme.
_TONE_THEMES: dict[str, tuple[str, ...]] = {
    "sad": ("sad quotes", "deep quotes"),
    "heartbroken": ("heartbreak quotes", "broken heart quotes", "sad quotes"),
    "lonely": ("loneliness quotes", "lonely quotes", "sad quotes"),
    "numb": ("emotional numbness", "sad quotes", "deep quotes"),
    # A live bittersweet quote ("never meant to be, but I'm glad we happened")
    # had every planner phrase refused by the suggestion check and kept only
    # the broad two; what people type for such quotes leads.
    "bittersweet": ("moving on quotes", "life quotes", "deep quotes"),
    "hopeful": ("hope quotes", "positive quotes"),
    "healing": ("healing quotes", "moving on quotes", "self love quotes"),
    "uplifting": ("positive quotes", "happy quotes"),
    "empowering": ("motivational quotes", "inspirational quotes", "self motivation"),
    "romantic": ("love quotes", "romantic quotes"),
    "calm": ("peaceful quotes", "calm quotes"),
    "nostalgic": ("nostalgia quotes", "memories quotes"),
    "anxious": ("overthinking quotes", "anxiety quotes"),
    "angry": ("attitude quotes", "fake people quotes"),
}
_GENERIC_THEMES = {
    "sad quotes", "deep quotes", "life quotes", "positive quotes", "happy quotes", "motivational quotes",
    "inspirational quotes", "emotional quotes", "deep emotional quotes", "hope quotes", "hopeful quotes",
}
# Words that name a mood every quote of a feeling shares, not this quote's
# theme: "sad reality quotes" or "self motivation" is filler, "sad love quotes" is not.
_BROAD_WORDS = {
    "sad", "deep", "life", "positive", "happy", "motivational", "motivation", "inspirational", "inspiration",
    "emotional", "emotion", "emotions", "hope", "hopeful", "best", "good", "true", "real", "reality", "famous",
    "daily", "powerful", "meaningful", "beautiful", "feeling", "feelings", "mood", "heart", "touching", "self",
    "positivity", "nice", "new", "latest", "top", "short", "sadness",
    # Mood-only searches: "nostalgic quotes", "heartfelt quotes", "memories quotes".
    "nostalgic", "nostalgia", "heartfelt", "memories", "memory", "vibes", "soulful", "aesthetic",
}
_QUOTE_FORM_WORDS = {"quotes", "quote", "status", "lines", "sayings", "thoughts", "words"}
_LOCAL_THEME_POOL = 5
# The quote's own subject, read from its words: what this quote is searched by,
# with the tones it may speak for (see _fits).
_WORD_THEMES: tuple[tuple[str, tuple[str, ...], frozenset[str]], ...] = (
    (r"\bdisciplin", ("discipline quotes", "self discipline"), _MOTIVATION_TONES),
    (_HEARTBREAK, ("heartbreak quotes", "broken heart quotes"), _PAIN_TONES),
    (r"\b(?:stop explaining|explain(?:ing)? yourself)\b|\bmisunderst\w*",
     ("misunderstood quotes", "self respect quotes", "attitude quotes"), _WORTH_TONES),
    (r"\b(?:doesn'?t|don'?t|does not|do not) value\b|\bvalue (?:you|your)\b",
     ("self respect quotes", "self worth quotes"), _WORTH_TONES),
    (r"\bpretend(?:ing)?\b.*\b(?:don't|do not) (?:have|care|feel)\b|\bhid(?:e|ing) (?:my|your) feelings\b",
     ("hiding feelings", "emotional numbness"), _NUMBNESS_TONES),
    (r"\bproud\b", ("proud of yourself quotes", "self love quotes"), _MOTIVATION_TONES),
    (r"\b(?:keep|kept) (?:going|trying)\b|\btrying\b", ("keep going quotes",), _MOTIVATION_TONES),
    (r"\bheal(?:ed|ing|s)?\b", ("healing quotes", "self healing"), _HEALING_TONES),
    (r"\b(?:only love you when|useful to them|use(?:d)? (?:me|you))\b",
     ("fake people quotes", "being used quotes", "self worth quotes", "self respect quotes"), _WORTH_TONES),
    (r"\b(?:alone|lonely|loneliness)\b", ("loneliness quotes",), _LONELY_TONES),
    (r"\b(?:overthink(?:ing)?|anxiety)\b", ("overthinking quotes",), _OVERTHINKING_TONES),
    (r"\bmotivat", ("motivational quotes",), _MOTIVATION_TONES),
    (_MOVING_ON, ("moving on quotes",), _MOVING_ON_TONES),
    (_MISSING, ("missing someone quotes",), _MISSING_TONES),
    (_LOVE, ("love quotes",), _LOVE_TONES),
    (r"\bsilen(?:ce|t)\b", ("silence quotes",), frozenset(TONES)),
    (r"\bself[- ]?love\b|\blove yourself\b", ("self love quotes",), _SELF_LOVE_TONES),
)
# The tone a quote's own words carry, most specific first. A rule whose words
# the quote denies ("Don't cry", "to not get your heart broken") does not count.
_TONE_RULES: tuple[tuple[str, str], ...] = (
    ("numb", r"\bnumb\b|\bfeel(?:ing)? nothing\b|\bfelt nothing\b|\bstopped feeling\b|\bcan'?t feel\b|"
             r"\bpretend(?:ing)? (?:that )?(?:you|i|we) (?:don'?t|do not) (?:have|care|feel)\b|"
             r"\bact(?:ing)? like (?:you|i|we) (?:don'?t|do not) care\b|\bheartless\b|\bcold[- ]hearted\b"),
    ("healing", r"\bheal(?:ed|ing|s)?\b|\brecover(?:ed|ing)?\b|\b(?:moved|moving) on\b|\blet(?:ting)? go\b"),
    # Weariness and regret before the empowering words they contain: "tired of
    # trying", "not proud of who I became".
    ("lonely", r"\bmake (?:people|them|someone|anyone|him|her) stay\b|\beveryone leaves\b|\bpeople (?:always )?leave\b"),
    ("sad", r"\btired of\b|\bexhausted\b|\bworn out\b|\bdone trying\b|\bnot proud\b|\bashamed\b|"
            r"\bwho i (?:became|have become)\b|\bregret\w*"),
    # "proud" and "trying" are left out: "Be proud of how hard you are trying"
    # is gentle encouragement (hopeful, warm light), not the cold resolve of
    # discipline, and this reading overrides the planner's tone for empowering.
    ("empowering", r"\bdisciplin\w*|\bstrong(?:er)?\b|\bstrength\b|\bkeep going\b|\bgive up\b|"
                   r"\bstop explaining\b|\bexplain(?:ing)? yourself\b|\bself[- ]?respect\b|\byour worth\b|"
                   r"\bbelieve in yourself\b|\bwork(?:ing)? hard\b|\bsuccess\b|\bdeserve better\b|\bconsisten\w*"),
    ("hopeful", r"\bhope\w*|\btomorrow\b|\bsomeday\b|\bone day\b|\bbetter days\b|\bnew beginnings?\b|"
                r"\bproud of\b|\bdoing your best\b|\bhow hard you\b"),
    ("romantic", r"\bi love you\b|\bin love\b|\bsoulmate\b|\bmy love\b|\bfalling for\b"),
    ("heartbroken", r"\bheart ?break\w*|\bheartbroken\b|\bbroke my heart\b|\bbroken heart\b|\bheart(?:'s)? broken\b|"
                    r"\bbreak(?:s|ing)? (?:my|your) heart\b|\bgoodbye\b"),
    ("lonely", r"\balone\b|\blonely\b|\bloneliness\b|\bno ?one\b|\bnobody\b"),
    ("nostalgic", r"\bremember\w*|\bmemories\b|\bused to\b|\bback then\b|\bold days\b|\bchildhood\b"),
    ("anxious", r"\boverthink\w*|\banxi\w*|\bworr(?:y|ied)\b|\bpanic\b|\bcan'?t sleep\b"),
    ("angry", r"\bangry\b|\banger\b|\brage\b|\bhate\b|\bliars?\b|\bbetray\w*"),
    ("sad", r"\bsad\w*|\bcry\w*|\btears?\b|\bhurt\w*|\bpain\w*|\bbroken\b|\blost\b|\bmiss\w*|"
            r"\bonly love you when\b|\buseful to them\b|\bused (?:me|you)\b"),
    ("calm", r"\bpeace\w*|\bcalm\b|\bbreathe\b|\bslow down\b|\bstillness\b"),
    ("uplifting", r"\bsmile\w*|\bhapp(?:y|iness)\b|\bgrateful\b|\bgratitude\b|\bjoy\w*|\bblessed\b"),
)
# Words a phrase viewers search for a quote's theme never carries.
_BANNED_THEME_WORDS = {
    "short", "shorts", "yt", "youtube", "video", "videos", "viral", "trending", "fyp", "tiktok", "reel", "reels",
    "status", "whatsapp", "instagram", "aesthetic", "edit", "ai", "background", "footage", "flow", "veo",
}
MAX_SUBJECT_TAGS = 5
# A theme phrase viewers type can be a long tail ("everything happens for a
# reason quotes"); the shared 30-character cap for a Short's tags exists to stop
# glued or junk tags, and these phrases are checked against real searches.
MAX_THEME_WORDS = 6
MAX_THEME_TAG_CHARS = 45
_PLATFORM_TAGS = ("yt", "shorts")
_SINGLE_LINE = re.compile(r"\s+")


def _clean_line(value: Any, limit: int = 300) -> str:
    """One line of planner text, safe to quote in a prompt."""
    return _SINGLE_LINE.sub(" ", normalize_unicode(value)).strip()[:limit]


def _affirmed(pattern: str, text: str) -> bool:
    """True when a match of ``pattern`` is not denied by a negator just before it."""
    for match in re.finditer(pattern, text, re.IGNORECASE):
        before = unicode_words(text[:match.start()], min_length=1)[-3:]
        # The pattern may carry its own negation ("pretend that you don't have").
        if not any(is_negator(word) for word in before):
            return True
    return False


def local_tone(quote: Any) -> str:
    """The tone the quote's own words carry, or "" when none can be read.

    Negation-aware: "to not get your heart broken" is not heartbreak, and
    "Don't cry" is not sadness.
    """
    text = normalize_unicode(quote).replace("’", "'").casefold()
    for tone, pattern in _TONE_RULES:
        if _affirmed(pattern, text):
            return tone
    return ""


def clean_theme(value: Any) -> str:
    """A search phrase as a tag: lowercase, 2-6 words, short, natural, nothing platform-ish; else ""."""
    phrase = normalize_phrase(value)
    words = phrase.split()
    if not 2 <= len(words) <= MAX_THEME_WORDS or len(phrase) > MAX_THEME_TAG_CHARS:
        return ""
    if any(word in _BANNED_THEME_WORDS for word in words) or not natural_tag_phrase(phrase):
        return ""
    if not re.fullmatch(r"[a-z0-9' ]+", phrase):
        return ""
    return phrase


def _local_themes(quote: str, tone: str) -> list[str]:
    text = normalize_unicode(quote).replace("’", "'").casefold()
    themes: list[str] = []
    for pattern, phrases, tones in _WORD_THEMES:
        if not _fits(tone, tones):
            continue
        about_heartbreak = pattern == _HEARTBREAK and tone in _PAIN_TONES and re.search(pattern, text)
        if about_heartbreak or _affirmed(pattern, text):
            themes.extend(phrases)
    themes = list(dict.fromkeys(theme for theme in (clean_theme(item) for item in themes) if theme))
    # The tone's broad searches fill the list up to five candidates: enough for
    # three to survive the suggestion check, without burying the quote's own theme.
    for theme in _TONE_THEMES.get(tone, ("deep quotes", "life quotes")):
        if len(themes) < _LOCAL_THEME_POOL and theme not in themes:
            themes.append(theme)
    return themes


def quote_understanding(quote: str, plan: dict[str, Any] | None = None, *, language: str = "english") -> dict[str, Any]:
    """The quote's meaning, tone, emotion and search themes: the planner's reading when it has one.

    ``plan["creative_direction"]`` carries quote_meaning, emotion, tone (one of
    TONES) and search_themes when the planner's Gemini call answered. A plan
    without them (Gemini down, or a plan saved before the reading existed) is
    read locally from the quote. Themes the quote's own words name are added
    after the planner's, so a short planner list is still checked against
    real searches.
    """
    direction = (plan or {}).get("creative_direction")
    direction = direction if isinstance(direction, dict) else {}
    # The planner keeps its reading apart from the scene: a scene it threw away
    # as a symbol leaves no creative direction, but the meaning, tone and
    # searches it read still hold.
    understanding = (plan or {}).get("quote_understanding")
    if isinstance(understanding, dict):
        direction = {**understanding, **{key: value for key, value in direction.items() if value}}
    planner_tone = _clean_line(direction.get("tone"), 40).casefold()
    tone = planner_tone if planner_tone in TONES else local_tone(quote)
    raw_themes = direction.get("search_themes")
    planner_themes = [
        theme for theme in (clean_theme(item) for item in (raw_themes if isinstance(raw_themes, list) else [])[:8])
        if theme
    ]
    # A Tamil or Tanglish Short is found by "tamil ... quotes": those lead after
    # the planner's first two themes, so the suggestion check always asks them.
    niche = _language_themes(language, tone)
    # A heartbroken or bittersweet quote that names love is searched as love
    # that hurts, never as romance.
    folded = normalize_unicode(quote).replace("’", "'").casefold()
    painful_love = (list(_PAINFUL_LOVE_THEMES)
                    if tone in {"heartbroken", "bittersweet"} and re.search(r"\blov(?:e|es|ed|ing)\b", folded) else [])
    # Then "<subject> quotes" for the quote's own subject words ("mother
    # quotes", "friendship quotes"): the obvious searches a reading can miss.
    themes = list(dict.fromkeys([
        *planner_themes[:2], *niche, *painful_love, *planner_themes[2:4], *_subject_themes(quote),
        *planner_themes[4:], *_local_themes(quote, tone),
    ]))
    return {
        "tone": tone,
        "tone_source": "planner" if planner_tone in TONES else ("quote_words" if tone else "unread"),
        "emotion": _clean_line(direction.get("emotion"), 60),
        "meaning": _clean_line(direction.get("quote_meaning")),
        "language": str(language or "english").strip().casefold() or "english",
        "planner_themes": planner_themes,
        "priority_themes": list(dict.fromkeys([*planner_themes, *niche, *painful_love])),
        "niche_themes": niche,
        # Kept only when viewers type them (verify_subject_tags): a quote word
        # alone is no evidence that anyone searches it.
        "subject_themes": _subject_themes(quote),
        "planner_hashtag": _planner_hashtag(direction.get("hashtag"), tone),
        "planner_emojis": _planner_emojis(direction.get("emojis"), tone),
        "search_themes": themes,
    }


def _language_themes(language: str, tone: str) -> list[str]:
    niche = _LANGUAGE_NICHES.get(str(language or "").strip().casefold())
    if not niche:
        return []
    flavour = ("sad" if tone in _PAIN_TONES else "love" if tone == "romantic"
               else "motivational" if tone in _MOTIVATION_TONES else "")
    phrases = [*([f"{niche} {flavour} quotes"] if flavour else []), f"{niche} quotes"]
    if niche == "hindi":
        phrases = ["hindi shayari", *phrases]
    return [phrase for phrase in (clean_theme(item) for item in phrases) if phrase]


# Words of a quote that name no subject a viewer searches: grammar, common
# verbs and adverbs. What is left ("mother", "storm", "goodbye") is tried as
# "<word> quotes"; the suggestion check drops the ones nobody types.
_NOT_A_SUBJECT = {
    "about", "above", "after", "again", "against", "always", "another", "anyone", "anything", "around", "because",
    "become", "becomes", "been", "before", "being", "best", "better", "between", "both", "cannot", "could",
    "decided", "doesn't", "doing", "don't", "down", "during", "each", "even", "ever", "every", "everyone",
    "everything", "explaining", "feel", "feels", "finally", "from", "gets", "give", "going", "gone", "good", "have",
    "having", "here", "into", "just", "keep", "know", "knows", "last", "least", "less", "like", "little", "long",
    "made", "make", "makes", "many", "might", "more", "most", "much", "must", "myself", "never", "nothing", "notice",
    "often", "once", "only", "other", "others", "ourselves", "over", "people", "place", "pretend", "rather", "really",
    "same", "should", "show", "since", "some", "someone", "something", "sometimes", "still", "such", "take", "than",
    "that", "their", "them", "themselves", "then", "there", "these", "they", "thing", "things", "think", "this",
    "those", "though", "through", "today", "together", "too", "trying", "under", "until", "used", "useful", "very",
    "want", "wants", "was", "way", "well", "were", "what", "when", "where", "which", "while", "who", "whole", "will",
    "with", "without", "won't", "would", "yet", "you're", "your", "yours", "yourself", "already", "answer",
    "hardest", "favorite", "favourite", "wonderful", "true", "real", "best", "worst", "great", "hard", "heavy",
    "find", "found", "gave", "given", "leave", "leaves", "left", "lose", "losing", "lost", "stay", "stays", "stayed",
    "drain", "protect", "choose", "chose", "hold", "held", "tell", "told", "said", "says", "need", "needs", "tried",
    "care", "cares", "change", "learn", "carry", "wait", "forget", "remember", "believe", "mean", "means", "meant",
    "matter", "matters", "deserve", "deserves", "start", "stop", "walk", "come", "comes", "came", "look", "looks",
    "seem", "seems", "turn", "turns", "harder", "easier", "stronger", "bigger", "deeper", "louder", "quieter",
    "softer", "kinder", "longer", "closer", "sooner", "later", "reason", "words", "while", "around",
}
# A subject word whose search viewers type in another form.
_SUBJECT_FORMS = {
    "friend": "friendship", "friends": "friendship", "mom": "mother", "mum": "mother", "maa": "mother",
    "energy": "positive energy", "goodbyes": "goodbye", "memories": "memories", "dreams": "dream",
}


def _subject_themes(quote: str, limit: int = 3) -> list[str]:
    """"<subject> quotes" for the quote's own content words, checked later against what viewers type."""
    found: list[str] = []
    for word in _flat_words(quote).split():
        if len(word) < 4 or word in _NOT_A_SUBJECT or word in _BROAD_WORDS or word.endswith(("ly", "ed", "ing")):
            continue
        phrase = clean_theme(f"{_SUBJECT_FORMS.get(word, word)} quotes")
        if phrase and phrase not in found:
            found.append(phrase)
        if len(found) >= limit:
            break
    return found


def _planner_hashtag(value: Any, tone: str) -> str:
    """The planner's feeling hashtag when it is one viewers follow and it fits the tone; else ""."""
    text = _clean_line(value, 40).casefold().replace(" ", "")
    if text and not text.startswith("#"):
        text = f"#{text}"
    if not _PLANNER_HASHTAG.fullmatch(text) or text in _NOT_A_FEELING_HASHTAG:
        return ""
    return text if _fits(tone, _HASHTAG_TONES.get(text, frozenset(TONES))) else ""


def _emoji_fits_tone(emoji: str, tone: str) -> bool:
    base = _base(emoji)
    if base in _LITERAL_EMOJIS:
        return False
    if tone in _PAIN_READING and base in _WARM_EMOJIS:
        return False
    if tone in _BRIGHT_TONES and base in _PAIN_EMOJIS:
        return False
    return not (tone in _DARK_TONES and base in _BRIGHT_EMOJIS)


def _planner_emojis(value: Any, tone: str) -> list[str]:
    """The planner's emojis (up to three) that are one emoji each, not the footage, and not against the tone."""
    kept: list[str] = []
    for item in (value if isinstance(value, list) else [value] if isinstance(value, str) else [])[:3]:
        text = _clean_line(item, 16)
        found = title_emojis(text)
        if (len(found) != 1 or len(_flat_words(text)) or _base(found[0]) not in _FEELING_EMOJIS
                or not _emoji_fits_tone(found[0], tone)):
            continue
        emoji = text.replace(" ", "")
        if emoji and _base(emoji) not in {_base(other) for other in kept}:
            kept.append(emoji)
    return kept


def understanding_of(brief: dict[str, Any] | None, quote: str = "") -> dict[str, Any]:
    """The reading the brief carries, or a local one for a brief built without it."""
    reading = (brief or {}).get("ai_shorts")
    if isinstance(reading, dict) and "tone" in reading:
        return reading
    return quote_understanding(quote or str((brief or {}).get("exact_quote") or ""),
                               language=str((brief or {}).get("language") or "english"))


def _base(emoji: str) -> str:
    return re.sub(r"[︎️‍]", "", emoji)


def repeated_emoji(recent_titles: Iterable[str]) -> str:
    """The emoji the quality gate would reject as a template: the one its three compared recent titles all end with.

    The gate compares a title's emojis with the last three of the recent
    titles it is given; a title with that same single emoji is rejected.
    """
    recent = [str(item) for item in recent_titles or [] if str(item or "").strip()]
    signatures = ["".join(title_emojis(title)) for title in recent[-3:]]
    if len(signatures) == 3 and signatures[0] and all(item == signatures[0] for item in signatures):
        return signatures[0]
    return ""


def emoji_candidates(reading: dict[str, Any], quote: str) -> list[str]:
    """The emojis that fit this quote, best first: the planner's, then its theme's, then its tone's."""
    tone = str(reading.get("tone") or "")
    text = normalize_unicode(quote).replace("’", "'").casefold()
    found: list[str] = [str(item) for item in reading.get("planner_emojis") or [] if str(item).strip()]
    theme = next((emojis for pattern, emojis, tones in _THEME_EMOJIS
                  if _fits(tone, tones) and _affirmed(pattern, text)), ())
    found.extend(emoji for emoji in theme if _emoji_fits_tone(emoji, tone))
    found.extend(TONE_EMOJIS.get(tone, NEUTRAL_EMOJIS))
    unique: dict[str, str] = {}
    for emoji in found:
        unique.setdefault(_base(emoji), emoji)
    return list(unique.values())


def _pick_emoji(candidates: list[str], written: Iterable[str], *, hard: set[str], soft: set[str], used: set[str]) -> str:
    """The writer's emoji when it fits and is free, else the best free candidate.

    ``hard`` would be rejected by the quality gate as a repeated template;
    ``soft`` led the last saved AI Shorts and ``used`` is on another title of
    this package, so each is skipped while another candidate is left.
    """
    by_base = {_base(item): item for item in candidates}
    for emoji in written:
        base = _base(emoji)
        if base in by_base and base not in hard | soft | used:
            return by_base[base]
    for blocked in (hard | soft | used, hard | used, hard):
        choice = next((item for item in candidates if _base(item) not in blocked), "")
        if choice:
            return choice
    return candidates[0]


def style_title(
    title: str, quote: str, brief: dict[str, Any] | None = None, recent_titles: Iterable[str] = (),
    used: Iterable[str] = (),
) -> str:
    """The AI Shorts title style: the body as written, then one emoji fitting the quote and #shorts.

    The emoji is the planner's when it fits, else the quote's theme's, else
    its tone's (see emoji_candidates); a written one is kept only when it is
    among them. A longer title than YouTube's 100 characters is returned as
    written rather than cut to make room for decoration.
    """
    reading = understanding_of(brief, quote)
    body = re.sub(r"(?i)#shorts\b", "", title).strip()
    emojis = title_emojis(body)
    hard = {_base(item) for item in [*(reading.get("avoid_emojis") or []), repeated_emoji(recent_titles)] if item}
    soft = {_base(item) for item in reading.get("recent_emojis") or [] if item}
    emoji = _pick_emoji(emoji_candidates(reading, quote), emojis, hard=hard, soft=soft,
                        used={_base(item) for item in used if item})
    for existing in emojis:
        body = body.replace(existing, "")
    body = re.sub(r"[︎️‍]", "", body)
    body = re.sub(r"\s+", " ", body).strip()
    # "...notice when. 🌅" reads as a typo. A question mark or "!" carries
    # meaning and stays, and so does "...", which the gate must still see.
    body = re.sub(r"(?<!\.)[.,;:]$", "", body).rstrip()
    styled = f"{body} {emoji} #shorts"
    return styled if len(styled) <= 100 else title


# The exact quote leads up to about 90 characters: with an emoji and #shorts
# that is still inside YouTube's 100.
WHOLE_QUOTE_TITLE_CHARS = 90
SHORT_PRIMARY_CHARS = 30


def _title_key(title: str) -> str:
    return _flat_words(title_body(title))


def is_exact_quote(title: str, quote: str) -> bool:
    """The title says the quote word for word (emoji, #shorts, case and punctuation aside)."""
    return bool(_flat_words(quote)) and _title_key(title) == _flat_words(quote)


def near_verbatim(title: str, quote: str) -> bool:
    """Almost the quote, but a word dropped or changed: "...to people who decided to misunderstand you" without "already".

    A near-quote reads as a misquote; it is worse than either the exact quote
    or a clear paraphrase.
    """
    quote_words = _flat_words(quote).split()
    title_words = _title_key(title).split()
    if len(quote_words) < 4 or title_words == quote_words:
        return False
    blocks = SequenceMatcher(None, quote_words, title_words, autojunk=False).get_matching_blocks()
    return sum(block.size for block in blocks) / len(quote_words) >= 0.85


MIN_TITLE_OPTIONS = 3
_CLAUSE_BREAK_RE = re.compile(r"\s*[,;:—–]\s*|\s+(?:but|yet|and|because|so)\s+", re.IGNORECASE)


def quote_clauses(quote: str) -> list[str]:
    """The quote's own complete clauses, its punchline (the last) first: faithful local title options."""
    whole = re.sub(r"\s+", " ", normalize_unicode(quote)).strip()
    parts = [part.strip(" .!?…\"'“”") for part in _CLAUSE_BREAK_RE.split(re.sub(r"[.!?…]+$", "", whole))]
    clauses = [part[:1].upper() + part[1:] for part in parts if len(part.split()) >= 3]
    if len(clauses) < 2:
        return []
    return list(dict.fromkeys([clauses[-1], *clauses[:-1]]))


def order_titles(
    titles: Iterable[str], quote: str, brief: dict[str, Any] | None = None, recent_titles: Iterable[str] = (),
) -> list[str]:
    """The styled titles: the exact quote first when it fits about 90 characters, short ones after longer ones.

    A live primary was "Stop explaining yourself 🛑 #shorts", the quote cut
    before its turn; another dropped a word of the quote. A near-quote gives
    way to the exact quote, or is dropped when the quote is too long to lead.
    A title under 30 characters says too little to lead; it stays as an
    alternative. The emojis rotate, so the alternatives do not all share one.
    """
    recent = list(recent_titles or [])
    whole = re.sub(r"\s+", " ", normalize_unicode(quote)).strip()
    fits = bool(whole) and len(re.sub(r"(?<!\.)[.,;:]$", "", whole)) <= WHOLE_QUOTE_TITLE_CHARS
    written = [str(title) for title in titles if str(title or "").strip()]
    kept = [title for title in written if not near_verbatim(title, quote)]
    bodies = [whole] if fits else []
    seen = {_title_key(whole)} if fits else set()
    for title in kept:
        if _title_key(title) not in seen:
            seen.add(_title_key(title))
            bodies.append(title)
    bodies = bodies or written[:1]
    # At least three options: when the writer gave fewer, the quote's own
    # clauses (its punchline first) stand in; the final gate still judges each.
    for clause in quote_clauses(quote):
        if len(bodies) >= MIN_TITLE_OPTIONS:
            break
        if _title_key(clause) not in {_title_key(title) for title in bodies}:
            bodies.append(clause)
    ordered = sorted(bodies, key=lambda title: not is_exact_quote(title, quote)
                     and len(title_body(title)) < SHORT_PRIMARY_CHARS)[:5]
    styled: list[str] = []
    used: list[str] = []
    for title in ordered:
        result = style_title(title, quote, brief, recent, used=used)
        styled.append(result)
        used.extend(title_emojis(result))
    return list(dict.fromkeys(styled))


def meaningful_tag(tag: Any) -> bool:
    """A subject tag a viewer of a quote Short searches: a phrase, not a lone word or a format tag."""
    text = normalize_phrase(tag)
    return text not in _PLATFORM_TAGS and len(text.split()) >= 2


def is_generic_tag(tag: Any) -> bool:
    """A filler search every quote of a feeling shares ("deep quotes", "sad reality quotes", "self motivation")."""
    text = normalize_phrase(tag)
    words = [word for word in text.split() if word not in _QUOTE_FORM_WORDS]
    return text in _GENERIC_THEMES or not words or all(word in _BROAD_WORDS for word in words)


MIN_GREEN_SUBJECT_TAGS = 3
MIN_GREEN_SPECIFIC_TAGS = 2


# One reflective question per tone, for a description left with the quote
# alone. Each speaks to the viewer about the quote and adds nothing to it: no
# scene, no person, no event, and none of the context words the quality gate
# refuses for a reflective quote (love, peace, healing, night...).
_REFLECTION_QUESTIONS = {
    "sad": "Have you ever felt this way?",
    "heartbroken": "Have you ever felt this way?",
    "lonely": "Have you ever felt this way?",
    "numb": "Have you ever felt this way?",
    "bittersweet": "Does this feel familiar?",
    "hopeful": "What are you still hoping for?",
    "healing": "Have you noticed how far you have come?",
    "uplifting": "Who needs to hear this today?",
    "empowering": "Who needs to hear this today?",
    "romantic": "Who comes to mind when you read this?",
    "calm": "How does this sit with you today?",
    "nostalgic": "What does this bring back for you?",
    "anxious": "Does this sound familiar?",
    "angry": "Have you been through this too?",
}
_DEFAULT_REFLECTION = "What does this mean to you?"


def _flat_words(value: Any) -> str:
    return " ".join(unicode_words(normalize_unicode(value).replace("’", "'"), min_length=1)).casefold()


# The creator's format tags leaked into a live description's prose
# ("...becomes a memory. yt"); the line formatter only drops a line that is
# nothing but a platform word.
_PLATFORM_WORD_RE = re.compile(r"(?i)(?<![#\w])(?:yt|youtube\s+shorts?)(?![\w'])")
_TRAILING_SHORTS_RE = re.compile(r"(?i)(?<=[.!?…”\"])\s+#?shorts\s*$")
_HASHTAG_LINE_RE = re.compile(r"\s*(?:#[^\s#]+\s*)+")


def strip_platform_words(description: str, quote: str = "") -> str:
    """The description without "yt" or a trailing "shorts" in its prose; hashtag lines and the quote stay as written."""
    flat_quote = _flat_words(quote)
    lines: list[str] = []
    for line in str(description or "").splitlines():
        if _HASHTAG_LINE_RE.fullmatch(line) or (flat_quote and _flat_words(line) == flat_quote):
            lines.append(line)
            continue
        cleaned = re.sub(r"[ \t]{2,}", " ", _TRAILING_SHORTS_RE.sub("", _PLATFORM_WORD_RE.sub("", line))).rstrip()
        # A line left with nothing but a platform word goes with it.
        if line.strip() and re.fullmatch(r"\s*(?:#?shorts?\s*)*", cleaned):
            continue
        lines.append(cleaned)
    return "\n".join(lines).strip()


def with_reflection(description: str, quote: str, brief: dict[str, Any] | None = None) -> str:
    """The description's prose with a reflective line after the quote: the writer's when one survived, else a safe question.

    A live healed-quote package shipped the quote and its hashtags only. The
    question comes from the quote's tone and claims nothing about the video.
    Platform words in the prose are dropped (strip_platform_words). The
    hashtag line is added back by format_upload_ready_description.
    """
    prose = description_prose(strip_platform_words(description, quote))
    flat_quote = _flat_words(quote)
    if not flat_quote:
        return prose or description
    remainder = f" {_flat_words(prose)} ".replace(f" {flat_quote} ", " ", 1).split()
    if len(remainder) >= 3:
        return prose
    reading = understanding_of(brief, quote)
    question = _REFLECTION_QUESTIONS.get(str(reading.get("tone") or ""), _DEFAULT_REFLECTION)
    return f"{prose}\n\n{question}".strip()


def ai_short_hashtags(brief: dict[str, Any] | None, quote: str) -> list[str]:
    """#shorts, #quotes (#tamilquotes for a Tamil or Tanglish Short) and the hashtag of the quote's feeling.

    The feeling hashtag is the planner's when it is valid and fits the tone;
    else the quote's own theme's, read from its words; else #heartbreak when
    its words are about heartbreak; else the tone's. A planner search theme
    never overrides the quote's own theme: "heartbreak quotes" among the
    searches made a quote about being used #heartbreak instead of #selfworth.
    """
    reading = understanding_of(brief, quote)
    tone = str(reading.get("tone") or "")
    text = normalize_unicode(quote).replace("’", "'").casefold()
    theme_tag = next(
        (tag for pattern, tag, tones in _THEME_HASHTAGS if _fits(tone, tones) and _affirmed(pattern, text)), "",
    )
    heartbreak = "#heartbreak" if tone in _PAIN_TONES and re.search(_HEARTBREAK, text) else ""
    feeling = (_accepted_planner_hashtag(reading) or theme_tag or heartbreak
               or TONE_HASHTAGS.get(tone) or feeling_hashtag(quote) or "#deepquotes")
    if tone in _PAIN_READING and feeling in {"#love", "#heartbreak"}:
        # Love that hurts is followed as #lovehurts when viewers type it, else
        # #heartbreak; #love is for a quote whose love does not hurt.
        typed = {str(item) for item in ((reading.get("search_demand") or {}).get("validated_keywords") or [])}
        feeling = "#lovehurts" if "love hurts quotes" in typed else "#heartbreak"
    niche = _NICHE_HASHTAGS.get(_LANGUAGE_NICHES.get(str(reading.get("language") or ""), ""), "#quotes")
    return list(dict.fromkeys(["#shorts", niche, feeling]))


def _accepted_planner_hashtag(reading: dict[str, Any]) -> str:
    """The planner's hashtag when viewers follow it: an established quote hashtag, or one whose words they type.

    #lifequotes fits nearly every quote, so it is left to the end of the line.
    """
    hashtag = str(reading.get("planner_hashtag") or "")
    if not hashtag or hashtag == _LAST_RESORT_HASHTAG:
        return ""
    if hashtag in _ESTABLISHED_HASHTAGS:
        return hashtag
    body = hashtag.lstrip("#")
    typed = {str(item).replace(" ", "") for item in ((reading.get("search_demand") or {}).get("validated_keywords") or [])}
    return hashtag if body in typed or f"{body}quotes" in typed else ""


def writer_guidance(brief: dict[str, Any] | None) -> str:
    """The quote's reading for the package writer: meaning, feeling, the tone's emojis and the searches it is found by."""
    reading = understanding_of(brief, str((brief or {}).get("exact_quote") or ""))
    lines: list[str] = []
    if reading.get("meaning"):
        lines.append(f"The quote means: {reading['meaning']}")
    tone = str(reading.get("tone") or "")
    if tone:
        feeling = f"{reading['emotion']} ({tone})" if reading.get("emotion") else tone
        palette = " ".join(emoji_candidates(reading, str((brief or {}).get("exact_quote") or ""))[:4])
        lines.append(f"Its feeling: {feeling}. A title's emoji fits that feeling, for example one of {palette}.")
    verified = [str(row.get("keyword")) for row in reading.get("subject_tags") or [] if isinstance(row, dict)]
    themes = verified or list(reading.get("search_themes") or [])[:MAX_SUBJECT_TAGS]
    if themes:
        lines.append("Viewers search this quote's theme as: " + ", ".join(themes)
                     + ". Use the ones true of this quote as tags; do not build a title around a search phrase.")
    # A live reflective line for "Home is not a place, it's a person" added
    # someone "sitting far away", a scene the quote never states.
    lines.append("The description's reflective line speaks to the viewer about the quote's feeling and adds no "
                 "place, person, event or time the quote does not state.")
    return " " + " ".join(lines)


# How a theme is tied to the quote, strongest first. A suggestion only proves
# a phrase exists, not that it fits: "football quotes" is typed by thousands
# and has nothing to do with a heartbreak quote. A theme with none of these
# ties is never a tag.
_RELATIONS: dict[str, tuple[int, str]] = {
    "quote_words": (90, "Every topic word is the quote's own"),
    "planner_reading": (78, "Every topic word is the quote's or the planner's reading of it (its meaning or emotion)"),
    "language": (75, "The Short's language niche"),
    # The weakest tie, at the shared final gate's evidence floor (70): one
    # point lower and the gate dropped every niche search ("moving on quotes"
    # on a healing quote) whose words the quote does not use.
    "quote_niche": (70, "Every topic word is the quote's, its reading's, or the quote niche's common vocabulary"),
}
UNRELATED = "unrelated_to_quote"
# Words that tie nothing: grammar, and the filler of a search ("best ... status").
_RELATION_STOP = {
    "the", "and", "you", "your", "yours", "are", "was", "were", "for", "but", "not", "with", "that", "this", "they",
    "them", "their", "have", "has", "had", "can", "could", "would", "should", "will", "just", "only", "one", "who",
    "what", "when", "where", "why", "how", "its", "it's", "our", "his", "her", "him", "she", "from", "into", "than",
    "then", "there", "these", "those", "some", "any", "all", "out", "about", "don't", "doesn't", "didn't", "won't",
    "can't", "i'm", "you're", "it's", "best", "top", "new", "latest", "status", "short", "shorts", "good", "nice",
    "famous", "daily", "real", "true", "whatsapp", "way", "get", "got", "too", "very", "even", "still",
}


def _stem(word: str) -> str:
    word = word.casefold().replace("'", "")
    for suffix in ("ingly", "edly", "ness", "ment", "ings", "ing", "ies", "ied", "ed", "es", "s", "ly"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def _stems(text: Any, *, drop: set[str] = frozenset()) -> set[str]:
    return {_stem(word) for word in _flat_words(text).split()
            if len(word) >= 3 and word not in _RELATION_STOP and word not in drop}


def _shares_stem(left: set[str], right: set[str]) -> bool:
    """One word's stem is the other's, or begins it ("heart" and "heartbreak"), at four letters or more."""
    for one in left:
        for other in right:
            short, long = sorted((one, other), key=len)
            if short == long or (len(short) >= 4 and long.startswith(short)):
                return True
            # Two forms of one long word: "misunderstood" and "misunderstand".
            shared = len(_common_prefix(one, other))
            if shared >= 6 and shared >= len(short) - 3:
                return True
    return False


def _common_prefix(left: str, right: str) -> str:
    size = 0
    for a, b in zip(left, right):
        if a != b:
            break
        size += 1
    return left[:size]


# Grammar a search phrase is built with; it carries no topic.
_CONNECTORS = {
    "of", "for", "about", "the", "a", "an", "and", "or", "my", "your", "to", "in", "on", "at", "by", "with",
    "without", "from", "is", "are", "be", "being", "you", "me", "i", "we", "our", "their", "his", "her", "its",
    "it", "this", "that", "yourself", "myself", "when", "who", "what", "how", "why", "after", "before",
}
# The quote niche's own vocabulary: feelings, relationships, life and
# self-growth. A theme word outside it and outside the quote and its reading
# ("surgery", "disease", "football") makes the whole theme unrelated, even
# when another of its words is the quote's ("heart surgery quotes").
_NICHE_WORDS = {
    *TONES,
    "love", "lover", "loving", "romance", "crush", "soulmate", "heart", "heartbreak", "broken", "pain", "hurt",
    "tears", "cry", "crying", "sadness", "alone", "loneliness", "silence", "silent", "quiet", "peace", "peaceful",
    "hope", "faith", "god", "prayer", "healing", "heal", "moving", "letting", "go", "keep", "going", "self",
    "respect", "worth", "value", "confidence", "attitude", "ego", "pride", "proud", "motivation", "motivational",
    "inspirational", "inspiration", "empowerment", "discipline", "success", "failure", "effort", "trying", "hard",
    "work", "strength", "strong", "power", "mindset", "positive", "positivity", "energy", "vibes", "good",
    "gratitude", "grateful", "thankful", "happy", "happiness", "joy", "smile", "laugh", "memories", "memory",
    "nostalgia", "past", "future", "time", "moments", "life", "lesson", "lessons", "truth", "reality", "trust",
    "betrayal", "loyalty", "cheating", "lies", "fake", "true", "real", "people", "person", "special", "someone",
    "friends", "friend", "friendship", "best", "family", "mother", "mom", "amma", "father", "dad", "appa", "son",
    "daughter", "child", "children", "kids", "parents", "sister", "brother", "wife", "husband", "girlfriend",
    "boyfriend", "couple", "relationship", "relationships", "marriage", "breakup", "missing", "miss", "goodbye",
    "goodbyes", "overthinking", "anxiety", "deep", "emotional", "emotions", "feelings", "feeling", "numbness",
    "hiding", "used", "regret", "forgive", "forgiveness", "kindness", "patience", "freedom", "karma", "destiny",
    "fate", "dreams", "dream", "goals", "growth", "change", "journey", "soul", "misunderstood", "care",
    "tamil", "hindi", "shayari", "anbu", "kadhal", "heartfelt", "inner", "painful",
}
# Established phrases whose other words count as the niche's once one of
# them is the quote's or its reading's: "law of attraction quotes" for a quote
# about attracting what you think, never for a heartbreak quote.
_NICHE_PHRASES = ("law of attraction",)


def _topic_words(phrase: str) -> list[str]:
    return [word for word in phrase.split() if word not in _QUOTE_FORM_WORDS and word not in _CONNECTORS]


def theme_relation(theme: Any, reading: dict[str, Any], quote: str) -> str:
    """How a candidate theme is tied to the quote (a key of _RELATIONS), or "" when it is not.

    The whole phrase is judged, word by word: every topic word must share a
    stem with the quote or the planner's reading, or belong to the quote
    niche's vocabulary. One word matching the quote is not enough: "heart
    surgery quotes" shares "heart" with a heartbreak quote and is unrelated.
    The grade is the weakest word's.
    """
    phrase = normalize_phrase(theme)
    if not phrase:
        return ""
    if phrase in set(reading.get("niche_themes") or []):
        return "language"
    words = _topic_words(phrase)
    if not words:
        return ""
    quote_stems = _stems(quote)
    reading_stems = _stems(f"{reading.get('meaning') or ''} {reading.get('emotion') or ''}")
    grounded = quote_stems | reading_stems
    phrase_niche = {
        word for niche in _NICHE_PHRASES if f" {niche} " in f" {phrase} "
        and _shares_stem({_stem(word) for word in _topic_words(niche)}, grounded)
        for word in _topic_words(niche)
    }
    levels: list[int] = []
    for word in words:
        stem = {_stem(word)}
        if _shares_stem(stem, quote_stems):
            levels.append(3)
        elif _shares_stem(stem, reading_stems):
            levels.append(2)
        elif word in _NICHE_WORDS or _stem(word) in _NICHE_WORDS or word in phrase_niche:
            levels.append(1)
        else:
            return ""
    return {3: "quote_words", 2: "planner_reading", 1: "quote_niche"}[min(levels)]


def _tag_row(phrase: str, *, validated: bool, rank: int | None, planner: bool, relation: str) -> dict[str, Any]:
    """A provenance row the final quality gate can read, its support graded by how the theme ties to the quote."""
    origin = "ai_shorts_planner_reading" if planner else "ai_shorts_quote_words"
    grade, support = _RELATIONS[relation]
    if validated:
        score = min(100, grade + max(2, 10 - int(rank or 0)))
        reason = f"{support}; typed by real viewers (YouTube search suggestion, rank {int(rank or 0) + 1}); not search volume."
    else:
        score = grade - 6
        reason = f"{support}; not checked against YouTube search suggestions."
    return {
        "keyword": phrase, "sources": [origin, *(["search_demand"] if validated else [])],
        "source": "+".join([origin, *(["search_demand"] if validated else [])]),
        "source_classification": "combined" if validated else "script_derived",
        "classification": "long_tail",
        "content_relevance_score": 42, "visual_relevance_score": 0,
        "relation_to_quote": relation,
        "source_support_score": grade, "source_support": support,
        "research_evidence_score": 0, "query_alignment_score": 0, "intent_score": 18, "specificity_score": 12,
        "diversity_score": None, "keyword_relevance_score": score, "evidence_count": 0,
        "demand_validated": validated, "demand_rank": rank if validated else None,
        **({"search_demand": "youtube_search_suggestion"} if validated else {}),
        "cluster": "ai_shorts_theme", "intent": "search_intent",
        "selection_reason": reason, "reason": reason,
    }


def _distinct(phrase: str, chosen: list[str]) -> bool:
    words = set(phrase.split())
    return all(words != set(other.split()) and phrase not in other and other not in phrase for other in chosen)


def suggest_client(language: str = "english") -> Any:
    """The configured, cached search-suggestion client (no YouTube Data API quota)."""
    from win_engine.core.config import get_settings
    from win_engine.ingestion.cache import shared_cache
    from win_engine.ingestion.search_suggest import SearchSuggestClient

    settings = get_settings()
    return SearchSuggestClient(
        enabled=settings.search_suggest_enabled,
        timeout_seconds=settings.search_suggest_timeout_seconds,
        # AI Shorts' own limit, used exactly as configured (0 turns the check
        # off); research's search_suggest_max_queries is never read or changed.
        max_queries=int(settings.ai_shorts_suggest_max_queries),
        cache=shared_cache(
            ttl_seconds=settings.cache_ttl_evergreen_seconds,
            redis_url=settings.redis_url,
            key_prefix=settings.redis_key_prefix,
        ),
    )


def verify_subject_tags(
    reading: dict[str, Any], *, quote: str, language: str = "english", region: str = "global", client: Any = None,
) -> dict[str, Any]:
    """Check the reading's search themes against YouTube search suggestions; keep the ones viewers type.

    Returns ``subject_tags`` (provenance rows, at most MAX_SUBJECT_TAGS),
    ``search_demand`` (what was asked and answered) and ``tag_note`` (one
    honest line for the package's warnings). Never raises: without
    suggestions only the reading's phrases are kept, unverified, and the note
    says so.
    """
    planner = set(reading.get("planner_themes") or [])
    # The planner's themes and the language niche's ("tamil sad quotes") lead.
    priority = set(reading.get("priority_themes") or planner)
    subject_only = set(reading.get("subject_themes") or []) - priority
    # Every theme must be tied to the quote before it is even asked about: the
    # planner's, the quote words', the subjects' and the tone's alike.
    relations: dict[str, str] = {}
    rejected: list[dict[str, str]] = []
    candidates: list[str] = []
    tone = str(reading.get("tone") or "")
    for theme in reading.get("search_themes") or []:
        if not theme or has_unsupported_instructional_framing(theme, quote):
            continue
        if contradicts_tone(theme, tone):
            rejected.append({"keyword": str(theme), "reason": CONTRADICTS_TONE, "source": "ai_shorts_theme"})
            continue
        relation = theme_relation(theme, reading, quote)
        if not relation:
            rejected.append({"keyword": str(theme), "reason": UNRELATED, "source": "ai_shorts_theme"})
            continue
        relations[theme] = relation
        candidates.append(theme)
    demand: dict[str, Any] = {"status": "no_seed_queries", "queries": [], "suggestions": {}, "failed_queries": []}
    try:
        if candidates:
            lookup = client if client is not None else suggest_client(language)
            demand = lookup.fetch(candidates, language=language, region=region)
    except Exception as exc:  # a lookup outage must never cost the package
        logger.warning("AI Shorts tag check against search suggestions failed: %s", type(exc).__name__)
        demand = {**demand, "status": "unavailable"}
    status = str(demand.get("status") or "unavailable")
    index = suggestion_index(demand)
    asked = {normalize_phrase(query) for query in demand.get("queries") or []}
    answered = demand.get("suggestions") or {}
    checked = status in {"ok", "partial"}

    validated: list[tuple[str, int]] = []
    unverified: list[str] = []
    for phrase in candidates:
        rank = demand_rank(phrase, index) if checked else None
        if rank is not None:
            validated.append((phrase, rank))
        elif phrase in subject_only:
            continue
        elif not checked or phrase not in asked or phrase not in answered:
            # Not asked (over the query cap) or its lookup failed: unknown, not refused.
            unverified.append(phrase)
    # Specific themes first; the broad ones every quote of a feeling shares after.
    # Three or more planner themes lead in the planner's order: the quote's own
    # words only top them up, never go ahead of them.
    strong_planner = len(planner) >= 3 or len(priority - planner) > 0
    # A search built from a single quote word ("love quotes") ranks after the
    # themes read from the quote's meaning, though it is asked early.
    validated.sort(key=lambda item: (
        item[0] not in priority if strong_planner else False, item[0] in subject_only, is_generic_tag(item[0]),
    ))
    chosen: list[dict[str, Any]] = []
    names: list[str] = []
    for phrase, rank in validated:
        if len(chosen) < MAX_SUBJECT_TAGS and _distinct(phrase, names):
            chosen.append(_tag_row(phrase, validated=True, rank=rank, planner=phrase in planner,
                                   relation=relations[phrase]))
            names.append(phrase)
    # Phrases nobody types are dropped; an unchecked one tops up a short list.
    floor = MAX_SUBJECT_TAGS if not checked else 3
    for phrase in sorted(unverified, key=lambda item: (item not in priority, is_generic_tag(item))):
        if len(chosen) < floor and _distinct(phrase, names):
            chosen.append(_tag_row(phrase, validated=False, rank=None, planner=phrase in planner,
                                   relation=relations[phrase]))
            names.append(phrase)
    typed = sum(1 for phrase, _ in validated if phrase in asked)
    if not candidates:
        note = "No search theme could be read from this quote, so no tag was checked against YouTube search suggestions."
    elif checked:
        note = (
            f"Tags come from the quote's meaning and were checked against YouTube search suggestions "
            f"(no API quota): {typed} of {len(asked)} phrases checked are typed by viewers; phrases nobody types "
            "were dropped. Suggestions show what people type, not search volume."
        )
    elif status == "disabled":
        note = ("YouTube search-suggestion checks are turned off, so the tags come from the quote's meaning alone "
                "and were not checked against what viewers type.")
    else:
        note = ("YouTube search suggestions could not be reached, so the tags come from the quote's meaning alone "
                "and were not checked against what viewers type.")
    return {
        "subject_tags": chosen,
        "rejected_themes": rejected,
        "search_demand": {
            "status": status, "scope": "youtube_search_suggestions_not_volume",
            "queries": sorted(asked), "suggestions": {key: list(value)[:10] for key, value in answered.items()},
            "validated_keywords": [row["keyword"] for row in chosen if row["demand_validated"]],
            "explanation": "Phrases marked as validated appear in YouTube's own search suggestions, so real viewers "
                           "type them. Suggestion rank reflects relative popularity for that prefix; it is not "
                           "search volume.",
        },
        "tag_note": note,
    }


def final_tags(
    brief: dict[str, Any] | None, selected_tags: Iterable[str], keyword_research: dict[str, Any], quote: str = "",
) -> tuple[list[str], dict[str, Any]]:
    """The AI Shorts tags: the verified theme phrases, topped up by the shared selector's, then yt and shorts.

    A single broad word the shared selector kept ("pretend") is only a last
    resort: it names no search a viewer of this quote makes. The evidence
    gains a provenance row for each theme phrase, so the final quality gate
    can explain every tag.
    """
    reading = understanding_of(brief, quote)
    rows = [row for row in reading.get("subject_tags") or [] if isinstance(row, dict) and row.get("keyword")]
    names = [str(row["keyword"]) for row in rows][:MAX_SUBJECT_TAGS]
    # A single word ("pretend", "heart", "useful") only repeats the quote; no
    # viewer of a quote Short searches it. The shared selector's multi-word
    # tags top up a list under three, and only when tied to the quote.
    refused = [dict(item) for item in reading.get("rejected_themes") or [] if isinstance(item, dict)]
    for tag in (str(tag) for tag in selected_tags if str(tag) not in _PLATFORM_TAGS):
        if len(names) >= MIN_GREEN_SUBJECT_TAGS or not meaningful_tag(tag) or not _distinct(tag, names):
            continue
        if contradicts_tone(tag, str(reading.get("tone") or "")):
            refused.append({"keyword": tag, "reason": CONTRADICTS_TONE, "source": "shared_selector"})
            continue
        if not theme_relation(tag, reading, quote):
            refused.append({"keyword": tag, "reason": UNRELATED, "source": "shared_selector"})
            continue
        names.append(tag)
    tags = [*names, *_PLATFORM_TAGS]
    evidence = dict(keyword_research or {})
    if refused:
        evidence["rejected_candidates"] = [*(evidence.get("rejected_candidates") or []), *refused]
    # Prepended so these rows, not an earlier row of the same phrase, explain the tag.
    mine = {str(row["keyword"]) for row in rows}
    evidence["candidates"] = [*rows, *(
        item for item in evidence.get("candidates") or []
        if not isinstance(item, dict) or str(item.get("keyword")) not in mine
    )]
    demand = reading.get("search_demand")
    if isinstance(demand, dict) and demand.get("status") not in (None, "not_checked"):
        evidence["search_demand"] = {**(evidence.get("search_demand") or {}), **demand}
        evidence["search_demand_available"] = bool(demand.get("suggestions"))
    return tags, synchronize_tag_evidence(evidence, tags)


def flag_sparse_subject_tags(gate: dict[str, Any], tags: Iterable[str]) -> dict[str, Any]:
    """Keep a package without three subject tags, two of them specific, from GREEN: weak tags are not hidden.

    The shared gate reports a Short's sparse tags as information only, which
    let a package whose only subject tag was one quote word show GREEN, and
    another whose tags were "emotional quotes", "life quotes", "deep quotes".
    """
    subject = [tag for tag in tags if meaningful_tag(tag)]
    specific = [tag for tag in subject if not is_generic_tag(tag)]
    if len(subject) >= MIN_GREEN_SUBJECT_TAGS and len(specific) >= MIN_GREEN_SPECIFIC_TAGS:
        return gate
    issue = {
        "code": "sparse_subject_tags", "field": "tags", "severity": "warning",
        "message": (f"{len(subject)} subject tag(s) viewers search came through for this quote, {len(specific)} of "
                    f"them specific to its theme (a GREEN AI Short needs {MIN_GREEN_SUBJECT_TAGS}, with "
                    f"{MIN_GREEN_SPECIFIC_TAGS} specific); add a phrase viewers search for this quote's own theme "
                    "before uploading. Broad searches such as \"deep quotes\", and yt and shorts, do not count."),
    }
    result = dict(gate)
    quality = dict(result.get("final_seo_quality") or {})
    result["warnings"] = [*(result.get("warnings") or []), issue]
    quality["warnings"] = [*(quality.get("warnings") or []), issue]
    if result.get("verdict") == "GREEN":
        result["verdict"] = "YELLOW"
        quality["verdict"] = "YELLOW"
    result["final_seo_quality"] = quality
    return result


# Notes the shared gate makes that mean nothing for an AI Short's title: the
# title is the quote, and "self respect quotes" never belongs in it.
_TITLE_NOISE = {"primary_keyword_missing_from_title"}
_LIMITING_GATE_WARNINGS = {"non_contextual_tags"}


def finalize_gate(gate: dict[str, Any], title: str, tags: Iterable[str], quote: str) -> dict[str, Any]:
    """The shared gate's verdict, as it applies to an AI Short.

    The exact quote may lead up to about 90 characters, so its length outside
    the 30-70 band no longer downgrades the package; the keyword-placement
    note is dropped; and a package without enough specific subject tags is
    not GREEN (flag_sparse_subject_tags). Every other warning stands.
    """
    removed = set(_TITLE_NOISE)
    if is_exact_quote(title, quote) and len(title_body(title)) <= WHOLE_QUOTE_TITLE_CHARS:
        removed.add("title_length_outside_band")
    result = dict(gate)
    quality = dict(result.get("final_seo_quality") or {})
    before = len(result.get("warnings") or []) + len(quality.get("warnings") or [])
    result["warnings"] = [item for item in result.get("warnings") or [] if item.get("code") not in removed]
    quality["warnings"] = [item for item in quality.get("warnings") or [] if item.get("code") not in removed]
    dropped = before != len(result["warnings"]) + len(quality["warnings"])
    still_limited = any(item.get("severity") == "warning" for item in quality["warnings"]) or any(
        item.get("code") in _LIMITING_GATE_WARNINGS and item.get("severity") == "warning" for item in result["warnings"]
    )
    if dropped and result.get("verdict") == "YELLOW" and not still_limited and result.get("passed", True):
        result["verdict"] = quality["verdict"] = "GREEN"
    result["final_seo_quality"] = quality
    return flag_sparse_subject_tags(result, tags)


def sync_trace(trace: dict[str, Any], tags: Iterable[str], keyword_research: dict[str, Any]) -> None:
    """Rewrite the trace's record of the final tags to the ones this package delivers.

    The writer stage records its own selection, which the AI Shorts tag step
    replaces afterwards: a live trace listed three tags beside five delivered.
    """
    provenance = [item for item in keyword_research.get("tag_provenance") or [] if isinstance(item, dict)]
    trace["final_tags"] = list(tags)
    trace["final_tag_provenance"] = provenance
    trace["final_tag_scores"] = [
        {"keyword": item.get("tag") or item.get("keyword"), "source_support_score": item.get("source_support_score"),
         "provenance": item.get("provenance")}
        for item in provenance
    ]
