"""Regression tests from the analysis audit: Indic scripts, negation scope and odd input."""

import unittest
from datetime import datetime, timedelta, timezone

from win_engine.analysis.audit_experiment import _hashtags, build_published_audit
from win_engine.analysis.creator_brief import _extract_duration, build_creator_brief, creator_topic
from win_engine.analysis.generation_quality import feeling_hashtag
from win_engine.analysis.idea_workspace import build_idea_evidence
from win_engine.analysis.intent_classifier import classify_intent
from win_engine.analysis.language_engine import build_language_strategy
from win_engine.analysis.pacing_engine import analyze_script_pacing
from win_engine.analysis.retention_assistant import analyze_retention_assistant
from win_engine.analysis.source_cues import affirmed_feeling_words, is_negator, is_short_video, quote_title
from win_engine.analysis.strategy_layer import build_upload_timing
from win_engine.analysis.topic_lock import extract_main_topic, force_hashtags, normalize_hashtag, source_lead_phrase
from win_engine.generation import ai_shorts_seo as seo
from win_engine.generation.strategy_engine import _feeling_emoji
from win_engine.scoring.outlier_engine import score_outliers

HINDI = "कभी कभी खामोशी सब कुछ कह देती है। दिल टूट जाता है।"
TAMIL = "சில நேரங்களில் மௌனம் எல்லாவற்றையும் சொல்லிவிடும்"


class NegationScopeTests(unittest.TestCase):
    def test_a_negation_does_not_reach_into_the_next_sentence(self):
        self.assertIn("love", affirmed_feeling_words("It's not over. Love always finds a way"))

    def test_no_one_is_a_subject_like_nobody(self):
        self.assertIn("hurts", affirmed_feeling_words("No one hurts you like the people you trust"))

    def test_real_denials_still_count(self):
        self.assertEqual(affirmed_feeling_words("Don't cry because it's over"), [])
        self.assertEqual(affirmed_feeling_words("Not one tear fell"), [])

    def test_a_pause_does_not_end_a_negation(self):
        for quote in ("I don't... love you anymore.", "I don't… love you anymore.", "Don't... cry for me.",
                      "I don't...\nlove you anymore."):
            with self.subTest(quote=quote):
                self.assertEqual(affirmed_feeling_words(quote), [])

    def test_a_line_break_ends_a_negation_only_after_a_sentence_end(self):
        self.assertEqual(affirmed_feeling_words("No more\ntears for people\nwho never cared."), [])
        self.assertEqual(affirmed_feeling_words("I'm not\nlonely anymore"), [])
        self.assertIn("love", affirmed_feeling_words("It's not over.\nLove always finds a way"))
        self.assertIn("love", affirmed_feeling_words("It's not over... It never was. Love stays"))

    def test_shorts_keep_a_negation_across_a_pause_or_a_line_break(self):
        love, cry = "I don't... love you anymore.", "Don't... cry for me."
        for quote in (love, cry):
            with self.subTest(quote=quote):
                self.assertEqual((feeling_hashtag(quote), _feeling_emoji(quote)), ("", ""))
        self.assertNotEqual(seo.local_tone(cry), "sad")
        self.assertNotIn("😢", seo.emoji_candidates(seo.quote_understanding(cry, {}), cry))
        self.assertNotIn("#sadquotes", seo.ai_short_hashtags(None, "No more\ntears for people\nwho never cared."))
        self.assertNotIn("#loneliness", seo.ai_short_hashtags(None, "I'm not\nlonely anymore"))
        self.assertFalse(seo._affirmed(r"\blove\b", "i don't... love you anymore"))
        self.assertTrue(seo._affirmed(r"\blove\b", "it's not over.\nlove will find you again"))


class OddInputTests(unittest.TestCase):
    def test_a_title_from_punctuation_words_does_not_crash(self):
        self.assertIsInstance(quote_title("- - - - - " + "the " * 30), str)


class IndicPacingTests(unittest.TestCase):
    def test_a_tamil_quote_is_counted_in_whole_words(self):
        pacing = analyze_script_pacing(TAMIL, video_format="youtube_shorts", exact_quote=TAMIL)
        self.assertEqual(pacing["recommended_read_time_seconds"], 3)

    def test_the_danda_ends_a_hindi_sentence(self):
        script = "मैं आज आपको बताऊंगा। यह बहुत आसान है। चलिए शुरू करते हैं। पहला कदम यह है।"
        pacing = analyze_script_pacing(script, video_format="tutorial")
        self.assertEqual(pacing["avg_sentence_length"], 4.0)
        self.assertEqual(pacing["pace_label"], "fast")

    def test_cue_words_count_only_as_whole_words(self):
        pacing = analyze_script_pacing("I know you know the snow. Knowledge is power. Butter is tasty.", video_format="tutorial")
        self.assertEqual(pacing["hook_density"], "low")
        self.assertEqual(pacing["pattern_interrupts"], 0)

    def test_cue_words_count_with_their_endings(self):
        script = "Two mistakes I made. Three secrets I kept. More mistakes, more secrets. Keep watching, I know."
        pacing = analyze_script_pacing(script, video_format="tutorial")
        self.assertEqual(pacing["hook_density"], "medium")
        self.assertEqual(pacing["pattern_interrupts"], 1)  # "watching"; "know" is not "now"
        for word in ("watches", "watched", "buts"):
            with self.subTest(word=word):
                self.assertEqual(analyze_script_pacing(f"No {word} here.", video_format="tutorial")["pattern_interrupts"], 1)
        for word in ("nowhere", "button", "watchtower", "thence"):
            with self.subTest(word=word):
                self.assertEqual(analyze_script_pacing(f"No {word} here.", video_format="tutorial")["pattern_interrupts"], 0)


