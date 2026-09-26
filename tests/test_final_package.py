"""Regression tests: what the creator receives is what was judged and scored.

Covers quality labels hard-coded to "approved"/"low", title scores that stayed
with writer-stage titles after refinement replaced them, refinement and final
checks that ignored recent and published titles, a refinement Gemini call made
after the writer had already fallen back, a fallback warning that blamed
validation for every provider failure, duplicate refined variants, and
category presets shown as keyword research.
"""

import unittest
from unittest.mock import patch

from win_engine.analysis.creator_brief import build_creator_brief
from win_engine.analysis.generation_quality import evaluate_package_quality
from win_engine.analysis.package_builder import build_title_thumbnail_packages, title_gate_status
from win_engine.feedback.history_store import HistoryStore
from win_engine.generation.quality_refinement import refine_package
from win_engine.generation.seo_generator import generate_seo_suggestions
from win_engine.llm import gemini_client

COLD_BREW = (
    "In this video I show you how to make cold brew coffee at home without any special "
    "equipment. You only need coarse ground coffee, a large mason jar, and cold water. "
    "Mix one cup of coffee grounds with four cups of water, stir, and let it steep in the "
    "fridge for 12 to 18 hours. Then strain it twice, first through a fine mesh sieve and "
    "then through a paper coffee filter. At the end I compare it side by side with regular "
    "hot brewed coffee and explain why cold brew tastes smoother and less bitter."
)
COLD_BREW_DESC = (
    "Learn how to make smooth cold brew coffee at home with just a mason jar. No special "
    "equipment needed.\n\n"
    "You need coarse ground coffee, a large mason jar and cold water. Use one cup of grounds "
    "to four cups of water and steep it in the fridge for 12 to 18 hours.\n\n"
    "Strain it twice through a fine mesh sieve and then a paper coffee filter. At the end I "
    "compare it with hot brewed coffee and explain why cold brew tastes smoother and less bitter."
)
# The writer's title lacks the main search phrase, so refinement asks Gemini
# for a repair and a repaired title that carries it outranks the original.
WRITER_TITLE = "Why Cold Water Makes a Smoother Cup at Home"
REPAIRED_TITLE = "Cold Brew Coffee at Home With Just a Mason Jar"


def _candidate(keyword, score):
    return {
        "keyword": keyword, "classification": "core_topic", "keyword_relevance_score": score,
        "content_relevance_score": 42, "source_support_score": 100,
        "source_support": "direct creator-source support", "source_classification": "combined",
        "evidence_count": 3, "sources": ["semantic"], "demand_validated": True, "demand_rank": 0,
    }


def _research(store, **extra):
    research = {
        "history_store": store, "youtube_results": [], "entity_signals": [], "top_opportunities": [],
        "upload_timing": {}, "thumbnail_intelligence": {},
        "keyword_signals": [{"keyword": "cold brew coffee", "mentions": 3}],
        "keyword_research": {
            "candidates": [_candidate("cold brew coffee", 95), _candidate("mason jar coffee", 92)],
            "subject_terms": ["cold", "brew", "coffee"],
            "content_terms": ["cold", "brew", "coffee", "mason", "jar", "water", "grounds", "fridge", "filter"],
        },
    }
    research.update(extra)
    return research


def _writer_package(title=WRITER_TITLE):
    return {"title": title, "variants": [title], "description": COLD_BREW_DESC,
            "tags": ["cold brew coffee", "mason jar coffee"], "hashtags": ["#ColdBrew"]}


def _repaired_package():
    return {"title": REPAIRED_TITLE, "variants": [REPAIRED_TITLE], "description": COLD_BREW_DESC,
            "tags": ["cold brew coffee"], "hashtags": ["#ColdBrew"]}


def _run(research, writer_output, *, available=True, repaired=None, source="gemini", diagnostics=None):
    brief = build_creator_brief(script=COLD_BREW)
    with patch("win_engine.generation.strategy_engine.write_multilang_packages_with_source",
               return_value=({"english": writer_output}, source)), \
         patch("win_engine.generation.strategy_engine.last_generation_diagnostics",
               return_value=diagnostics or {}), \
         patch.object(gemini_client, "is_available", return_value=available), \
         patch("win_engine.generation.quality_refinement.generate_one",
               return_value=repaired) as refinement_call:
        response = generate_seo_suggestions(COLD_BREW, research, context={
            "language": "english", "region": "global", "creator_brief": brief,
        })
    return response, refinement_call


