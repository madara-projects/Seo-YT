"""Regression tests: tags are measured, and every script survives normalization.

Covers model tags recorded with a flat source support of 100, tag keys that
dropped accents and non-Tamil scripts, the junk-tag check that rejected every
non-ASCII tag and hashtag, and a sparse-tag warning read from a missing key.
"""

import unittest

from win_engine.analysis.generation_quality import evaluate_package_quality
from win_engine.analysis.keyword_research import (
    _atomic_concepts,
    _is_generic,
    _normalize,
    _tokens,
    _typed_similarity,
    build_keyword_research,
    demand_seed_phrases,
    select_final_tags,
)
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


class TagVariantTests(unittest.TestCase):
    SCRIPT = "Self love is not selfish. Love yourself first, then love others."
    BRIEF = {"exact_quote": "Self love is not selfish. Love yourself first.", "video_format": "short"}

    def test_one_search_written_three_ways_takes_one_short_tag(self):
        # A Short's five slots went to "self-love quotes", "self love quotes" and "self love quote".
        demand = {"status": "ok", "queries": ["self love quotes"], "suggestions": {
            "self love quotes": ["self love quotes", "self love quotes for her", "self love quote"]}}
        research = build_keyword_research(
            script=self.SCRIPT, semantic={"primary_topic": "self love"}, youtube_results=[], research_queries=[],
            entity_signals=[], creator_brief=self.BRIEF, search_demand=demand,
        )
        tags, _ = select_final_tags(research, generated_tags=["self-love quotes"], title="Love yourself first",
                                    script=self.SCRIPT, creator_brief=self.BRIEF, is_short=True)
        variants = [tag for tag in tags if tag.replace("-", " ").rstrip("s") == "self love quote"]
        self.assertEqual(len(variants), 1, tags)

    def test_word_forms_and_spacing_are_the_same_search(self):
        for left, right in (("betrayal quote", "betrayal quotes"), ("break up quotes", "breakup quotes"),
                            ("motivation quotes", "motivational quotes"), ("self-love quotes", "self love quotes")):
            with self.subTest(left=left):
                self.assertEqual(_typed_similarity(left, right), 1.0)
        # Longer searches stay different searches.
        self.assertLess(_typed_similarity("sad betrayal quotes", "betrayal quotes"), 0.9)
        self.assertLess(_typed_similarity("cold brew coffee recipe", "cold brew coffee"), 0.9)

    def test_quotation_marks_are_not_part_of_a_tag(self):
        self.assertEqual(_normalize("‘Sad’ quotes"), "sad quotes")
        self.assertEqual(_normalize("'Sad' quotes"), "sad quotes")

    def test_brief_prose_is_not_cut_into_short_tags(self):
        # Split at its commas, the inferred brief's prose shipped as the tags
        # "deep emotional resonance" and "relatable truth"; whole, it is rejected.
        self.assertEqual(len(_atomic_concepts("deep emotional resonance, relatable truth and life")), 1)
        self.assertEqual(_atomic_concepts("manual and burr coffee grinders"), ["manual and burr coffee grinders"])
        self.assertEqual(len(_atomic_concepts("24/7 motivation")), 1)