class PublishedHashtagTests(unittest.TestCase):
    def test_tamil_and_hindi_hashtags_are_read_whole(self):
        self.assertEqual(
            _hashtags("Watch #காதல் #प्यार #love_life, #fyp."), ["#காதல்", "#प्यार", "#love_life", "#fyp"],
        )

    def test_an_unchanged_tamil_hashtag_is_an_exact_match(self):
        audit = build_published_audit({
            "run": {"package": {"title": "t", "hashtags": ["#காதல்"]}},
            "link": {"youtube_metadata": {"title": "t", "description": "மௌனம் #காதல்"}, "metadata_synced_at": "2026-01-01"},
        })
        hashtags = next(item for item in audit["comparisons"] if item["field"] == "hashtags")
        self.assertEqual(hashtags["generated_to_published"], "exact_match")


class SelectedLanguageTests(unittest.TestCase):
    def test_a_selected_hindi_or_tanglish_is_kept(self):
        self.assertEqual(build_language_strategy("Tum yaad aate ho har pal", {"language": "hindi"})["primary_language"], "hinglish_or_hindi")
        self.assertEqual(build_language_strategy("Nee illama naan illa", {"language": "tanglish"})["primary_language"], "tanglish")


class IndicTopicTests(unittest.TestCase):
    def test_a_hindi_source_has_a_topic(self):
        self.assertEqual(source_lead_phrase(HINDI), "कभी कभी खामोशी सब कुछ कह देती है")
        self.assertIn("खामोशी", extract_main_topic(HINDI))
        brief = build_creator_brief(script=HINDI, video_format="youtube_shorts", language="hindi")
        self.assertIn("खामोशी", creator_topic(brief))

    def test_a_labelled_tamil_quote_names_the_topic_without_its_label(self):
        brief = build_creator_brief(script=f"the quote is- {TAMIL}")
        self.assertEqual(brief["exact_quote"], TAMIL)
        self.assertEqual(creator_topic(brief), TAMIL)


class InferredDurationTests(unittest.TestCase):
    def test_a_number_in_a_recipe_is_not_the_videos_length(self):
        script = " ".join(f"step{index}" for index in range(300)) + ". Then microwave it for 90 seconds."
        brief = build_creator_brief(script=script, video_format="tutorial")
        self.assertEqual(brief["field_provenance"]["duration_seconds"]["source"], "inferred")
        result = analyze_retention_assistant(script, creator_brief=brief)
        codes = [item["risk_code"] for stage in result["risk_map"] for item in stage["risks"]]
        self.assertNotIn("spoken_content_overload", codes)
        self.assertEqual(result["trace"]["timing_basis"], "relative_stage_only")

    def test_a_supplied_length_still_counts(self):
        script = " ".join(f"step{index}" for index in range(300))
        brief = build_creator_brief(script=script, video_format="tutorial", duration_seconds=90, voice_over="present")
        result = analyze_retention_assistant(script, creator_brief=brief)
        codes = [item["risk_code"] for stage in result["risk_map"] for item in stage["risks"]]
        self.assertIn("spoken_content_overload", codes)


class CapturedVelocityTests(unittest.TestCase):
    def test_velocity_is_measured_up_to_when_the_counts_were_captured(self):
        now = datetime.now(timezone.utc)
        row = {"view_count": "10000", "like_count": "500", "comment_count": "20", "subscriber_count": "5000",
               "published_at": (now - timedelta(days=10)).isoformat(), "duration": "PT45S"}
        cached = score_outliers([{**row, "captured_at": (now - timedelta(days=8)).isoformat()}])[0]
        live = score_outliers([row])[0]
        self.assertAlmostEqual(cached["views_per_day"], 5000, delta=1)
        self.assertAlmostEqual(live["views_per_day"], 1000, delta=1)


class CasualContractionTests(unittest.TestCase):
    def test_apostrophe_less_contractions_deny(self):
        for word in ("dont", "cant", "didnt", "wont", "isnt", "doesnt", "wasnt", "arent", "couldnt",
                     "wouldnt", "shouldnt", "aint", "don't", "can’t"):
            with self.subTest(word=word):
                self.assertTrue(is_negator(word))
        self.assertEqual(affirmed_feeling_words("Dont cry because its over"), [])
        self.assertEqual(affirmed_feeling_words("Love hurts"), ["love", "hurts"])


