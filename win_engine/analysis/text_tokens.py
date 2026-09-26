"""Unicode-aware text helpers shared by every analysis step.

Tamil, Devanagari and most Indic scripts write vowels as combining marks,
which Python's ``\\w`` does not match. Splitting on them tears words apart,
so the word pattern here adds every combining mark to ``\\w``.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

# Zero-width non-joiner and joiner (U+200C, U+200D) select conjunct forms
# inside Indic words, such as a half form of "क्ष"; they belong to the word.
JOINERS = chr(0x200C) + chr(0x200D)


def _is_symbol_mark(code: int) -> bool:
    # Emoji variation selectors and the marks that decorate symbols (keycaps)
    # are category M but never part of a word: U+FE0F after a heart emoji
    # turned "Love" into a different word.
    return 0x20D0 <= code <= 0x20FF or 0xFE00 <= code <= 0xFE0F or 0xE0100 <= code <= 0xE01EF


def is_word_character(char: str) -> bool:
    """A letter, digit, vowel sign or joiner of any script."""

    return char in JOINERS or (
        unicodedata.category(char)[0] in "LMN" and not _is_symbol_mark(ord(char))
    )


def _combining_mark_class() -> str:
    ranges: list[tuple[int, int]] = []
    for code in range(0x10000):
        if unicodedata.category(chr(code))[0] == "M" and not _is_symbol_mark(code):
            if ranges and ranges[-1][1] == code - 1:
                ranges[-1] = (ranges[-1][0], code)
            else:
                ranges.append((code, code))
    return "".join(
        f"\\u{start:04x}" if start == end else f"\\u{start:04x}-\\u{end:04x}" for start, end in ranges
    )


_MARKS = _combining_mark_class()
_LETTER = rf"[\w{_MARKS}]"
# A joiner counts only between letters, so emoji ZWJ sequences stay non-words.
_WORD = rf"{_LETTER}+(?:[{JOINERS}]+{_LETTER}+)*"
_WORD_RE = re.compile(rf"{_WORD}(?:['’]{_WORD})?")
# A run of joiners without a letter on one side; a run is judged whole.
_STRAY_JOINERS_RE = re.compile(
    rf"(?<![\w{_MARKS}{JOINERS}])[{JOINERS}]+|[{JOINERS}]+(?![\w{_MARKS}{JOINERS}])"
)


def strip_stray_joiners(text: str) -> str:
    """Drop joiners that do not sit between two letters."""

    return _STRAY_JOINERS_RE.sub("", text)


def normalize_unicode(value: Any) -> str:
    """Return stable printable Unicode without invisible control characters."""

    text = unicodedata.normalize("NFKC", str(value or ""))
    return "".join(
        char for char in text
        if char in "\n\t" or char in JOINERS or not unicodedata.category(char).startswith("C")
    ).strip()


def unicode_words(value: Any, *, min_length: int = 2) -> list[str]:
    """Casefolded words of at least `min_length` characters, from every script."""

    return [
        token.casefold()
        for token in _WORD_RE.findall(normalize_unicode(value))
        if len(token.replace("_", "")) >= min_length
    ]