class RescoredFinalTitleTests(unittest.TestCase):
    def test_scores_and_feedback_follow_the_refined_title(self):
        response, refinement_call = _run(_research(HistoryStore(":memory:")), _writer_package(),
                                         repaired=_repaired_package())
        self.assertEqual(refinement_call.call_count, 1)
        self.assertEqual(response["title"], REPAIRED_TITLE)
        scored = response["title_optimization"]["scored_variants"]
        self.assertEqual(response["title_optimization"]["best_title"], REPAIRED_TITLE)
        self.assertEqual(scored[0]["title"], REPAIRED_TITLE)
        self.assertEqual({item["title"] for item in scored}, set(dict.fromkeys([response["title"], *response["title_variants"]])))
        self.assertTrue(all(item["score"] > 0 for item in scored))
        self.assertEqual(response["ctr_prediction"]["title_quality_score"], scored[0]["score"])
        self.assertEqual(response["ab_test_pack"]["variation_a"], REPAIRED_TITLE)
        self.assertEqual(response["performance_sync"]["current_title_score"], scored[0]["score"])

    def test_the_refinement_request_is_counted(self):
        writer = {**_writer_package(), "generation_trace": {
            "gemini_call_count": 1, "provider_requests": 1, "provider_attempts": 1,
            "retry_count": 0, "provider_retries": 0, "retry_reasons": [],
        }}
        repaired = {**_repaired_package(), "_provider_trace": {
            "status": "gemini_success", "attempts": 2, "retries": 1, "retry_reasons": ["rate_limit"],
        }}
        response, _ = _run(_research(HistoryStore(":memory:")), writer, repaired=repaired)
        trace = response["generation_trace"]
        self.assertTrue(trace["quality_refinement"]["attempted"])
        self.assertEqual(trace["quality_refinement"]["provider_call"]["attempts"], 2)
        self.assertTrue(trace["gemini_attempted"])
        self.assertEqual(trace["gemini_call_count"], 2)
        self.assertEqual(trace["provider_requests"], 2)
        self.assertEqual(trace["provider_attempts"], 3)
        self.assertEqual(trace["retry_count"], 1)
        self.assertEqual(trace["retry_reasons"], ["rate_limit"])

    def test_history_keeps_the_delivered_titles_score(self):
        store = HistoryStore(":memory:")
        with patch.object(store, "record_analysis_run", wraps=store.record_analysis_run) as record:
            response, _ = _run(_research(store), _writer_package(), repaired=_repaired_package())
        writer_score = record.call_args.kwargs["title_score"]
        final_score = response["ctr_prediction"]["title_quality_score"]
        self.assertNotEqual(writer_score, final_score)
        saved = store.history_run(response["history_run_id"])
        self.assertEqual(saved["title"], REPAIRED_TITLE)
        self.assertEqual(saved["title_score"], final_score)

    def test_packages_carry_the_final_gate_verdict(self):
        response, _ = _run(_research(HistoryStore(":memory:")), _writer_package(), repaired=_repaired_package())
        gate = response["generation_quality"]
        accepted = {item["title"] for item in gate["accepted_candidates"]}
        self.assertTrue(response["title_thumbnail_packages"])
        for package in response["title_thumbnail_packages"]:
            with self.subTest(title=package["title"]):
                self.assertEqual(package["quality_gate"]["source"], "final_quality_gate")
                expected = "approved" if package["title"] in accepted else "rejected"
                self.assertEqual(package["quality_status"], expected)