class ReelCueTests(unittest.TestCase):
    def test_a_fishing_or_highlight_reel_is_not_a_short(self):
        for script in ("My new fishing reel review: drag, gear ratio and line capacity",
                       "Season highlight reel from our football club", "Restoring an old film reel from 1962",
                       "Best fishing reels under 100 dollars", "Our season highlights reel",
                       "A highlight-reel save from our keeper"):
            with self.subTest(script=script):
                self.assertFalse(is_short_video(script, {}))

    def test_a_reel_as_the_format_is_a_short(self):
        for script in ("Instagram reel about letting go", "Posting this as a reel tonight",
                       "reel video: rain on a window", "quote reels for sad nights", "#reels"):
            with self.subTest(script=script):
                self.assertTrue(is_short_video(script, {}))

    def test_a_single_reel_as_the_format_is_a_short(self):
        for script in ("Make a reel on this quote", "reel: The quietest people usually have the loudest minds.",
                       "Soft piano for this reel", "My next reel is about city lights at night"):
            with self.subTest(script=script):
                self.assertTrue(is_short_video(script, {}))
        for video_format in ("quote_reel", "ig_reel", "reel_video"):
            with self.subTest(video_format=video_format):
                self.assertTrue(is_short_video("", {"video_format": video_format}))


class OddNumberTests(unittest.TestCase):
    def test_infinite_or_nan_counts_are_unknown(self):
        (row,) = score_outliers([{"view_count": float("inf"), "like_count": float("nan"), "comment_count": "5",
                                  "subscriber_count": "100", "published_at": "2026-01-01T00:00:00Z"}])
        self.assertIsNone(row["outlier_score"])

    def test_unreadable_analytics_do_not_crash_upload_timing(self):
        now = datetime(2026, 10, 14, 12, tzinfo=timezone.utc)
        bad_window = {"reliable": True, "sample_size": 30,
                      "windows": [{"day": "monday", "activity": "high", "start_hour": float("inf")}]}
        timing = build_upload_timing([], channel_analytics={"audience_activity": bad_window}, timezone_name="UTC", now=now)
        self.assertEqual(timing["basis"], "general_recommendation")
        videos = [{"published_at": f"2026-10-0{day}T10:00:00Z", "views": "many", "average_view_percentage": "n/a"}
                  for day in range(1, 6)]
        timing = build_upload_timing([], channel_analytics={"audience_activity": {**bad_window, "sample_size": "lots"}},
                                     historical_videos=videos, timezone_name="UTC", now=now)
        self.assertEqual(timing["basis"], "historical_channel_data")

    def test_non_text_keys_in_unserialisable_research_do_not_crash(self):
        evidence = build_idea_evidence({"youtube_results": [{1: object(), "title": "x"}]})
        self.assertEqual(evidence["youtube_results"], [{"1": None, "title": "x"}])


class StatedLengthTests(unittest.TestCase):
    def test_minutes_and_seconds_together(self):
        self.assertEqual(_extract_duration("A 1 min 30 sec quote short"), 90.0)
        self.assertEqual(_extract_duration("2 minutes and 15 seconds of rain"), 135.0)
        self.assertEqual(_extract_duration("a 30-second reel"), 30.0)


class IndicHashtagTests(unittest.TestCase):
    def test_indic_hashtags_stay_whole_and_english_is_unchanged(self):
        self.assertEqual(normalize_hashtag("#சிக்கன் பிரியாணி"), "#சிக்கன்பிரியாணி")
        self.assertEqual(normalize_hashtag("#प्यार।"), "#प्यार")
        self.assertEqual(normalize_hashtag("cold brew"), "#ColdBrew")
        self.assertEqual(normalize_hashtag("#iPhone15"), "#iPhone15")

    def test_filler_hashtags_are_dropped(self):
        hashtags = force_hashtags(["#இந்த", "#வீடியோவில்", "#वीडियो", "#சிக்கன்பிரியாணி", "#ColdBrew"], "", "cooking")
        self.assertEqual(hashtags, ["#சிக்கன்பிரியாணி", "#ColdBrew"])
        self.assertEqual(force_hashtags(["#Latte", "#ColdBrew", "#Coffee"], "", "cooking"), ["#Latte", "#ColdBrew", "#Coffee"])


class IntentMarkerTests(unittest.TestCase):
    def test_a_marker_must_open_a_word(self):
        self.assertEqual(classify_intent("History repeats when the heart forgets"), "SUGGESTED")
        self.assertEqual(classify_intent("A sneak preview of the new song"), "SUGGESTED")
        self.assertEqual(classify_intent("My honest reviews of budget phones"), "BROWSE")


if __name__ == "__main__":
    unittest.main()
