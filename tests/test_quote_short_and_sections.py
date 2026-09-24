"""Regression tests for the defects found by testing a real quote Short.

Input: "There is nothing more painful in this world than to be in love with
something that never can be." over "Rainy road with vehicles". The package
leaked the writer's rules into the description, the quote was missed without
quotation marks, and several strategy sections printed templates or claims
made from no data.
"""

import unittest
from unittest.mock import MagicMock, patch

from win_engine.analysis.content_auditor import audit_content_package
from win_engine.analysis.creator_brief import build_creator_brief, creator_topic
from win_engine.analysis.gap_engine import analyze_opportunity_gaps
from win_engine.analysis.generation_quality import evaluate_package_quality, narrates_process, strip_process_narration
from win_engine.analysis.keyword_research import (
    _reject_reason,
    _source_terms,
    build_keyword_research,
    demand_seed_phrases,
    quote_themes,
    subject_terms,
)
from win_engine.analysis.package_builder import build_title_thumbnail_packages
from win_engine.analysis.strategy_layer import build_content_graph_strategy
from win_engine.analysis.thumbnail_classifier import build_thumbnail_strategy
from win_engine.analysis.thumbnail_intelligence import analyze_thumbnails
from win_engine.feedback.learning_engine import build_feedback_package
from win_engine.generation.automation_engine import build_automation_workflow
from win_engine.generation.expansion_engine import build_binge_bridge, build_session_expansion
from win_engine.llm import gemini_client
from win_engine.llm.seo_writer import _sanitize_generated_package

QUOTE = "There is nothing more painful in this world than to be in love with something that never can be."
VISUAL = "Rainy road with vehicles"


class ProcessNarrationTests(unittest.TestCase):
    LEAKED = (
        "Impossible love is often the most painful experience in this world. This short features a poignant "
        "reflection set against a rainy road, honoring the exact emotional weight of unfulfilled longing without "
        "adding external stories or invented outcomes. 🌧️"
    )

    def test_leaked_clause_is_cut_and_the_rest_kept(self):
        cleaned = strip_process_narration(self.LEAKED)
        self.assertNotIn("invented outcomes", cleaned)
        self.assertNotIn("exact emotional weight", cleaned)
        self.assertIn("set against a rainy road.", cleaned)
        self.assertIn("Impossible love is often the most painful experience in this world.", cleaned)
        cleaned = strip_process_narration(
            "This quiet reflection captures that exact realization of hidden secrets and broken trust "
            "without adding outside assumptions."
        )
        self.assertEqual(cleaned, "This quiet reflection captures that exact realization of hidden secrets and broken trust.")

    def test_ordinary_copy_is_untouched(self):
        for text in (
            "Make cold brew without any special equipment.",
            "How the show differs from the source material.",
            "This remix stays true to the original.",
            "Learn it without adding sugar.",
            "The funniest clips without any context.",
        ):
            self.assertFalse(narrates_process(text), text)
            self.assertEqual(strip_process_narration(text), text)

    def test_gate_flags_a_leak_that_reaches_it(self):
        brief = build_creator_brief(script=QUOTE, visual_requirements=VISUAL)
        gate = evaluate_package_quality(
            {"title": "When you love something that can never be #shorts", "variants": [], "tags": [], "hashtags": [],
             "description": f"“{QUOTE}”\n\nA reflection on impossible love, without adding external stories."},
            script=QUOTE, creator_brief=brief, require_shorts_tags=False, enforce_final_tag_rules=False,
        )
        self.assertIn("creator_instruction_leakage", {item["code"] for item in gate["issues"]})

    def test_writer_strips_the_leak_before_the_gate_sees_it(self):
        brief = build_creator_brief(script=QUOTE, visual_requirements=VISUAL)
        package = _sanitize_generated_package(
            {"title": "When you love something that can never be #shorts", "variants": [],
             "description": f"“{QUOTE}”\n\n{self.LEAKED}", "tags": [], "hashtags": []},
            QUOTE, brief,
        )
        self.assertFalse(narrates_process(package["description"]))
        self.assertIn("rainy road", package["description"])