class TitleHistoryTests(unittest.TestCase):
    def test_refinement_cannot_reuse_a_recent_title(self):
        store = HistoryStore(":memory:")
        store.record_analysis_run(
            "an earlier video", "SEARCH", "Authority", REPAIRED_TITLE, 8.0, "LOW", "WORKABLE", 60.0,
        )
        response, refinement_call = _run(_research(store), _writer_package(), repaired=_repaired_package())
        self.assertEqual(refinement_call.call_count, 1)
        self.assertNotEqual(response["title"], REPAIRED_TITLE)
        self.assertNotIn(REPAIRED_TITLE, response["title_variants"])

    def test_final_gate_sees_titles_from_before_this_run(self):
        store = HistoryStore(":memory:")
        store.record_analysis_run("an earlier video", "SEARCH", "Authority", "Earlier title", 8.0, "LOW", "WORKABLE", 60.0)
        research = _research(store, youtube_results=[{"title": "Cold brew in 5 minutes", "view_count": 100}])
        with patch("win_engine.generation.seo_generator.evaluate_package_quality",
                   wraps=evaluate_package_quality) as final_gate:
            _run(research, _writer_package(), available=False)
        kwargs = final_gate.call_args.kwargs
        self.assertEqual(kwargs["recent_titles"], ["Earlier title"])
        self.assertEqual(kwargs["published_titles"], [])
        self.assertEqual(kwargs["competitor_titles"], ["Cold brew in 5 minutes"])

    def test_refinement_checks_and_prompts_with_channel_history(self):
        learning = {"recent_titles": ["Recent one"], "published_titles": ["Published one"]}
        # A measured shortfall (a 60-point tag) prompts the repair; a score that
        # was never measured does not.
        package = {"title": WRITER_TITLE, "variants": [WRITER_TITLE], "description": COLD_BREW_DESC,
                   "tags": ["cold brew coffee"], "hashtags": []}
        evidence = {"selected_keywords": [{**_candidate("cold brew coffee", 60), "demand_validated": False}]}
        with patch("win_engine.generation.quality_refinement.evaluate_package_quality",
                   wraps=evaluate_package_quality) as gate, \
             patch.object(gemini_client, "is_available", return_value=True), \
             patch("win_engine.generation.quality_refinement.generate_one", return_value=None) as refinement_call:
            refine_package(package, script=COLD_BREW, brief={}, language="english", region="global",
                           evidence=evidence, competitors=[], channel_learning=learning)
        self.assertTrue(gate.call_args_list)
        for call in gate.call_args_list:
            self.assertEqual(call.kwargs["recent_titles"], ["Recent one"])
            self.assertEqual(call.kwargs["published_titles"], ["Published one"])
        self.assertIs(refinement_call.call_args.kwargs["channel_learning"], learning)


class RefinedVariantTests(unittest.TestCase):
    def test_a_promoted_alternative_is_listed_once(self):
        evidence = {"subject_terms": ["cold", "brew", "coffee"], "selected_keywords": [
            {**_candidate("cold brew coffee", 95), "classification": "core_topic"},
        ]}
        package = {"title": WRITER_TITLE, "variants": [WRITER_TITLE, REPAIRED_TITLE], "description": COLD_BREW_DESC,
                   "tags": ["cold brew coffee"], "hashtags": []}
        with patch.object(gemini_client, "is_available", return_value=False):
            refined, _ = refine_package(package, script=COLD_BREW, brief=build_creator_brief(script=COLD_BREW),
                                        language="english", region="global", evidence=evidence, competitors=[])
        self.assertEqual(refined["title"], REPAIRED_TITLE)
        self.assertEqual(refined["variants"], [REPAIRED_TITLE, WRITER_TITLE])


class RefinementBudgetTests(unittest.TestCase):
    def test_no_refinement_request_after_the_writer_fell_back(self):
        research = _research(HistoryStore(":memory:"))
        # A weak tag keeps the package under target, which used to trigger the request.
        research["keyword_research"]["candidates"] = [{**_candidate("cold brew coffee", 60), "demand_validated": False}]
        response, refinement_call = _run(research, None, source="fallback", repaired=_repaired_package())
        self.assertEqual(response["generation_source"], "fallback")
        refinement = response["generation_trace"]["quality_refinement"]
        self.assertLess(refinement["before"]["tag_score"], 90)
        refinement_call.assert_not_called()
        self.assertEqual(refinement["skipped_reason"], "writer_used_local_fallback")

    def test_no_refinement_request_while_the_provider_cools_down(self):
        with patch.object(gemini_client, "provider_health", return_value={"cooldown_active": True}):
            response, refinement_call = _run(_research(HistoryStore(":memory:")), _writer_package(),
                                             repaired=_repaired_package())
        refinement_call.assert_not_called()
        self.assertEqual(response["generation_trace"]["quality_refinement"]["skipped_reason"], "provider_cooling_down")
        self.assertEqual(response["title"], WRITER_TITLE)


