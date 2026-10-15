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

from win_engine.analysis.creator_brief import build_creator_brief, creator_topic
from win_engine.analysis.generation_quality import evaluate_package_quality
from win_engine.analysis.package_builder import build_title_thumbnail_packages, is_filler_phrase, title_gate_status
from win_engine.analysis.topic_lock import force_hashtags, normalize_hashtag, source_lead_phrase
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


HINDI_EDITING = (
    "मोबाइल वीडियो एडिटिंग कैसे करें: इस ट्यूटोरियल में CapCut ऐप से वीडियो एडिटिंग सीखें। पहले CapCut खोलें, "
    "फिर अपना वीडियो इम्पोर्ट करें, क्लिप काटें, टेक्स्ट और म्यूजिक जोड़ें और 1080p में एक्सपोर्ट करें।"
)
HINDI_EDITING_PACKAGE = {
    "title": "मोबाइल वीडियो एडिटिंग कैसे करें | CapCut Tutorial",
    "variants": ["मोबाइल वीडियो एडिटिंग कैसे करें | CapCut Tutorial", "CapCut से वीडियो एडिटिंग सीखें"],
    "description": "इस ट्यूटोरियल में CapCut ऐप से मोबाइल वीडियो एडिटिंग सीखें: क्लिप काटें, टेक्स्ट और म्यूजिक जोड़ें "
                   "और 1080p में एक्सपोर्ट करें।",
    "tags": ["मोबाइल वीडियो एडिटिंग", "वीडियो एडिटिंग", "capcut tutorial"],
    "hashtags": ["#वीडियोएडिटिंग", "#CapCut"],
}
HINDI_STORY = (
    "यह भी गुजर जाएगा। एक राजा ने फकीर से पूछा कि दुख में क्या करूं। फकीर ने एक अंगूठी दी जिस पर लिखा था: "
    "यह भी गुजर जाएगा। राजा ने सुख और दुख दोनों में यह बात याद रखी।"
)
HINDI_STORY_PACKAGE = {
    "title": "यह भी गुजर जाएगा | राजा और फकीर की कहानी",
    "variants": ["यह भी गुजर जाएगा | राजा और फकीर की कहानी", "राजा और फकीर की अंगूठी की कहानी"],
    "description": "एक राजा और फकीर की कहानी: यह भी गुजर जाएगा। सुख और दुख दोनों में यह बात याद रखें।",
    "tags": ["यह भी गुजर जाएगा", "यह भी गुजर जाएगा कहानी", "राजा और फकीर की कहानी"],
    "hashtags": ["#यहभीगुजरजाएगा", "#कहानी"],
}
UPSC_NOTES = "सबसे पहले NCERT की किताबें पढ़ें, फिर रोज अखबार पढ़ें और नोट्स बनाएं।"
HINDI_GREETING = f"नमस्ते दोस्तों! आज हम बात करेंगे UPSC की तैयारी के बारे में। {UPSC_NOTES}"
UPSC_PACKAGE = {
    "title": "UPSC की तैयारी कैसे करें | NCERT से शुरुआत",
    "variants": ["UPSC की तैयारी कैसे करें | NCERT से शुरुआत", "UPSC तैयारी: NCERT और अखबार"],
    "description": f"UPSC की तैयारी के लिए {UPSC_NOTES}",
    "tags": ["upsc की तैयारी", "ncert books", "upsc preparation"],
    "hashtags": ["#UPSC", "#NCERT"],
}


def _run_hindi(script, writer=None, *, video_format=""):
    """A Hindi run; without a writer package Gemini is off and the local fallback ships."""

    brief = build_creator_brief(script=script, language="hindi", video_format=video_format)
    research = {"history_store": HistoryStore(":memory:"), "youtube_results": [], "keyword_signals": [],
                "entity_signals": [], "top_opportunities": [], "upload_timing": {}, "thumbnail_intelligence": {}}
    with patch("win_engine.generation.strategy_engine.write_multilang_packages_with_source",
               return_value=({"hindi": writer}, "gemini" if writer else "fallback")), \
         patch("win_engine.generation.strategy_engine.last_generation_diagnostics", return_value={}), \
         patch.object(gemini_client, "is_available", return_value=writer is not None), \
         patch("win_engine.generation.quality_refinement.generate_one", return_value=None):
        return generate_seo_suggestions(script, research, context={
            "language": "hindi", "region": "india", "creator_brief": brief,
        })


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


