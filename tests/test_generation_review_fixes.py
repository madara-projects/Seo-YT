"""Regression tests for the generation and analysis review findings.

Each test pins a defect reproduced offline: an "auto" language package the UI
showed without refinement, the risk filter or the final gate; emoji variation
selectors and Indic joiners mishandled as word characters; a re-run of one
script judged as repeating its own title; Tamil title scores and quote word
counts computed on letter fragments; risk hashtags missed in other casings;
decomposed Tamil openings; fallback titles that claimed things no creator
said; and helpers duplicated or left unused.
"""

import os
import tempfile
import unicodedata
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from win_engine.analysis.content_auditor import audit_content_package
from win_engine.analysis.creator_brief import build_creator_brief
from win_engine.analysis.generation_quality import title_similarity
from win_engine.analysis.keyword_research import select_final_tags
from win_engine.analysis.numbers import optional_number
from win_engine.analysis.research_planner import brief_research_text
from win_engine.analysis.search_opportunities import UNSUPPORTED_ADJACENT_CONTEXT
from win_engine.analysis.strategy_layer import build_channel_intelligence
from win_engine.analysis.text_tokens import normalize_unicode, unicode_words
from win_engine.analysis.topic_lock import (
    is_junk_tag,
    force_topic_in_title,
    normalize_risk_terms,
    unsupported_risk_terms,
)
from win_engine.feedback.history_store import HistoryStore
from win_engine.generation.quality_refinement import title_demand_words
from win_engine.generation.seo_generator import generate_seo_suggestions
from win_engine.generation.strategy_engine import (
    _deterministic_score,
    _score_tokens,
    _titles_of_other_videos,
    resolve_output_language,
)
from win_engine.llm import gemini_client

# Written as code points: these characters are invisible in source.
VS16 = chr(0xFE0F)
ZWNJ = chr(0x200C)
ZWJ = chr(0x200D)
HEART = chr(0x2764)
COFFEE = chr(0x2615)

MOD_APK = (
    "Why you should never install a mod apk: malware explained. I walk through how a modded game file "
    "steals your login, what the permissions screen hides, and how to check an app before you install it."
)
COLD_BREW = (
    "How to make cold brew coffee at home without any special equipment. First, grind the beans coarse. "
    "Then mix one part coffee with four parts water in a jar and steep it in the fridge for 18 hours. "
    "Finally strain it through a paper filter and dilute it with milk or water."
)
TAMIL_TOPIC = "செட்டிநாடு சிக்கன் பிரியாணி"


def _generate(script, store, *, language="english", video_language="english", generated=None, brief=None):
    brief = brief or build_creator_brief(script=script, video_format="tutorial")
    research = {"history_store": store, "youtube_results": [], "keyword_signals": [], "entity_signals": [],
                "top_opportunities": [], "upload_timing": {}, "thumbnail_intelligence": {}}
    with ExitStack() as stack:
        stack.enter_context(patch.object(gemini_client, "is_available", return_value=False))
        if generated is not None:
            stack.enter_context(patch(
                "win_engine.generation.strategy_engine.write_multilang_packages_with_source",
                return_value=({resolve_output_language({"language": language, "video_language": video_language}):
                               dict(generated)}, "gemini"),
            ))
        return generate_seo_suggestions(script, research, context={
            "language": language, "video_language": video_language, "region": "global", "creator_brief": brief,
        })