class QuoteDetectionTests(unittest.TestCase):
    def test_quote_without_quotation_marks_is_a_quote_short(self):
        for visual in (VISUAL, ""):
            brief = build_creator_brief(script=QUOTE, visual_requirements=visual)
            self.assertEqual(brief["video_format"], "youtube_shorts")
            self.assertTrue(brief["exact_quote"].startswith("There is nothing more painful"))

    def test_similar_short_lines_that_are_not_quotes(self):
        for script in ("Why people never save money", "My 20 minute home workout for beginners",
                       "We hiked to Top Station and fell in love with the view"):
            self.assertEqual(build_creator_brief(script=script)["exact_quote"], "", script)
        self.assertEqual(build_creator_brief(script="We accept the love we think we deserve")["video_format"],
                         "youtube_shorts")

    def test_topic_does_not_end_mid_phrase(self):
        brief = build_creator_brief(script=QUOTE, visual_requirements=VISUAL)
        self.assertEqual(brief["topic"], "there is nothing more painful in this world")
        self.assertEqual(creator_topic(brief), "there is nothing more painful in this world")


class QuoteTagTests(unittest.TestCase):
    def test_real_search_reusing_quote_words_is_not_a_copy(self):
        entry = {"keyword": "painful love", "classification": "long_tail", "demand_validated": True,
                 "source_support_score": 100, "keyword_relevance_score": 90}
        self.assertIsNone(_reject_reason(entry, "x", QUOTE, {"painful", "love"}))
        chopped = {**entry, "keyword": "something that never can be"}
        self.assertEqual(_reject_reason(chopped, "x", QUOTE, {"something", "never"}), "quote_copy")

    def test_painful_quote_is_also_searched_as_sad_quotes(self):
        terms = subject_terms({}, [], _source_terms(QUOTE, {}), themes=quote_themes(QUOTE))
        seeds = demand_seed_phrases({"subject_terms": sorted(terms), "candidates": []}, {},
                                    {"exact_quote": QUOTE, "video_format": "Short"})
        self.assertEqual(seeds[:2], ["love quotes", "sad love quotes"])
        happy = "Love is the best thing that ever happened to me."
        seeds = demand_seed_phrases({"subject_terms": ["love"], "candidates": []}, {},
                                    {"exact_quote": happy, "video_format": "Short"})
        self.assertNotIn("sad love quotes", seeds)

    def test_background_words_are_not_subjects(self):
        brief = {"exact_quote": QUOTE, "visual_requirements": VISUAL, "video_format": "Short"}
        research = build_keyword_research(
            script=QUOTE, semantic={"primary_topic": "impossible love", "entities": ["vehicles"]},
            youtube_results=[], research_queries=[], entity_signals=[], creator_brief=brief,
        )
        self.assertIn("love", research["subject_terms"])
        self.assertNotIn("vehicles", research["subject_terms"])


class NoDataHonestyTests(unittest.TestCase):
    def test_no_competitors_means_no_thumbnail_claim(self):
        result = analyze_thumbnails([])
        self.assertNotIn("skew low-resolution", result["recommendation"])
        self.assertEqual(result["sample_size"], 0)

    def test_no_competitors_means_opportunity_is_unmeasured(self):
        result = analyze_opportunity_gaps([], [], [], [], {}, target_title="x")
        self.assertIsNone(result["opportunity_score"]["score"])
        self.assertEqual(result["opportunity_score"]["label"], "UNMEASURED")
        self.assertEqual(result["idea_kill_switch"]["status"], "insufficient_evidence")
        self.assertNotIn("strong enough", result["idea_kill_switch"]["reason"])
        self.assertEqual(result["viability_verdict"]["status"], "unknown")

    def test_one_earlier_run_is_not_a_winning_pattern(self):
        feedback = build_feedback_package(
            {"title": "t", "content_angle": "Story", "title_optimization": {"scored_variants": []},
             "opportunity_gap_analysis": {"opportunity_score": {"score": None}}},
            {"youtube_results": []},
            {"angle_effectiveness": [{"content_angle": "Story", "run_count": 1, "avg_title_score": 7.5}],
             "winning_titles": [{"title": "3 Morning Habits to Sharpen Focus"}]},
            {"total_runs": 5, "avg_title_score": 7.0, "avg_opportunity_score": 40.0},
        )
        self.assertEqual(feedback["winning_patterns"]["best_angle_so_far"], "UNKNOWN")
        self.assertEqual(feedback["winning_patterns"]["best_title_so_far"], "")
        self.assertIsNone(feedback["historical_comparison"]["opportunity_score_vs_average"])