class QuoteToneTests(unittest.TestCase):
    HOPEFUL = "Never give up on the people you love."
    PAINFUL = "You never loved me, and love was all I gave."
    DEMAND = {"status": "ok", "queries": ["love quotes"],
              "suggestions": {"love quotes": ["love quotes", "sad love quotes", "love quotes for her"]}}

    def seeds(self, quote):
        return demand_seed_phrases({"subject_terms": ["love"], "candidates": []}, {},
                                   {"exact_quote": quote, "video_format": "Short"})

    def research(self, quote):
        brief = {"exact_quote": quote, "video_format": "Short"}
        return brief, build_keyword_research(
            script=quote, semantic={"primary_topic": "love"}, youtube_results=[], research_queries=[],
            entity_signals=[], creator_brief=brief, search_demand=self.DEMAND,
        )

    def test_never_as_encouragement_is_not_pain(self):
        self.assertNotIn("sad love quotes", self.seeds(self.HOPEFUL))
        for quote in (self.PAINFUL, "I’ll never see you again, my love.", "Never again will I love like that.",
                      "You would have never left if my love was enough.", "Love ended in betrayal."):
            with self.subTest(quote=quote):
                self.assertIn("sad love quotes", self.seeds(quote))

    def test_a_sad_suggestion_needs_a_sad_quote(self):
        brief, research = self.research(self.HOPEFUL)
        self.assertNotIn("sad love quotes", research["search_demand"]["grounded_suggestions"])
        tags, evidence = select_final_tags(research, generated_tags=["sad love quotes"], title="Never give up",
                                           script=self.HOPEFUL, creator_brief=brief, is_short=True)
        self.assertNotIn("sad love quotes", tags)
        rejected = {row["keyword"]: row["reason"] for row in evidence["rejected_candidates"]}
        self.assertEqual(rejected.get("sad love quotes"), "mood_not_in_source")
        _, research = self.research(self.PAINFUL)
        self.assertIn("sad love quotes", research["search_demand"]["grounded_suggestions"])

    def test_uplifting_mood_words_alone_are_generic(self):
        for phrase in ("motivational quotes", "inspirational quotes", "motivational inspirational quotes"):
            with self.subTest(phrase=phrase):
                self.assertTrue(_is_generic(phrase))
        self.assertFalse(_is_generic("motivational speech"))


class BriefBoilerplateTests(unittest.TestCase):
    INTENT = "Preserve and package the exact emotional idea without inventing events."

    def test_app_written_brief_text_gives_no_source_support(self):
        from win_engine.analysis.keyword_research import _source_terms

        script = "I loved you more than words could hold."
        inferred = {"creator_intent": self.INTENT, "field_provenance": {"creator_intent": {"source": "inferred"}}}
        self.assertNotIn("preserve", _source_terms(script, inferred))
        typed = {"creator_intent": self.INTENT, "field_provenance": {"creator_intent": {"source": "creator_supplied"}}}
        self.assertIn("preserve", _source_terms(script, typed))
        self.assertIn("preserve", _source_terms(script, {"creator_intent": self.INTENT}))  # no provenance: as before

    def test_app_written_words_never_become_tags(self):
        quote = "It's about who makes you seen, felt, heard and loved."
        brief = {"exact_quote": quote, "creator_intent": self.INTENT, "video_format": "Short",
                 "field_provenance": {"creator_intent": {"source": "inferred"}}}
        research = build_keyword_research(
            script=quote, semantic={"primary_topic": "loved preserve", "secondary_topics": ["exact emotional idea"]},
            youtube_results=[], research_queries=[], entity_signals=[], creator_brief=brief,
        )
        self.assertFalse({"loved preserve", "exact emotional idea"} & {row["keyword"] for row in research["candidates"]})
        tags, evidence = select_final_tags(research, generated_tags=["loved preserve"], title="Seen and loved",
                                           script=quote, creator_brief=brief, is_short=True)
        self.assertNotIn("loved preserve", tags)
        rejected = {row["keyword"]: row["reason"] for row in evidence["rejected_candidates"]}
        self.assertEqual(rejected.get("loved preserve"), "app_brief_text")

    def test_footage_words_never_become_quote_short_tags(self):
        quote = "Some people stay in your heart forever."
        content = f"the quote is- {quote} and the video is of road, recorded from the car front window."
        brief = {"exact_quote": quote, "content": content, "video_format": "Short"}
        tags, evidence = select_final_tags({}, generated_tags=["car front window", "heart forever"], title="Stay",
                                           script=content, creator_brief=brief, is_short=True)
        self.assertNotIn("car front window", tags)
        rejected = {row["keyword"]: row["reason"] for row in evidence["rejected_candidates"]}
        self.assertEqual(rejected.get("car front window"), "footage_not_topic")
        self.assertNotEqual(rejected.get("heart forever"), "footage_not_topic")  # quote words still count


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
