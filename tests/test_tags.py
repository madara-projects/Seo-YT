"""Regression tests: tags are measured, and every script survives normalization.

Covers model tags recorded with a flat source support of 100, tag keys that
dropped accents and non-Tamil scripts, the junk-tag check that rejected every
non-ASCII tag and hashtag, and a sparse-tag warning read from a missing key.
"""

import unittest

from win_engine.analysis.generation_quality import evaluate_package_quality
from win_engine.analysis.keyword_research import _normalize, _tokens, select_final_tags
from win_engine.analysis.topic_lock import is_junk_tag, force_hashtags

STARTUP = "In this video we talk about startup hiring. Hiring your first engineers at a startup is hard."


def _row(tags, keyword):
    return next((row for row in tags if row.get("keyword") == keyword), None)


class ModelTagSupportTests(unittest.TestCase):
    def test_model_tag_support_is_measured_against_the_source(self):
        tags, evidence = select_final_tags(
            {}, generated_tags=["startup hiring mistakes"], title="Hiring at a startup", script=STARTUP,
        )
        row = _row(evidence["selected_keywords"], "startup hiring mistakes")
        self.assertIsNotNone(row)
        # Two of three words appear in the script; "mistakes" does not.
        self.assertEqual(row["source_support_score"], 67)
        self.assertNotEqual(row["source_support"], "generated suggestion has direct semantic support")
        provenance = next(item for item in evidence["tag_provenance"] if item["tag"] == "startup hiring mistakes")
        self.assertEqual(provenance["source_support_score"], 67)

    def test_weakly_supported_model_tag_meets_the_same_floor(self):
        tags, evidence = select_final_tags(
            {}, generated_tags=["startup equity vesting schedules"], title="Hiring at a startup", script=STARTUP,
        )
        self.assertNotIn("startup equity vesting schedules", tags)
        rejected = {item["keyword"]: item["reason"] for item in evidence["rejected_candidates"]}
        self.assertEqual(rejected.get("startup equity vesting schedules"), "weak_source_support")

    def test_fully_supported_model_tag_is_unaffected(self):
        tags, evidence = select_final_tags({}, generated_tags=["startup hiring"], title="Hiring", script=STARTUP)
        self.assertIn("startup hiring", tags)
        self.assertEqual(_row(evidence["selected_keywords"], "startup hiring")["source_support_score"], 100)


class UnicodeTagTests(unittest.TestCase):
    def test_normalization_keeps_every_script(self):
        self.assertEqual(_normalize("Pokémon cards"), "pokémon cards")
        self.assertEqual(_normalize("Beyoncé live!"), "beyoncé live")
        self.assertEqual(_normalize("हिन्दी गाने"), "हिन्दी गाने")
        self.assertEqual(_normalize("செட்டிநாடு பிரியாணி"), "செட்டிநாடு பிரியாணி")
        # ASCII behaviour is unchanged.
        self.assertEqual(_normalize("  Cold-Brew   Coffee!! #1 "), "cold-brew coffee 1")
        self.assertEqual(_tokens("Pokémon cards"), ["pokémon", "cards"])
        self.assertEqual(_tokens("हिन्दी गाने"), ["हिन्दी", "गाने"])

    def test_final_tags_keep_accents(self):
        script = "Opening a box of Pokémon cards to find the rarest pull."
        tags, _ = select_final_tags({}, generated_tags=["pokémon cards"], title="Rare pull", script=script)
        self.assertIn("pokémon cards", tags)
        self.assertNotIn("pok mon cards", tags)

    def test_non_ascii_tags_are_not_junk(self):
        for tag in ("பிரியாணி", "செட்டிநாடு சிக்கன் பிரியாணி", "pokémon cards", "हिन्दी गाने"):
            with self.subTest(tag=tag):
                self.assertFalse(is_junk_tag(tag))
        for tag in ("", "#bad|tag", "tips", "2024", "free", "didn least deserve"):
            with self.subTest(tag=tag):
                self.assertTrue(is_junk_tag(tag))

    def test_tamil_hashtags_survive(self):
        hashtags = force_hashtags(["#பிரியாணி", "#ChettinadBiryani"], "", "cooking")
        self.assertIn("#பிரியாணி", hashtags)


class SparseTagWarningTests(unittest.TestCase):
    def test_one_strong_tag_does_not_raise_the_sparse_warning(self):
        quote = "You deserve somebody who knows how hard it is to find somebody like you"
        gate = evaluate_package_quality(
            {"title": "Know Your Worth—You're Hard to Replace #shorts", "variants": [],
             "description": f"“{quote}”\n\nA reflection about recognizing your worth.",
             "tags": ["know your worth", "shorts"], "hashtags": ["#shorts"]},
            script=quote,
            creator_brief={"exact_quote": quote, "video_format": "youtube_shorts",
                           "visual_requirements": "Rain on a window", "creator_intent": "A reflection on worth"},
            tag_evidence={"selected_keywords": [
                {"keyword": "know your worth", "keyword_relevance_score": 96, "source_support_score": 100,
                 "source_classification": "combined", "source_support": "direct creator-source support"},
                {"keyword": "shorts", "classification": "platform_format", "source_classification": "creator_strategy",
                 "source_support_score": 100, "source_support": "creator-preferred Shorts discovery tag"},
            ]},
            enforce_final_tag_rules=False,
        )
        codes = [item["code"] for item in gate["final_seo_quality"]["warnings"]]
        self.assertNotIn("sparse_tag_set", codes)


if __name__ == "__main__":
    unittest.main()