class SavedRunTests(unittest.TestCase):
    def test_the_saved_run_leaves_out_research_only_result_detail(self):
        # analysis_runs.payload_json is cloud-synced; competitor tags and full descriptions only made it grow.
        store = HistoryStore(":memory:")
        row = {"video_id": "v1", "title": "Cold brew in 5 minutes", "view_count": 100, "tags": ["cold brew"],
               "full_description": "x" * 4000, "default_audio_language": "en"}
        with patch.object(store, "update_analysis_payload") as save:
            response, _ = _run(_research(store, youtube_results=[row], top_opportunities=[row]),
                               _writer_package(), available=False)
        saved = save.call_args.args[2]
        for field in ("youtube_results", "top_opportunities"):
            with self.subTest(field=field):
                self.assertEqual(saved[field][0], {"video_id": "v1", "title": "Cold brew in 5 minutes", "view_count": 100})
                self.assertEqual(response[field][0]["tags"], ["cold brew"])  # the response keeps them


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

    def test_the_titles_the_writer_discarded_reach_the_refinement_request(self):
        # One title passed the writer's gate, so the one refinement request asks
        # for alternatives and names the discarded ones.
        discarded = {"title": "Cold brew coffee guaranteed to go viral", "codes": ["invented_outcome"]}
        writer = {**_writer_package(), "generation_trace": {"rejected_titles": [discarded]}}
        response, refinement_call = _run(_research(HistoryStore(":memory:")), writer, repaired=None)
        refinement_call.assert_called_once()
        feedback = " ".join(item["message"] for item in refinement_call.call_args.kwargs["repair_feedback"])
        self.assertIn("Only 1 distinct title(s) passed", feedback)
        self.assertIn(discarded["title"], feedback)
        self.assertNotIn("the quote", feedback)  # not a quote Short
        self.assertEqual(response["generation_trace"]["rejected_titles"], [discarded])


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

    def test_an_exhausted_call_allowance_is_named(self):
        # Research runs first on the same allowance; the owner saw the generic warning.
        # The writer's own retries can spend the rest too, so it says no more than that.
        (warning,) = self._warnings({"status": "gemini_budget_exhausted", "events": ["gemini_budget_exhausted"]})
        self.assertTrue(warning.startswith("This request's Gemini call allowance ran out before the writer produced a package"))
        self.assertNotIn("validation", warning)


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


class YouTubeSafeCopyTests(unittest.TestCase):
    def test_a_missing_keyword_or_title_is_not_the_word_none(self):
        from win_engine.generation.strategy_engine import _select_content_angle, _topic_from_signals

        self.assertEqual(_topic_from_signals([{"keyword": None}, {"keyword": "cold brew coffee"}]),
                         ("cold brew coffee", "engagement"))
        self.assertEqual(_select_content_angle("BROWSE", "A calm walk.", [{"title": None}]), "Story")

    def test_narration_about_the_video_is_never_a_tag_or_thumbnail_text(self):
        from win_engine.analysis.package_builder import is_filler_phrase

        for phrase in ("இந்த வீடியோவில் வீட்டிலேயே", "இந்த வீடியோவில்", "வீடியோவில் வீட்டிலேயே சுலபமாக",
                       "इस वीडियो में", "walk through", "in this video"):
            self.assertTrue(is_filler_phrase(phrase), phrase)
        for phrase in ("வீட்டிலேயே சுலபமாக செட்டிநாடு", "mod apk malware", "game walkthrough", "video editing"):
            self.assertFalse(is_filler_phrase(phrase), phrase)
        packages = build_title_thumbnail_packages(
            [{"title": "இந்த வீடியோவில் வீட்டிலேயே சுலபமாக செட்டிநாடு பிரியாணி"}], {}, validated=True,
            focus_phrases=["இந்த வீடியோவில் வீட்டிலேயே", "வீட்டிலேயே சுலபமாக செட்டிநாடு"])
        self.assertEqual(packages[0]["thumbnail_text"], "வீட்டிலேயே சுலபமாக செட்டிநாடு")

    def test_no_delivered_title_carries_characters_youtube_rejects(self):
        from win_engine.analysis.generation_quality import apply_quality_gate

        # Whatever produced the titles, the final step makes them uploadable.
        def with_brackets(package, gate):
            gated = apply_quality_gate(package, gate)
            return {**gated, "title": f"{gated['title']} <3", "variants": [f"{t} -> now" for t in gated["variants"]]}

        store = HistoryStore(":memory:")
        with patch("win_engine.generation.seo_generator.apply_quality_gate", side_effect=with_brackets):
            response, _ = _run(_research(store), _writer_package(REPAIRED_TITLE), available=False)
        options = response["title_optimization"]
        titles = [response["title"], *response["title_variants"], options["best_title"],
                  *(item["title"] for item in options["scored_variants"]),
                  *(item["title"] for item in response["title_thumbnail_packages"]),
                  *(text for package in response["multilang"].values() for text in [package["title"], *package["variants"]])]
        self.assertFalse([title for title in titles if "<" in title or ">" in title])
        self.assertTrue(response["title"].endswith("‹3"))
        self.assertEqual(store.history_run(response["history_run_id"])["title"], response["title"])


