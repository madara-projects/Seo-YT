"""Conservative source anchors for quote research, not semantic certainty."""
from __future__ import annotations

import re

from win_engine.analysis.text_tokens import unicode_words
from win_engine.analysis.transliteration import has_tamil, phonetic_keys, phonetic_match

_FUNCTION_WORDS = set("a an and are as at be been but by can could day do for from going had has have how i if in is it its just me more much my of on one or our out own re so some someone than that the their them then there these they this time to too us was we were what when where which who why will with would you your yourself quote quotes short shorts video videos emotional emotion feel feeling feelings".split())
_CONTEXTS = (
    {"parent", "parents", "mother", "father", "mom", "dad", "bereavement", "death", "died", "rip"},
    {"anime", "naruto", "manga", "venom", "movie", "film"},
    {"neet", "neetaspirents", "aiims", "exam", "exams", "student", "education"},
    {"ptsd", "anxiety", "depression", "therapy", "trauma", "diagnosis"},
    {"football", "soccer", "cricket", "nba", "nfl", "utd", "player", "players", "transfer", "transfers"},
)
_BROAD_MOODS = {"guilt", "heartbreak", "pain", "loss", "sad", "sadness", "emotion", "emotional", "feeling", "feelings", "regret", "deep"}


def broad_mood_only(text: str) -> bool:
    words = set(unicode_words(text)) - {"quote", "quotes"}
    return bool(words) and words <= _BROAD_MOODS


def semantic_subject(semantic: dict) -> str:
    """A validated primary interpretation may bridge a real paraphrase.

    A mood alone cannot replace the specific situation in a longer quote.
    It may still be used when directly named by the creator.
    """
    topic = str(semantic.get("primary_topic") or "")
    terms = set(unicode_words(topic)) - _FUNCTION_WORDS
    if semantic.get("concept_evidence_validated") is not True or not terms or terms <= _BROAD_MOODS:
        return ""
    return topic


def _root(word: str) -> str:
    irregular = {"understood": "understand", "misunderstood": "misunderstand", "forgotten": "forget", "forgot": "forget", "memories": "memory"}
    if word in irregular:
        return irregular[word]
    if word in {"love", "loved", "loving", "loves"}:
        return "love"
    if word in {"let", "letting", "lets"}:
        return "let"
    if len(word) > 5 and word.endswith("ing"):
        stem = word[:-3]
        return stem[:-1] if len(stem) > 2 and stem[-1] == stem[-2] else stem
    if len(word) > 4 and word.endswith("ed"):
        return word[:-2]
    if len(word) > 4 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def subject_terms(text: str) -> set[str]:
    return {_root(word) for word in unicode_words(text) if word not in _FUNCTION_WORDS and not re.fullmatch(r"(?:you|they|we|i|he|she|it)[’'](?:re|ll|ve|d|s|m)", word)}


def source_matches(text: str, source: str) -> set[str]:
    terms, source_terms = subject_terms(text), subject_terms(source)
    latin = phonetic_keys([word for word in source_terms if not has_tamil(word)])
    tamil = phonetic_keys([word for word in source_terms if has_tamil(word)])
    return {word for word in terms if word in source_terms
            or phonetic_match(word, latin if has_tamil(word) else tamil)}


def quote_result_support(title: str, quote: str, primary_subject: str = "") -> tuple[bool, set[str]]:
    """Reject foreign contexts and require a source anchor in the visible title.

    Description/channel keyword stuffing cannot supply the anchor. This is a
    lexical screen and is labelled as such; absence of proof means no evidence.
    """
    title_words, source_words = set(unicode_words(title)), set(unicode_words(quote))
    if any(title_words & context and not source_words & context for context in _CONTEXTS):
        return False, set()
    # Negated acceptance is a different intent from anticipated regret.
    if re.search(r"\b(?:without|no|never)\s+regret", title, re.I) and not re.search(
        r"\b(?:without|no|never)\s+regret", quote, re.I
    ):
        return False, set()
    if re.search(r"\b(?:letting|let) go of (?:your |the )?regret|forgive yourself", title, re.I) and not re.search(
        r"\b(?:letting|let) go of (?:your |the )?regret|forgive yourself", quote, re.I
    ):
        return False, set()
    matches = source_matches(title, quote)
    if not matches and primary_subject:
        primary_terms = subject_terms(primary_subject)
        primary_matches = source_matches(title, primary_subject)
        if primary_terms and len(primary_matches) >= min(2, len(primary_terms)):
            return True, primary_matches
    minimum = min(2, len(subject_terms(quote)))
    return bool(matches) and len(matches) >= minimum, matches
