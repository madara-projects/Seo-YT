"""Script bridging for grounding Latin search phrases in Tamil sources.

Tamil creators write scripts in Tamil script, but their audience searches in
English, Tanglish, and Tamil ("chettinad chicken biryani in tamil"). Every
source-grounding check in the pipeline compared words literally, so an English
tag could never be grounded in a Tamil script and Tamil videos ended up with no
tags at all.

This module provides a *matching* bridge, not a translation:

* ``tamil_to_latin`` renders Tamil script phonetically in Latin letters.
* ``phonetic_key`` reduces any word, in either script, to a consonant skeleton
  so spelling variants collapse together::

      chettinad  -> stnt      செட்டிநாடு -> settinaatu -> stnt
      biryani    -> prn       பிரியாணி   -> piriyaani  -> prn
      chicken    -> skn       சிக்கன்    -> sikkan     -> skn

It deliberately matches only what sounds the same, which covers the words that
matter most for search: dish and place names, brands, and English loanwords.
Native Tamil words that merely *mean* the same thing (வெங்காயம் / onion) do not
match, and that is intentional; meaning-level equivalence belongs to the
semantic layer, not to a phonetic key.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Iterable

TAMIL_RE = re.compile(r"[஀-௿]")

_PULLI = "்"

_INDEPENDENT_VOWELS = {
    "அ": "a", "ஆ": "aa", "இ": "i", "ஈ": "ii", "உ": "u", "ஊ": "uu",
    "எ": "e", "ஏ": "ee", "ஐ": "ai", "ஒ": "o", "ஓ": "oo", "ஔ": "au",
}

# ச is rendered as "s": it is pronounced s/ch depending on the word, and the
# phonetic key merges both into one class anyway.
_CONSONANTS = {
    "க": "k", "ங": "ng", "ச": "s", "ஞ": "nj", "ட": "t", "ண": "n",
    "த": "t", "ந": "n", "ப": "p", "ம": "m", "ய": "y", "ர": "r",
    "ல": "l", "வ": "v", "ழ": "zh", "ள": "l", "ற": "r", "ன": "n",
    "ஜ": "j", "ஷ": "sh", "ஸ": "s", "ஹ": "h", "ஶ": "sh",
}

_VOWEL_SIGNS = {
    "ா": "aa", "ி": "i", "ீ": "ii", "ு": "u", "ூ": "uu",
    "ெ": "e", "ே": "ee", "ை": "ai", "ொ": "o", "ோ": "oo",
    "ௌ": "au", "ௗ": "",
}

_DIGRAPHS = (
    ("sch", "s"), ("ch", "s"), ("sh", "s"), ("zh", "l"), ("th", "t"), ("dh", "t"),
    ("ph", "p"), ("bh", "p"), ("kh", "k"), ("gh", "k"), ("ck", "k"), ("qu", "kv"),
    ("wh", "v"), ("ng", "n"), ("nj", "n"),
)
_LETTER_CLASSES = str.maketrans({
    "b": "p", "d": "t", "g": "k", "j": "s", "z": "s", "f": "p", "q": "k", "w": "v",
})

MIN_KEY_LENGTH = 3


def has_tamil(text: object) -> bool:
    return bool(TAMIL_RE.search(str(text or "")))


def tamil_to_latin(text: object) -> str:
    """Render Tamil script phonetically; non-Tamil characters pass through."""

    source = str(text or "")
    out: list[str] = []
    index = 0
    while index < len(source):
        char = source[index]
        if char in _CONSONANTS:
            out.append(_CONSONANTS[char])
            following = source[index + 1] if index + 1 < len(source) else ""
            if following == _PULLI:
                index += 1
            elif following in _VOWEL_SIGNS:
                out.append(_VOWEL_SIGNS[following])
                index += 1
            else:
                out.append("a")
        elif char in _INDEPENDENT_VOWELS:
            out.append(_INDEPENDENT_VOWELS[char])
        elif char == "ஃ":  # aytham: marks f/z in loanwords; the key merges it away
            pass
        elif char == _PULLI or char in _VOWEL_SIGNS:
            pass  # orphaned mark
        else:
            out.append(char)
        index += 1
    return "".join(out)


@lru_cache(maxsize=4096)
def phonetic_key(word: str) -> str:
    """Consonant skeleton of one word, comparable across Tamil and Latin script."""

    value = tamil_to_latin(word) if has_tamil(word) else str(word or "")
    value = re.sub(r"[^a-z]", "", value.casefold())
    for digraph, replacement in _DIGRAPHS:
        value = value.replace(digraph, replacement)
    # English "c" is soft before e/i/y ("rice") and hard elsewhere ("coffee").
    value = re.sub(r"c(?=[eiy])", "s", value).replace("c", "k")
    value = value.translate(_LETTER_CLASSES).replace("x", "ks")
    value = re.sub(r"[aeiouyh]", "", value)
    return re.sub(r"(.)\1+", r"\1", value)


def script_words(text: object) -> list[str]:
    """Latin and Tamil words of a text, lower-cased, in order."""

    folded = str(text or "").casefold()
    return re.findall(r"[a-z0-9]+|[஀-௿]+", folded)


def phonetic_keys(texts: Iterable[object] | object) -> set[str]:
    """Phonetic keys of every sufficiently distinctive word in the given text(s)."""

    values = [texts] if isinstance(texts, (str, bytes)) or not isinstance(texts, Iterable) else texts
    keys: set[str] = set()
    for value in values:
        for word in script_words(value):
            key = phonetic_key(word)
            if len(key) >= MIN_KEY_LENGTH:
                keys.add(key)
    return keys


def phonetic_match(word: str, source_keys: set[str]) -> bool:
    """Whether ``word`` sounds like a word in the source.

    Tamil is agglutinative ("குக்கரில்" is "in the cooker"), so a longer source
    key may carry a suffix. A prefix match is accepted only for keys of four or
    more consonants, where a coincidental collision is unlikely.
    """

    key = phonetic_key(word)
    if len(key) < MIN_KEY_LENGTH:
        return False
    if key in source_keys:
        return True
    return len(key) >= 4 and any(candidate.startswith(key) for candidate in source_keys)