class IndicSubjectTests(unittest.TestCase):
    """"This" or "video" inside a Hindi or Tamil subject is the subject, not narration about the video."""

    def test_this_or_video_inside_a_subject_is_not_narration(self):
        for phrase in ("मोबाइल वीडियो एडिटिंग", "वीडियो एडिटिंग", "#वीडियोएडिटिंग", "यह भी गुजर जाएगा",
                       "இந்த காதல்", "इस दुनिया में"):
            with self.subTest(phrase=phrase):
                self.assertFalse(is_filler_phrase(phrase))
        for phrase in ("इस वीडियो में", "यह वीडियो", "இந்த வீடியோவில் வீட்டிலேயே", "வீடியோவில் வீட்டிலேயே சுலபமாக",
                       "#இந்த", "#வீடியோவில்", "#वीडियो", "this video", "walking you through"):
            with self.subTest(phrase=phrase):
                self.assertTrue(is_filler_phrase(phrase))

    def test_a_hindi_subject_keeps_its_tags_hashtags_and_thumbnail(self):
        editing = _run_hindi(HINDI_EDITING, HINDI_EDITING_PACKAGE, video_format="tutorial")
        for tag in ("मोबाइल वीडियो एडिटिंग", "वीडियो एडिटिंग"):
            self.assertIn(tag, editing["tags"])
        self.assertIn("#वीडियोएडिटिंग", editing["hashtags"])
        story = _run_hindi(HINDI_STORY, HINDI_STORY_PACKAGE, video_format="storytelling")
        self.assertIn("यह भी गुजर जाएगा", story["tags"])
        self.assertEqual(story["title_thumbnail_packages"][0]["thumbnail_text"], "यह भी गुजर जाएगा")

    def test_thumbnail_text_never_joins_words_the_title_keeps_apart(self):
        expected = {
            "यह भी गुजर जाएगा | राजा और फकीर की कहानी": "यह भी गुजर जाएगा",
            "मोबाइल वीडियो एडिटिंग कैसे करें": "मोबाइल वीडियो एडिटिंग कैसे",
            "நீ இல்லாத இந்த இரவு மிகவும் நீளமாக இருக்கிறது": "நீ இல்லாத இந்த இரவு",
            # Narration in the middle is left out, not closed over.
            "चिकन बिरयानी इस वीडियो में आसान तरीका": "चिकन बिरयानी",
        }
        for title, text in expected.items():
            with self.subTest(title=title):
                [package] = build_title_thumbnail_packages([{"title": title}], {}, validated=True)
                self.assertEqual(package["thumbnail_text"], text)

    def test_a_hindi_greeting_is_not_the_topic(self):
        self.assertEqual(source_lead_phrase(HINDI_GREETING), "upsc की तैयारी")
        self.assertEqual(creator_topic(build_creator_brief(script=HINDI_GREETING, language="hindi")), "upsc की तैयारी")
        fallback = _run_hindi(HINDI_GREETING)
        self.assertNotIn("नमस्ते", fallback["title"])
        self.assertTrue(fallback["hashtags"])
        self.assertEqual(fallback["content_graph_strategy"]["hub_topic"], "upsc की तैयारी")
        # The writer's title is scored against the subject, as it is without a greeting.
        greeted = _run_hindi(HINDI_GREETING, UPSC_PACKAGE)
        plain = _run_hindi(f"UPSC की तैयारी। {UPSC_NOTES}", UPSC_PACKAGE)
        self.assertEqual(greeted["ctr_prediction"]["title_quality_score"],
                         plain["ctr_prediction"]["title_quality_score"])

    def test_hindi_openers_are_dropped_and_other_openings_are_unchanged(self):
        expected = {
            "नमस्कार दोस्तों, आज के इस वीडियो में हम जानेंगे कि UPSC की तैयारी कैसे करें।": "upsc की तैयारी कैसे करें",
            "हेलो दोस्तों। आज हम UPSC की तैयारी के बारे में बात करेंगे।": "upsc की तैयारी",
            "दोस्तों, इस वीडियो में मोबाइल वीडियो एडिटिंग सीखें।": "मोबाइल वीडियो एडिटिंग सीखें",
            # "Friends" or "namaste" as the subject stays.
            "दोस्तों के साथ गोवा ट्रिप। पहला दिन बीच पर।": "दोस्तों के साथ गोवा ट्रिप",
            "नमस्ते का महत्व। भारत में लोग हाथ जोड़कर मिलते हैं।": "नमस्ते का महत्व",
            "Hey guys, welcome back! In this video I show you how to fix a flat tyre.": "how to fix a flat tyre",
            "Hello everyone, let's talk about budget travel in Munnar.": "budget travel in munnar",
            "வணக்கம்! இந்த வீடியோவில் செட்டிநாடு சிக்கன் பிரியாணி செய்வது எப்படி என்று பார்க்கலாம்.":
                "செட்டிநாடு சிக்கன் பிரியாணி செய்வது எப்படி என்று பார்க்கலாம்",
        }
        for script, topic in expected.items():
            with self.subTest(script=script):
                self.assertEqual(source_lead_phrase(script), topic)

    def test_a_tamil_greeting_or_hindi_about_to_tell_is_not_the_topic(self):
        biryani = "செட்டிநாடு சிக்கன் பிரியாணி செய்வது எப்படி என்று பார்க்கலாம்"
        expected = {
            f"வணக்கம் நண்பர்களே! இந்த வீடியோவில் {biryani}.": biryani,
            f"வணக்கம் நண்பர்களே {biryani}.": biryani,
            f"அனைவருக்கும் வணக்கம். {biryani}.": biryani,
            "दोस्तों, आज मैं आपको बताने वाला हूं iPhone 16 के बारे में।": "iphone 16",
            "आज मैं आपको बताने वाली हूँ घर पर पनीर बनाने का तरीका।": "घर पर पनीर बनाने का तरीका",
            # "Friends' Day" names the subject.
            "நண்பர்கள் தினம் வாழ்த்துக்கள்.": "நண்பர்கள் தினம் வாழ்த்துக்கள்",
        }
        for script, topic in expected.items():
            with self.subTest(script=script):
                self.assertEqual(source_lead_phrase(script), topic)
        brief = build_creator_brief(script=f"வணக்கம் நண்பர்களே! {biryani}.", language="tamil")
        self.assertEqual(creator_topic(brief), biryani)

    def test_a_tie_between_subject_words_has_one_answer(self):
        from win_engine.analysis import topic_lock

        # "masala" and "recipe" are equally long; set order differs per process.
        answers = set()
        for reverse in (False, True):
            keywords = {category: sorted(terms, reverse=reverse)
                        for category, terms in topic_lock.CATEGORY_KEYWORDS.items()}
            with patch.object(topic_lock, "CATEGORY_KEYWORDS", keywords):
                answers.add(topic_lock.extract_main_topic("Masala Tea Recipe"))
        self.assertEqual(answers, {"masala"})

    def test_hashtags_carry_no_invisible_joiners(self):
        zwj, zwnj = "‍", "‌"
        expected = {
            f"#प्यार{zwj}": "#प्यार",
            f"#{zwnj}दिल": "#दिल",
            f"#क्{zwj}षमा": "#क्षमा",
            f"#சிக்கன்{zwnj} பிரியாணி": "#சிக்கன்பிரியாணி",
            f"#love{zwj}": "#love",
        }
        for raw, tag in expected.items():
            with self.subTest(raw=ascii(raw)):
                self.assertEqual(normalize_hashtag(raw), tag)
        self.assertEqual(force_hashtags([f"#प्यार{zwj}", f"#दिल{zwnj}"], "", "quotes"), ["#प्यार", "#दिल"])


if __name__ == "__main__":
    unittest.main()