class AutoLanguageTests(unittest.TestCase):
    GENERATED = {
        "title": "Get Unlimited Diamonds Safely? The Mod APK Malware Trap",
        "variants": ["Get Unlimited Diamonds Safely? The Mod APK Malware Trap",
                     "Never Install a Mod APK: How Modded Games Steal Your Login"],
        "description": "Unlimited diamonds sound great, but a mod apk can steal your login. Check the permissions screen.",
        "tags": ["mod apk malware", "unlimited diamonds"], "hashtags": ["#ModApk", "#UnlimitedDiamonds"],
    }

    def test_auto_resolves_like_the_writer_stage(self):
        self.assertEqual(resolve_output_language({"language": "auto", "video_language": "Tamil"}), "tamil")
        self.assertEqual(resolve_output_language({"language": "auto"}), "english")
        self.assertEqual(resolve_output_language({"language": " Hindi "}), "hindi")
        self.assertEqual(resolve_output_language({"language": "klingon"}), "english")
        self.assertEqual(resolve_output_language(None), "english")

    def test_the_package_the_ui_shows_for_auto_is_the_final_one(self):
        store = HistoryStore(":memory:")
        brief = build_creator_brief(script=MOD_APK, video_format="explainer")
        with patch.object(store, "retention_learning_summary", wraps=store.retention_learning_summary) as learning:
            response = _generate(MOD_APK, store, language="auto", generated=self.GENERATED, brief=brief)
        package = response["multilang"]["english"]
        for field in ("title", "variants", "description", "tags", "hashtags"):
            self.assertEqual(package[field], response[field if field != "variants" else "title_variants"], field)
        self.assertNotIn("unlimited diamonds", package["title"].casefold())
        self.assertNotIn("unlimited diamonds", package["description"].casefold())
        self.assertNotIn("#UnlimitedDiamonds", package["hashtags"])
        self.assertEqual(response["generation_quality"]["requested_language"], "english")
        self.assertEqual(learning.call_args.kwargs["language_filter"], "english")


class EmojiSelectorTests(unittest.TestCase):
    def test_variation_selectors_are_not_word_characters(self):
        self.assertEqual(unicode_words(f"{HEART}{VS16}Love hurts"), ["love", "hurts"])
        self.assertEqual(title_similarity(f"{HEART}{VS16}Love hurts", "Love hurts"), 1.0)
        keycap = f"1{VS16}{chr(0x20E3)} step one"
        self.assertEqual(unicode_words(keycap, min_length=1), ["1", "step", "one"])

    def test_a_tag_never_carries_an_invisible_selector(self):
        self.assertTrue(is_junk_tag(f"{VS16}love quotes"))
        script = ("Cold brew coffee at home: how to make cold brew coffee without special equipment. Grind the "
                  "coffee coarse, steep the cold brew coffee in the fridge for 18 hours, then strain the cold brew.")
        brief = build_creator_brief(script=script, video_format="tutorial")
        tags, _ = select_final_tags({}, generated_tags=[f"{COFFEE}{VS16}cold brew coffee"],
                                    title="Cold brew coffee at home", script=script, creator_brief=brief)
        self.assertIn("cold brew coffee", tags)
        self.assertFalse([tag for tag in tags if VS16 in tag])


class JoinerTests(unittest.TestCase):
    def test_joiners_stay_inside_indic_words(self):
        for joiner in (ZWJ, ZWNJ):
            word = f"क्{joiner}ष"
            with self.subTest(joiner=hex(ord(joiner))):
                self.assertEqual(unicode_words(word), [word])
                self.assertEqual(normalize_unicode(word), word)
                self.assertFalse(is_junk_tag(f"{word}त्रिय"))
        self.assertFalse(is_junk_tag(f"क{ZWNJ}{ZWJ}ष"))

    def test_joiners_outside_words_are_not_words(self):
        family = f"{chr(0x1F468)}{ZWJ}{chr(0x1F469)}{ZWJ}{chr(0x1F467)} family vlog"
        self.assertEqual(unicode_words(family), ["family", "vlog"])
        self.assertTrue(is_junk_tag(f"{ZWJ}love quotes"))


class SameScriptRerunTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = HistoryStore(os.path.join(self.directory.name, "history.sqlite3"))

    def test_rerunning_a_script_is_not_a_title_repetition(self):
        results = [_generate(COLD_BREW, self.store) for _ in range(4)]
        self.assertEqual([item["generation_quality"]["verdict"] for item in results].count("RED"), 0)
        self.assertEqual(len({item["title"] for item in results}), 1)

    def test_another_videos_title_is_still_a_repetition(self):
        first = _generate(COLD_BREW, HistoryStore(os.path.join(self.directory.name, "other.sqlite3")))
        self.store.record_analysis_run("A different video about coffee", "SEARCH", "Story", first["title"],
                                       7.0, "LOW", "WORKABLE", 50.0)
        response = _generate(COLD_BREW, self.store)
        # Refinement moves to an alternative rather than repeat another video's title.
        self.assertNotEqual(response["title"], first["title"])
        self.assertNotIn(first["title"], response["title_variants"])

    def test_titles_of_other_videos_leave_out_this_script(self):
        same = self.store.record_analysis_run(COLD_BREW, "SEARCH", "Story", "Cold brew at home", 7.0, "LOW", "OK", 1.0)
        self.store.record_analysis_run(f"  {COLD_BREW.upper()}  ", "SEARCH", "Story", "Cold brew draft", 7.0,
                                       "LOW", "OK", 1.0)
        other = self.store.record_analysis_run("Masala tea at home", "SEARCH", "Story", "Masala tea", 7.0,
                                               "LOW", "OK", 1.0)
        self.store.link_published_video(same, "coldbrew001", "2026-08-01T10:00:00+00:00",
                                        selected_title="Cold Brew Coffee at Home")
        self.store.link_published_video(other, "masalatea01", "2026-08-02T10:00:00+00:00",
                                        selected_title="Masala Tea Recipe")
        recent, published = _titles_of_other_videos(self.store, COLD_BREW)
        self.assertEqual(recent, ["Masala tea"])
        self.assertEqual(published, ["Masala Tea Recipe"])


class TamilScoringTests(unittest.TestCase):
    def test_tamil_words_are_scored_whole(self):
        self.assertEqual(_score_tokens(TAMIL_TOPIC), TAMIL_TOPIC.split())

    def test_an_on_topic_tamil_title_outscores_an_unrelated_one(self):
        on_topic = _deterministic_score(f"{TAMIL_TOPIC} செய்முறை", TAMIL_TOPIC)
        unrelated = _deterministic_score("காதல் கவிதை தனிமை இரவு", TAMIL_TOPIC)
        self.assertGreater(on_topic, unrelated)


class TamilAuditTests(unittest.TestCase):
    def test_a_tamil_quote_is_counted_in_whole_words(self):
        quote = "நீ இல்லாத இந்த இரவு மிகவும் நீளமாக இருக்கிறது இன்று"
        self.assertEqual(len(quote.split()), 8)
        audit = audit_content_package(f'"{quote}"', "நீ இல்லாத இரவு #shorts", "இரவு", "",
                                      video_format="youtube_shorts", exact_quote=quote)
        self.assertIn("8 words", audit["hook_audit"]["basis"])
        self.assertEqual(audit["hook_audit"]["hook_strength"], "HIGH")
        self.assertEqual(audit["first_30_second_simulator"]["predicted_dropoff_risk"], "LOW")
        self.assertGreater(audit["alignment"]["title_script_alignment"], 0)

    def test_a_decomposed_tamil_opening_names_the_topic(self):
        # கொழுக்கட்டை typed with the two-part vowel sign as separate code points.
        decomposed = "".join(chr(code) for code in (
            0x0B95, 0x0BC6, 0x0BBE, 0x0BB4, 0x0BC1, 0x0B95, 0x0BCD, 0x0B95, 0x0B9F, 0x0BCD, 0x0B9F, 0x0BC8,
        ))
        script = decomposed + " செய்வது எப்படி. இன்று முழு செய்முறை 5 படிகளில்."
        for topic in (decomposed, unicodedata.normalize("NFC", decomposed)):
            with self.subTest(composed=topic != decomposed):
                audit = audit_content_package(script, "t", topic, "", video_format="tutorial")
                self.assertTrue(audit["hook_audit"]["keyword_in_opening"])


