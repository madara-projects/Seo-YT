"""Regression tests: the creator's source is used as written, and copy describes the video.

Covers the risk filter that rewrote the creator's script ("never install a mod
apk" became "never install a official method"), fallback descriptions that told
viewers how they were assembled, thumbnail text lifted from the creator's
direction for the image, and a title score that credited context words
against the topic's size.
"""

import unittest
from unittest.mock import patch

from win_engine.analysis.creator_brief import build_creator_brief, creator_topic
from win_engine.analysis.package_builder import build_title_thumbnail_packages
from win_engine.analysis.topic_lock import normalize_risk_terms, unsupported_risk_terms
from win_engine.feedback.history_store import HistoryStore
from win_engine.generation.seo_generator import generate_seo_suggestions
from win_engine.generation.strategy_engine import (
    _content_specific_fallback,
    _deterministic_score,
    _safe_minimal_package,
)
from win_engine.llm import gemini_client

MOD_APK = (
    "Why you should never install a mod apk: malware explained. I walk through how a modded game file "
    "steals your login, what the permissions screen hides, and how to check an app before you install it."
)


def _run(script, generated):
    store = HistoryStore(":memory:")
    brief = build_creator_brief(script=script, video_format="explainer")
    research = {"history_store": store, "youtube_results": [], "keyword_signals": [{"keyword": "mod apk malware"}],
                "entity_signals": [], "top_opportunities": [], "upload_timing": {}, "thumbnail_intelligence": {}}
    with patch("win_engine.generation.strategy_engine.write_multilang_packages_with_source",
               return_value=({"english": generated}, "gemini")) as writer, \
         patch.object(gemini_client, "is_available", return_value=False):
        response = generate_seo_suggestions(script, research, context={
            "language": "english", "region": "global", "creator_brief": brief,
        })
    return response, store, writer


class RiskWordingTests(unittest.TestCase):
    def test_the_creators_script_is_not_rewritten(self):
        generated = {
            "title": "Never Install a Mod APK: How Modded Games Steal Your Login",
            "variants": ["Never Install a Mod APK: How Modded Games Steal Your Login"],
            "description": "A mod apk can steal your login. Check the permissions screen before you install an app.",
            "tags": ["mod apk malware"], "hashtags": ["#ModApk"],
        }
        response, store, writer = _run(MOD_APK, generated)
        self.assertEqual(writer.call_args.args[0], MOD_APK)
        self.assertEqual(store.history_run(response["history_run_id"])["query"], MOD_APK)
        # The creator's own subject stays in the copy.
        self.assertIn("mod apk", response["title"].casefold())
        self.assertIn("mod apk", response["description"])
        self.assertNotIn("official method", (response["title"] + response["description"]).casefold())

    def test_generated_copy_cannot_add_an_exploit_promise(self):
        generated = {
            "title": "Get Unlimited Diamonds Safely? The Mod APK Malware Trap",
            "variants": ["Get Unlimited Diamonds Safely? The Mod APK Malware Trap",
                         "Never Install a Mod APK: How Modded Games Steal Your Login"],
            "description": "Mod apk files promise unlimited diamonds but steal your login.",
            "tags": ["mod apk malware", "unlimited diamonds"], "hashtags": ["#ModApk", "#UnlimitedDiamonds"],
        }
        response, _, _ = _run(MOD_APK, generated)
        titles = [response["title"], *response["title_variants"]]
        self.assertFalse([title for title in titles if "unlimited diamonds" in title.casefold()])
        self.assertEqual(response["title"], "Never Install a Mod APK: How Modded Games Steal Your Login")
        self.assertNotIn("unlimited diamonds", response["tags"])
        self.assertNotIn("#UnlimitedDiamonds", response["hashtags"])
        self.assertNotIn("unlimited diamonds", response["description"].casefold())

    def test_only_phrases_missing_from_the_source_are_replaced(self):
        source = "GTA 5 unlimited money glitch patched"
        self.assertEqual(normalize_risk_terms("The GTA 5 unlimited money glitch is gone", source=source),
                         "The GTA 5 unlimited money glitch is gone")
        self.assertEqual(normalize_risk_terms("Free diamonds for everyone", source=source), "earn diamonds for everyone")
        self.assertEqual(unsupported_risk_terms("#FreeFireHack tips", source=source), ["free fire hack"])
        self.assertEqual(unsupported_risk_terms("unlimited money glitch", source=source), [])


class FallbackCopyTests(unittest.TestCase):
    QUOTE = "In the end, I wasn't abandoned. I was erased."

    def test_fallback_descriptions_describe_the_video_not_their_assembly(self):
        brief = build_creator_brief(script="Quote Short over evening road traffic.", exact_quote=self.QUOTE,
                                    on_screen_text=self.QUOTE, video_format="youtube_shorts")
        for description in (
            _content_specific_fallback(creator_topic(brief), [], brief)["description"],
            _safe_minimal_package(creator_topic(brief), brief)["description"],
        ):
            with self.subTest(description=description):
                self.assertIn(f"“{self.QUOTE}”", description)
                for narration in ("exact words shown on screen", "built only from the words", "supplied by the creator"):
                    self.assertNotIn(narration, description)

    def test_minimal_package_keeps_the_scene(self):
        brief = build_creator_brief(script=self.QUOTE, exact_quote=self.QUOTE, video_format="youtube_shorts",
                                    visual_requirements="One person walking alone in quiet streets.")
        description = _safe_minimal_package(creator_topic(brief), brief)["description"]
        self.assertEqual(description, f"“{self.QUOTE}”\n\nA lone person walks through quiet streets.")


class ThumbnailTextTests(unittest.TestCase):
    def test_the_image_direction_is_the_visual_not_the_text(self):
        brief = {"thumbnail_idea": "Show me holding the phone with the battery graph behind me"}
        package = build_title_thumbnail_packages(
            [{"title": "Samsung Galaxy S25 Ultra battery test after a week"}], brief, validated=True,
            focus_phrases=["galaxy s25 ultra battery"],
        )[0]
        self.assertEqual(package["thumbnail_visual"], brief["thumbnail_idea"])
        self.assertNotIn("SHOW ME", package["thumbnail_text"].upper())
        self.assertTrue(package["thumbnail_text"].isupper())


class TitleScoreTests(unittest.TestCase):
    def test_context_words_do_not_stand_in_for_the_topic(self):
        context = "why mornings with a notebook feel calmer and quieter"
        off_topic = _deterministic_score("Why mornings with a notebook feel calmer", "cold brew coffee",
                                         context_text=context)
        on_topic = _deterministic_score("Why cold brew coffee tastes calmer", "cold brew coffee",
                                        context_text=context)
        self.assertLessEqual(off_topic, 7.0)
        self.assertGreater(on_topic, off_topic)


if __name__ == "__main__":
    unittest.main()