class PackagingSectionTests(unittest.TestCase):
    def test_thumbnail_text_keeps_the_subject(self):
        tags = ["painful love", "impossible love", "love quotes", "sad love quotes"]
        texts = {
            item["title"]: item["thumbnail_text"]
            for item in build_title_thumbnail_packages(
                [{"title": "The heavy weight of impossible love 🌧️ #shorts"},
                 {"title": "Sad love quotes about an impossible connection 💔 #shorts"},
                 {"title": "Love quotes for when it can never be 🌧️ #shorts"},
                 {"title": "The pain of being in love with what cannot be 🥀 #shorts"}],
                {"exact_quote": QUOTE, "visual_requirements": VISUAL}, validated=True, focus_phrases=tags,
            )
        }
        self.assertEqual(texts["The heavy weight of impossible love 🌧️ #shorts"], "IMPOSSIBLE LOVE")
        self.assertEqual(texts["Sad love quotes about an impossible connection 💔 #shorts"], "SAD LOVE QUOTES")
        self.assertEqual(texts["Love quotes for when it can never be 🌧️ #shorts"], "LOVE QUOTES")
        fallback = texts["The pain of being in love with what cannot be 🥀 #shorts"]
        self.assertFalse(fallback.split()[-1].lower() in {"cannot", "it", "when", "being", "in"}, fallback)
        packages = build_title_thumbnail_packages(
            [{"title": "Cold brew coffee recipe at home without special equipment"}], {}, validated=True,
            focus_phrases=["cold brew coffee recipe", "cold brew at home"],
        )
        self.assertEqual(packages[0]["thumbnail_text"], "COLD BREW COFFEE RECIPE")

    def test_word_forms_match_the_search_phrase(self):
        from win_engine.analysis.generation_quality import keyword_placement

        self.assertEqual(keyword_placement("Loving something that never can be 🌧️ #shorts", "love quotes"), "front")
        texts = [item["thumbnail_text"] for item in build_title_thumbnail_packages(
            [{"title": "When loving what can never be hurts the most 💔 #shorts"}],
            {"exact_quote": QUOTE}, validated=True, focus_phrases=["impossible love", "love quotes"],
        )]
        self.assertEqual(texts, ["IMPOSSIBLE LOVE"])

    def test_validated_search_tags_are_not_pruned_for_the_score(self):
        from win_engine.generation.quality_refinement import refine_package

        evidence = {"subject_terms": ["love"], "selected_keywords": [
            {"keyword": "painful love", "keyword_relevance_score": 90, "demand_validated": True, "source_support_score": 100},
            {"keyword": "impossible love", "keyword_relevance_score": 100, "source_support_score": 100},
            {"keyword": "love quotes", "keyword_relevance_score": 77, "demand_validated": True, "source_support_score": 100},
            {"keyword": "sad love quotes", "keyword_relevance_score": 75, "demand_validated": True, "source_support_score": 100},
        ]}
        package = {"title": "Painful love and the ache of things that never can be #shorts", "variants": [],
                   "description": f"“{QUOTE}”\n\nLove quotes about the ache of an impossible love.",
                   "tags": ["painful love", "impossible love", "love quotes", "sad love quotes", "yt", "shorts"],
                   "hashtags": ["#shorts"]}
        with patch.object(gemini_client, "is_available", return_value=False):
            refined, _ = refine_package(package, script=QUOTE, brief=build_creator_brief(script=QUOTE),
                                        language="english", region="global", evidence=evidence, competitors=[])
        self.assertIn("love quotes", refined["tags"])
        self.assertIn("sad love quotes", refined["tags"])

    def test_short_tag_slots_go_to_real_searches_first(self):
        from win_engine.analysis.keyword_research import select_final_tags

        betrayal = "The biggest betrayal is knowing that if you didn't find out, they would have never told you."

        def row(keyword, score, validated):
            return {"keyword": keyword, "classification": "long_tail", "keyword_relevance_score": score,
                    "source_support_score": 100, "content_relevance_score": 60, "demand_validated": validated,
                    "semantic_evidence": not validated, "evidence_count": 1, "sources": ["semantic"]}

        research = {"subject_terms": ["betrayal"], "content_terms": ["betrayal", "secret", "trust", "deception"],
                    "candidates": [row("deception discovery", 100, False), row("trust violation", 99, False),
                                   row("emotional betrayal", 85, True), row("secret betrayal", 76, True),
                                   row("betrayal quotes", 74, True), row("sad betrayal quotes", 72, True)]}
        tags, _ = select_final_tags(research, generated_tags=[], title="When you find out #shorts", script=betrayal,
                                    creator_brief={"exact_quote": betrayal, "video_format": "Short"}, is_short=True)
        self.assertIn("betrayal quotes", tags)
        self.assertIn("sad betrayal quotes", tags)

    def test_weak_interpretation_is_pruned_when_searches_cover_the_package(self):
        from win_engine.generation.quality_refinement import refine_package

        evidence = {"subject_terms": ["love"], "selected_keywords": [
            {"keyword": "impossible love", "keyword_relevance_score": 100, "source_support_score": 100},
            {"keyword": "love quotes", "keyword_relevance_score": 77, "demand_validated": True, "source_support_score": 100},
            {"keyword": "sad love quotes", "keyword_relevance_score": 75, "demand_validated": True, "source_support_score": 100},
            {"keyword": "forbidden love", "keyword_relevance_score": 51, "source_support_score": 60},
        ]}
        package = {"title": "The heavy weight of loving what cannot be #shorts", "variants": [],
                   "description": f"“{QUOTE}”\n\nSad love quotes about an impossible love.",
                   "tags": ["impossible love", "love quotes", "sad love quotes", "forbidden love", "yt", "shorts"],
                   "hashtags": ["#shorts"]}
        with patch.object(gemini_client, "is_available", return_value=False):
            refined, _ = refine_package(package, script=QUOTE, brief=build_creator_brief(script=QUOTE),
                                        language="english", region="global", evidence=evidence, competitors=[])
        self.assertNotIn("forbidden love", refined["tags"])
        self.assertIn("love quotes", refined["tags"])

    def test_grounded_long_tail_tags_are_not_pruned_to_three(self):
        from win_engine.generation.quality_refinement import refine_package

        script = ("A day in Munnar: we hiked to Top Station at sunrise, visited a tea factory, and ended with a boat "
                  "ride on Mattupetty Dam. At the end I share the full budget for two people.")
        rows = [("munnar trip", 95, True), ("munnar travel guide", 92, True), ("munnar trip budget", 90, True),
                ("top station sunrise hike", 84, False), ("mattupetty dam boat ride", 80, False),
                ("munnar tea factory", 72, False)]
        evidence = {"subject_terms": ["munnar"], "selected_keywords": [
            {"keyword": k, "keyword_relevance_score": s, "demand_validated": v, "source_support_score": 100}
            for k, s, v in rows]}
        package = {"title": "Munnar trip budget for two: Top Station and a tea factory", "variants": [],
                   "description": "Munnar trip budget for two, with a sunrise hike to Top Station and a tea factory visit.",
                   "tags": [k for k, _, _ in rows], "hashtags": ["#Munnar"]}
        with patch.object(gemini_client, "is_available", return_value=False):
            refined, _ = refine_package(package, script=script, brief=build_creator_brief(script=script, video_format="vlog"),
                                        language="english", region="india", evidence=evidence, competitors=[])
        self.assertGreaterEqual(len(refined["tags"]), 5)
        self.assertIn("top station sunrise hike", refined["tags"])

    def test_title_with_the_search_phrase_beats_a_quote_echo(self):
        from win_engine.generation.quality_refinement import refine_package

        betrayal = "The biggest betrayal is knowing that if you didn't find out, they would have never told you."
        evidence = {"subject_terms": ["betrayal"], "selected_keywords": [
            {"keyword": "betrayal quotes", "keyword_relevance_score": 90, "demand_validated": True,
             "source_support_score": 100, "classification": "long_tail"},
            {"keyword": "hidden betrayal", "keyword_relevance_score": 95, "demand_validated": True,
             "source_support_score": 100, "classification": "long_tail"},
        ]}
        package = {"title": "If you didn't find out, they wouldn't have told you #shorts",
                   "variants": ["If you didn't find out, they wouldn't have told you #shorts",
                                "Hidden betrayal hurts the deepest #shorts"],
                   "description": f"“{betrayal}”\n\nHidden betrayal cuts deep when the truth was never meant to reach you.",
                   "tags": ["betrayal quotes", "hidden betrayal", "yt", "shorts"], "hashtags": ["#shorts", "#Betrayal"]}
        brief = build_creator_brief(script=betrayal, exact_quote=betrayal, video_format="youtube_shorts")
        with patch.object(gemini_client, "is_available", return_value=False):
            refined, _ = refine_package(package, script=betrayal, brief=brief, language="english", region="global",
                                        evidence=evidence, competitors=[])
        self.assertEqual(refined["title"], "Hidden betrayal hurts the deepest #shorts")

    def test_a_validated_search_tag_meets_the_tag_bar(self):
        evidence = {"subject_terms": ["love"], "selected_keywords": [
            {"keyword": "love quotes", "keyword_relevance_score": 77, "demand_validated": True,
             "source_support_score": 100, "classification": "long_tail"},
            {"keyword": "impossible love", "keyword_relevance_score": 100, "source_support_score": 100,
             "classification": "long_tail"},
        ]}
        gate = evaluate_package_quality(
            {"title": "Painful love and the ache of things that never can be #shorts", "variants": [],
             "description": f"“{QUOTE}”\n\nLove quotes about impossible love.", "tags": ["love quotes", "impossible love"],
             "hashtags": []},
            script=QUOTE, creator_brief=build_creator_brief(script=QUOTE), require_shorts_tags=False,
            tag_evidence=evidence, enforce_final_tag_rules=False,
        )
        self.assertGreaterEqual(gate["final_seo_quality"]["tag_score"], 90)

    def test_why_click_is_whole_sentences(self):
        package = build_title_thumbnail_packages(
            [{"title": "Impossible love hurts the deepest #shorts", "package_intent": "Search"},
             {"title": "The heavy weight of impossible love #shorts", "package_intent": "Browse"}],
            {"exact_quote": QUOTE, "visual_requirements": VISUAL}, validated=True,
        )
        for item in package:
            self.assertNotIn(": A brief", item["why_click"])
            self.assertNotIn("backed by Rainy", item["why_click"])
        self.assertIn("background (rainy road with vehicles)", package[1]["why_click"])

    def test_quote_short_sections_follow_the_real_tags(self):
        related = ["love quotes", "impossible love", "painful love"]
        graph = build_content_graph_strategy("there is nothing more painful", "", "Story", [
            {"keyword": "There Nothing"}, {"keyword": "More Painful"}], related_phrases=related, short_form=True)
        self.assertEqual(graph["hub_topic"], "love quotes")
        self.assertEqual(graph["supporting_topics"], ["impossible love", "painful love"])
        text = str(graph) + str(build_session_expansion("t", [], related_phrases=related, short_form=True))
        text += build_binge_bridge("t", "Story", related_phrases=related, short_form=True)
        for junk in ("There Nothing", "More Painful", "YouTube Growth System", "mistakes to avoid",
                     "packaging teardown", "case study", "tutorial or checklist"):
            self.assertNotIn(junk, text)
        workflow = build_automation_workflow("When you love something that can never be #shorts", ["#shorts"], [],
                                             graph, short_form=True)
        flat = " ".join(sum(workflow.values(), []))
        self.assertNotIn("30 seconds", flat)
        self.assertNotIn("timestamps", flat)

    def test_long_form_graph_without_tags_does_not_invent_spokes(self):
        graph = build_content_graph_strategy("cold brew coffee", "", "Tutorial", [], related_phrases=[])
        self.assertEqual(graph["supporting_topics"], [])
        self.assertNotIn("mistakes", str(graph))

    def test_quote_short_audit_judges_reading_load(self):
        audit = audit_content_package(f'"{QUOTE}"', "When you love something that can never be #shorts",
                                      "love", "", "Story", video_format="youtube_shorts", exact_quote=QUOTE)
        self.assertEqual(audit["pattern_interrupts"]["assessment"], "NOT_APPLICABLE")
        self.assertEqual(audit["retention_risk"]["level"], "MEDIUM")  # 19 words, about 7.6 seconds
        self.assertEqual(audit["alignment"]["package_match"], "STRONG")
        self.assertNotIn("pattern interrupts", " ".join(audit["retention_risk"]["notes"]).lower())

    def test_quote_short_thumbnail_is_not_instructional(self):
        strategy = build_thumbnail_strategy({}, "Impossible love hurts the deepest", "Story", quote_short=True)
        self.assertEqual(strategy["style"], "quote_frame")
        self.assertEqual(build_thumbnail_strategy({}, "Cold brew at home", "Tutorial")["competitive_strength"], "unknown")