class FallbackWarningTests(unittest.TestCase):
    def _warnings(self, diagnostics):
        response, _ = _run(_research(HistoryStore(":memory:")), None, source="fallback",
                           diagnostics={"english": diagnostics})
        return [item for item in response["research_warnings"] if "local fallback" in item]

    def test_the_warning_names_the_provider_failure(self):
        cases = {
            "gemini_rate_limited": "Gemini rate-limited the request",
            "gemini_timeout": "Gemini timed out",
            "gemini_cooldown": "Gemini is paused after repeated failures",
            "gemini_unavailable": "Gemini is not configured",
        }
        for status, cause in cases.items():
            with self.subTest(status=status):
                warnings = self._warnings({"status": status, "events": [status]})
                self.assertEqual(len(warnings), 1)
                self.assertTrue(warnings[0].startswith(cause))
                self.assertNotIn("validation", warnings[0])

    def test_a_rejected_gemini_package_is_reported_as_a_validation_failure(self):
        warnings = self._warnings({
            "status": "gemini_success", "fallback_reason": "quality_gate_rejection",
            "initial_quality_rejection": {"verdict": "RED"},
        })
        self.assertEqual(warnings, [
            "No Gemini package passed the local validation checks, so this run used the content-specific local fallback."
        ])


class KeywordSignalFallbackTests(unittest.TestCase):
    def test_empty_research_is_reported_not_filled_with_presets(self):
        script = "A night-mode walkthrough of the Pixel camera on a rooftop at dusk, with raw samples."
        store = HistoryStore(":memory:")
        research = {"history_store": store, "youtube_results": [], "keyword_signals": [], "entity_signals": [],
                    "top_opportunities": [], "upload_timing": {}, "thumbnail_intelligence": {}}
        with patch("win_engine.generation.strategy_engine.write_multilang_packages_with_source",
                   return_value=({"english": None}, "fallback")), \
             patch.object(gemini_client, "is_available", return_value=False):
            response = generate_seo_suggestions(script, research, context={
                "language": "english", "region": "global", "category": "tech",
                "creator_brief": build_creator_brief(script=script),
            })
        self.assertEqual(response["keyword_signals"], [])
        self.assertTrue(any(item.startswith("Keyword signals are unavailable") for item in response["research_warnings"]))
        presets = {"tech review", "smartphone guide", "app tutorial", "best gadgets", "tech tips", "honest review"}
        self.assertFalse(presets & set(response["tags"]))


class PackageLabelTests(unittest.TestCase):
    GATE = {
        "accepted_candidates": [{"title": "Cold Brew Coffee at Home"}],
        "rejected_candidates": [
            {"title": "Cold Brew Coffee That Cures Anxiety", "issues": [{"code": "unsupported_context"}]},
            {"title": "Cold Brew Coffee at Home, Again", "issues": [{"code": "semantic_duplicate"}]},
        ],
    }

    def test_labels_follow_each_titles_verdict(self):
        titles = ["Cold Brew Coffee at Home", "Cold Brew Coffee That Cures Anxiety", "Cold Brew Coffee at Home, Again",
                  "A Title No Gate Saw"]
        rows = [{"title": title, "quality_gate": title_gate_status(title, self.GATE, source="final_quality_gate")}
                for title in titles[:3]] + [{"title": titles[3]}]
        packages = build_title_thumbnail_packages(rows, {}, validated=True)
        labels = [(item["quality_status"], item["misleading_risk"]) for item in packages]
        self.assertEqual(labels, [
            ("approved", "low"), ("rejected", "high"), ("rejected", "low"), ("not evaluated", "not evaluated"),
        ])
        self.assertEqual(packages[1]["quality_gate"]["issues"], ["unsupported_context"])

    def test_the_builders_own_checks_still_count_as_an_evaluation(self):
        packages = build_title_thumbnail_packages(
            [{"title": "How to Make Cold Brew Coffee With a Mason Jar"}], {"content": COLD_BREW},
        )
        self.assertEqual((packages[0]["quality_status"], packages[0]["misleading_risk"]), ("approved", "low"))


if __name__ == "__main__":
    unittest.main()