class RiskHashtagTests(unittest.TestCase):
    def test_the_creators_own_hashtag_subject_is_supported(self):
        source = "My #FreeFireHack test: why these hacks get accounts banned"
        self.assertEqual(unsupported_risk_terms("#FreeFireHack", source=source), [])
        self.assertEqual(normalize_risk_terms("Free fire hack bans explained", source=source),
                         "Free fire hack bans explained")

    def test_hashtags_in_any_casing_are_caught(self):
        for hashtag in ("#UNLIMITEDDIAMONDS", "#unlimiteddiamonds", "#UnlimitedDiamonds"):
            with self.subTest(hashtag=hashtag):
                self.assertEqual(unsupported_risk_terms(hashtag, source="free fire tips"), ["unlimited diamonds"])

    def test_prose_is_not_run_together(self):
        self.assertEqual(unsupported_risk_terms("It's free. Diamonds are forever", source=""), [])

    def test_the_rewrite_drops_a_risk_hashtag(self):
        self.assertEqual(normalize_risk_terms("Free fire tricks #FreeFireHack", source="free fire tips"),
                         "Free fire tricks")
        self.assertEqual(normalize_risk_terms("Get #UNLIMITEDDIAMONDS today\nNext line", source=""),
                         "Get today\nNext line")
        self.assertEqual(normalize_risk_terms("#ModApk dangers", source="never install a mod apk"),
                         "#ModApk dangers")


class ContentFreeInputTests(unittest.TestCase):
    def test_an_inferred_format_is_not_research_text(self):
        brief = build_creator_brief(script="\U0001F525\U0001F525 \U0001F4AF")
        self.assertEqual(brief["video_format"], "talking_head")
        self.assertNotIn("talking", brief_research_text(brief["content"], brief))
        supplied = build_creator_brief(script="Cold brew at home", video_format="tutorial")
        self.assertTrue(brief_research_text("Cold brew at home", supplied).endswith("tutorial"))
        self.assertTrue(brief_research_text("Cold brew at home", {"video_format": "review"}).endswith("review"))

    def test_an_emoji_only_script_is_not_titled_by_its_guessed_format(self):
        script = "\U0001F525\U0001F525\U0001F525 \U0001F4AF"
        response = _generate(script, HistoryStore(":memory:"), brief=build_creator_brief(script=script))
        self.assertNotIn("talking", response["title"].casefold())

    def test_fallback_titles_claim_nothing(self):
        for index in range(5):
            with self.subTest(index=index):
                title = force_topic_in_title("", "cold brew coffee", "cooking", variant_index=index)
                self.assertEqual(title, "Cold Brew Coffee")
                short = force_topic_in_title("", "love quotes", "shorts", variant_index=index, short_form=True)
                self.assertEqual(short.casefold().count("#shorts"), 1)
                self.assertFalse(any(char.isdigit() for char in title + short))
        # With nothing to name, no placeholder ("General Guide") is invented.
        self.assertEqual(force_topic_in_title("", "", "general"), "")


class SharedHelperTests(unittest.TestCase):
    def test_optional_number(self):
        for value in (None, "", "  ", "n/a", [3]):
            self.assertIsNone(optional_number(value), value)
        self.assertEqual(optional_number("12"), 12.0)
        self.assertEqual(optional_number(7), 7.0)

    def test_hidden_subscriber_counts_stay_unknown(self):
        self.assertEqual(build_channel_intelligence([{"title": "t", "subscriber_count": ""}])["dominant_channel_size"],
                         "unknown")
        self.assertEqual(build_channel_intelligence([{"title": "t", "subscriber_count": "5000"}])["dominant_channel_size"],
                         "small")

    def test_adjacent_context_terms_are_public(self):
        self.assertIn("gaming", UNSUPPORTED_ADJACENT_CONTEXT)

    def test_demand_phrases_are_counted_in_whole_hindi_words(self):
        evidence = {"search_demand": {"validated_keywords": ["चाय बनाने का तरीका"]}}
        self.assertEqual(title_demand_words("आसान चाय बनाने का तरीका घर पर", evidence), 4)


if __name__ == "__main__":
    unittest.main()