class LongFormSectionTests(unittest.TestCase):
    COLD_BREW = (
        "In this video I show you how to make cold brew coffee at home without any special equipment. You only "
        "need coarse ground coffee, a large mason jar, and cold water."
    )

    def test_a_clear_tutorial_opening_is_not_rated_high_risk(self):
        audit = audit_content_package(self.COLD_BREW, "Cold brew coffee recipe at home", "cold brew coffee", "",
                                      "Tutorial", video_format="tutorial")
        self.assertEqual(audit["hook_audit"]["hook_strength"], "HIGH")
        self.assertEqual(audit["retention_risk"]["level"], "LOW")
        self.assertEqual(audit["pattern_interrupts"]["assessment"], "NOT_ASSESSED")  # a 30-word summary

    def test_follow_ups_are_different_searches(self):
        tags = ["cold brew", "cold brew coffee", "cold brew coffee recipe", "mason jar coffee",
                "how to strain coffee grounds smoothly", "coffee brewing methods"]
        graph = build_content_graph_strategy("how to make cold brew coffee at home without any special equipment",
                                             "", "Tutorial", [], related_phrases=tags)
        self.assertEqual(graph["hub_topic"], "cold brew")
        self.assertEqual(graph["supporting_topics"], ["mason jar coffee", "how to strain coffee grounds smoothly"])
        self.assertEqual(build_session_expansion("t", [], related_phrases=tags)["next_video_hook"],
                         "Watch next: Mason jar coffee")

    def test_thumbnail_text_prefers_a_search_phrase_over_a_sentence_slice(self):
        texts = [item["thumbnail_text"] for item in build_title_thumbnail_packages(
            [{"title": "Every hidden detail you missed in the new GTA 6 footage"}], {}, validated=True,
            focus_phrases=["gta 6 trailer 2", "gta 6 hidden details", "vice city map"],
        )]
        self.assertEqual(texts, ["GTA 6 HIDDEN DETAILS"])

    def test_thumbnail_style_follows_the_format(self):
        self.assertEqual(build_thumbnail_strategy({}, "Munnar trip budget for two", "Story", video_format="vlog")["style"],
                         "scene_thumbnail")
        self.assertEqual(build_thumbnail_strategy({}, "SIP vs lump sum", "Tutorial", video_format="comparison")["style"],
                         "comparison_thumbnail")
        self.assertEqual(build_thumbnail_strategy({}, "Samsung Galaxy S25 Ultra review", "Tutorial", video_format="review")["style"],
                         "proof_thumbnail")


class QuoteParagraphTests(unittest.TestCase):
    def test_commentary_after_a_paraphrased_quote_survives(self):
        brief = build_creator_brief(script=QUOTE, visual_requirements=VISUAL)
        paraphrased = QUOTE.replace("never can be", "can never be")
        package = _sanitize_generated_package(
            {"title": "When you love something that can never be #shorts", "variants": [],
             "description": f"{paraphrased} Impossible love leaves the deepest ache. A rainy road carries the mood.",
             "tags": [], "hashtags": []},
            QUOTE, brief,
        )
        paragraphs = package["description"].split("\n\n")
        self.assertTrue(paragraphs[0].startswith("“There is nothing more painful"))
        self.assertIn("Impossible love leaves the deepest ache.", package["description"])


class BackupModelTests(unittest.TestCase):
    @staticmethod
    def _response(status, payload=None):
        response = MagicMock(status_code=status, headers={})
        response.json.return_value = payload or {}
        return response

    def test_overloaded_primary_switches_to_the_backup_once(self):
        ok = self._response(200, {"candidates": [{"content": {"parts": [{"text": "{}"}]}, "finishReason": "STOP"}]})
        calls = []

        def fake_post(url, **kwargs):
            calls.append(url)
            return self._response(503) if "primary-model" in url else ok

        with patch.dict("os.environ", {"WIN_ENGINE_GEMINI_MODEL": "primary-model",
                                       "WIN_ENGINE_GEMINI_FALLBACK_MODEL": "backup-model",
                                       "WIN_ENGINE_GEMINI_API_KEY": "test-key",
                                       "WIN_ENGINE_GEMINI_TRANSIENT_RETRIES": "0"}), \
                patch.object(gemini_client.httpx, "post", side_effect=fake_post), \
                patch.object(gemini_client.time, "sleep"):
            text, diagnostic = gemini_client.generate_with_diagnostics("p", "s", max_tokens=300)
        self.assertEqual(text, "{}")
        self.assertTrue(diagnostic["backup_model_used"])
        self.assertEqual(diagnostic["model"], "backup-model")
        self.assertEqual([("primary" in url) for url in calls], [True, False])

    def test_no_backup_configured_keeps_old_behaviour(self):
        with patch.dict("os.environ", {"WIN_ENGINE_GEMINI_MODEL": "primary-model",
                                       "WIN_ENGINE_GEMINI_FALLBACK_MODEL": "",
                                       "WIN_ENGINE_GEMINI_API_KEY": "test-key",
                                       "WIN_ENGINE_GEMINI_TRANSIENT_RETRIES": "0"}), \
                patch.object(gemini_client.httpx, "post", return_value=self._response(503)) as post, \
                patch.object(gemini_client.time, "sleep"):
            text, diagnostic = gemini_client.generate_with_diagnostics("p", "s", max_tokens=300)
        self.assertEqual(text, "")
        self.assertEqual(post.call_count, 1)


class JsonRepairTests(unittest.TestCase):
    def test_trailing_commas_are_repaired_without_a_new_call(self):
        from win_engine.llm.seo_writer import _extract_json

        raw = '{\n  "title": "x",\n  "variants": [\n    "a",\n  ],\n  "tags": ["t",],\n}'
        self.assertEqual(_extract_json(raw), {"title": "x", "variants": ["a"], "tags": ["t"]})
        self.assertIsNone(_extract_json("not json"))


class ResearchCacheTests(unittest.TestCase):
    def test_failed_search_is_not_cached(self):
        from win_engine.ingestion.research_service import ResearchService

        service = ResearchService.__new__(ResearchService)
        service._cache = MagicMock()
        service._cache.get.return_value = []  # an entry poisoned by an earlier failure
        service._settings = MagicMock(youtube_max_results=5)
        service._youtube = MagicMock()
        service._youtube.search_videos.return_value = []
        service._youtube.runtime_state.return_value = {"warning": "YouTube API request failed: rateLimitExceeded"}
        results, _ = service._search_research_queries([{"query": "love quotes", "type": "core"}], "evergreen", 60)
        self.assertEqual(results, [])
        service._youtube.search_videos.assert_called_once()  # the empty entry was treated as a miss
        service._cache.set.assert_not_called()  # and the failure was not cached


if __name__ == "__main__":
    unittest.main()
