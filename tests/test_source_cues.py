"""Regression tests for the generation-heuristic audit (AN-2/3/4/5/19/20/21/46/84/85).

Each test pins a verified failure: a word that made a tutorial a Short, a
quoted button name that became a mandatory quote, a visual requirement read
out of "Visual Studio Code", a stock concept searched against the opposite
meaning, a title written for a test quote, and a score raised and reported as
measured.
"""

import unittest
from unittest.mock import patch

from win_engine.analysis.content_auditor import audit_content_package
from win_engine.analysis.creator_brief import build_creator_brief, creator_topic
from win_engine.analysis.generation_quality import evaluate_package_quality, is_short_content
from win_engine.analysis.keyword_research import build_keyword_research, select_final_tags
from win_engine.analysis.pacing_engine import analyze_script_pacing
from win_engine.analysis.research_planner import plan_research_queries
from win_engine.analysis.retention_assistant import analyze_retention_assistant
from win_engine.analysis.semantic_research import analyze_script_semantics
from win_engine.analysis.source_cues import extract_quote, is_short_video, labelled_visual, source_quote
from win_engine.analysis.topic_lock import extract_main_topic, infer_category
from win_engine.feedback.history_store import HistoryStore
from win_engine.generation.quality_refinement import enforce_quality_target
from win_engine.generation.seo_generator import generate_seo_suggestions
from win_engine.generation.strategy_engine import _content_specific_fallback
from win_engine.llm import gemini_client
from win_engine.llm.seo_writer import _sanitize_generated_package

SHORT_RIBS = (
    "How to cook short ribs in the oven: season them, sear them in a hot pan, "
    "then braise them for three hours until tender."
)
GALAXY = "In short, the Galaxy S25 has the best battery of any phone I tested this year."
SAVE_CHANGES = (
    'In this tutorial I show you how to turn on dark mode. Open Settings, pick Appearance, '
    'then click "Save changes" and restart the app.'
)
PAINFUL = '"There is nothing more painful in this world than to be in love with something that never can be."'


class ShortResolverTests(unittest.TestCase):
    """AN-2 / AN-5 / AN-85: one resolver, and a known format decides."""

    def test_non_short_formats_are_never_shorts_whatever_the_text_says(self):
        for script, video_format in ((SHORT_RIBS, "tutorial"), (GALAXY, "review"), ("A #shorts tag in a vlog", "vlog")):
            with self.subTest(video_format=video_format):
                brief = build_creator_brief(script=script, video_format=video_format)
                self.assertFalse(is_short_content(script, brief))

    def test_a_long_form_story_with_a_short_duration_stays_long_form(self):
        brief = build_creator_brief(
            script='On-screen quote: "Some doors close so the right ones can open".',
            video_format="story", duration_seconds=15,
        )
        self.assertFalse(is_short_video(brief["content"], brief))

    def test_short_formats_and_explicit_cues_are_shorts(self):
        for brief in (
            {"video_format": "Short"}, {"video_format": "youtube_shorts"}, {"video_format": "quote"},
            {"video_format": "YouTube Short emotional quote video"}, {"video_format": "reels"},
            {"duration_seconds": 45}, {"content": "Behind the scenes #shorts"},
            {"content": "A YouTube Short about my commute"}, {"content": "short-form clip of the match"},
        ):
            with self.subTest(brief=brief):
                self.assertTrue(is_short_video("", brief))

    def test_bare_short_words_and_long_durations_are_not_shorts(self):
        for brief in (
            {"content": SHORT_RIBS}, {"content": GALAXY}, {"content": "A short guide to budgeting"},
            {"duration_seconds": 600, "content": "#shorts"}, {"video_format": "other", "content": "summer shorts haul"},
        ):
            with self.subTest(brief=brief):
                self.assertFalse(is_short_video("", brief))

    def test_a_number_read_out_of_the_script_is_not_the_video_length(self):
        brief = build_creator_brief(script="Microwave the rice for 90 seconds, then stir in the butter.")
        self.assertEqual(brief["duration_seconds"], 90)
        self.assertEqual(brief["field_provenance"]["duration_seconds"]["source"], "inferred")
        self.assertNotEqual(brief["video_format"], "youtube_shorts")
        self.assertFalse(is_short_content(brief["content"], brief))

    def test_a_short_ribs_tutorial_gets_no_shorts_rules(self):
        brief = build_creator_brief(script=SHORT_RIBS, video_format="tutorial")
        gate = evaluate_package_quality(
            {"title": "How to Cook Short Ribs in the Oven", "variants": [],
             "description": "Season the short ribs, sear them in a hot pan, then braise them for three hours.",
             "tags": ["short ribs"], "hashtags": ["#ShortRibs"]},
            script=SHORT_RIBS, creator_brief=brief, enforce_final_tag_rules=False,
        )
        codes = {item["code"] for item in gate["issues"]} | {
            reason["code"] for item in gate["rejected_candidates"] for reason in item["issues"]
        }
        self.assertNotIn("missing_shorts_title_hashtag", codes)
        retention = analyze_retention_assistant(SHORT_RIBS, creator_brief=brief)
        self.assertEqual(retention["pacing"]["format_assessment"], "long_form_or_unspecified")
        tags, _ = select_final_tags({"candidates": []}, generated_tags=[], title="", script=SHORT_RIBS, creator_brief=brief)
        self.assertNotIn("shorts", tags)

    def test_the_quotes_category_does_not_make_a_talk_a_short(self):
        script = (
            "Five lessons I learned building a bootstrapped startup: charge from day one, talk to customers "
            "weekly, hire slowly, keep costs low, and write everything down."
        )
        brief = build_creator_brief(script=script)
        self.assertEqual(infer_category(script), "quotes")
        rows = [
            {"keyword": keyword, "sources": ["model"], "classification": "core_topic", "keyword_relevance_score": 94,
             "content_relevance_score": 42, "source_support_score": 100, "source_support": "direct",
             "source_classification": "script_derived"}
            for keyword in ("bootstrapped startup", "startup lessons")
        ]
        research = {
            "main_topic": "bootstrapped startup", "keyword_signals": [], "entity_signals": [], "top_opportunities": [],
            "youtube_results": [], "research_queries": [], "creator_brief": brief,
            "keyword_research": {"candidates": rows, "content_terms": ["bootstrapped", "startup", "lessons"]},
            "history_store": HistoryStore(":memory:"),
        }
        package = {
            "title": "5 Bootstrapped Startup Lessons I Learned", "variants": ["5 Bootstrapped Startup Lessons I Learned"],
            "description": "Five lessons from building a bootstrapped startup: charge from day one and talk to customers weekly.",
            "tags": ["bootstrapped startup", "startup lessons"], "hashtags": ["#BootstrappedStartup"],
        }
        context = {"language": "english", "video_language": "english", "region": "global", "creator_brief": brief}
        with patch("win_engine.generation.strategy_engine.write_multilang_packages_with_source",
                   return_value=({"english": package}, "gemini")), \
             patch.object(gemini_client, "is_available", return_value=False):
            response = generate_seo_suggestions(script, research, context=context)
        self.assertNotIn("yt", response["tags"])
        self.assertNotIn("shorts", response["tags"])
        self.assertNotIn("#shorts", [tag.casefold() for tag in response["hashtags"]])
        self.assertNotIn("#shorts", response["title"].casefold())
        self.assertNotIn("platform_tag_filler", [item["code"] for item in response["generation_quality"]["issues"]])


class BriefFormatInferenceTests(unittest.TestCase):
    """AN-4: only explicit cues infer a Short."""

    def test_weak_cues_no_longer_infer_a_short(self):
        for script in (
            "Our travel vlog from Goa: we watched the sunset at Vagator beach and ate at a shack.",
            'How to fix "Error 404" on WordPress permalinks',
            "Morning motivation talk: why I stopped chasing productivity hacks and started sleeping more.",
            "An aesthetic desk setup tour with my favourite keyboard and lamp.",
        ):
            with self.subTest(script=script):
                self.assertNotEqual(build_creator_brief(script=script)["video_format"], "youtube_shorts")

    def test_error_404_is_not_a_quote(self):
        brief = build_creator_brief(script='How to fix "Error 404" on WordPress permalinks')
        self.assertEqual(brief["video_format"], "tutorial")
        self.assertEqual(brief["exact_quote"], "")

    def test_explicit_cues_still_infer_a_short(self):
        for script in (
            PAINFUL,
            "the quote is- You don't give up overnight on someone. and the video is of rain on a window",
            "the quote on video is- let go of what does not stay and the video is of a road",
            "Quote: \"Be gentle with the person you were\" #shorts",
            "late night thoughts, quiet emotional quotes, youtube shorts",
        ):
            with self.subTest(script=script):
                self.assertEqual(build_creator_brief(script=script)["video_format"], "youtube_shorts")

    def test_a_stated_length_decides(self):
        self.assertEqual(build_creator_brief(script="My desk tour", duration_seconds=45)["video_format"], "youtube_shorts")
        self.assertNotEqual(
            build_creator_brief(script="the quote is- stay kind always", duration_seconds=600)["video_format"],
            "youtube_shorts",
        )


class QuoteExtractionTests(unittest.TestCase):
    """AN-21 / AN-84: one extractor, labelled or quote-Short spans only."""

    def test_a_quoted_button_in_a_tutorial_is_not_a_mandatory_quote(self):
        brief = build_creator_brief(script=SAVE_CHANGES)
        self.assertEqual(brief["video_format"], "tutorial")
        self.assertEqual(brief["exact_quote"], "")
        gate = evaluate_package_quality(
            {"title": "How to Turn On Dark Mode in Settings", "variants": [],
             "description": "Turn on dark mode from Settings, pick Appearance and restart the app.",
             "tags": ["dark mode"], "hashtags": ["#DarkMode"]},
            script=SAVE_CHANGES, creator_brief=brief, enforce_final_tag_rules=False,
        )
        self.assertNotIn("quote_fidelity", [item["code"] for item in gate["issues"]])
        self.assertFalse(gate["exact_quote_checked"])
        self.assertNotEqual(extract_main_topic(SAVE_CHANGES), "save changes")
        self.assertNotIn("save changes", creator_topic(brief))
        self.assertNotIn("save changes", creator_topic({"content": SAVE_CHANGES, "video_format": "tutorial"}))

    def test_a_tutorial_short_does_not_turn_its_quoted_label_into_a_quote(self):
        script = '#shorts How to fix "Error 404" on WordPress in 30 seconds'
        self.assertTrue(is_short_video(script))
        self.assertEqual(extract_quote(script, short=True), "")
        self.assertEqual(build_creator_brief(script=script, video_format="Short")["exact_quote"], "")

    def test_quote_shorts_keep_their_quotes(self):
        brief = build_creator_brief(script=PAINFUL)
        self.assertEqual(
            brief["exact_quote"],
            "There is nothing more painful in this world than to be in love with something that never can be",
        )
        story = build_creator_brief(
            script='Background video: a quiet harbour at dawn. On-screen quote: "Some doors close so the right ones can open".',
            video_format="story",
        )
        self.assertEqual(story["exact_quote"], "Some doors close so the right ones can open")
        labelled = build_creator_brief(script="the quote is- stay soft in a hard world and the video is of a beach at dusk")
        self.assertEqual(labelled["exact_quote"], "stay soft in a hard world")

    def test_production_notes_after_a_labelled_quote_are_not_part_of_it(self):
        # Two common ways of starting the visual note were read as part of the
        # quote: "and the video background is ..." and a note glued to the full stop.
        cases = {
            "the quote is- Some doors close so the right ones can open and the video "
            "background is of a harbour at dawn":
                "Some doors close so the right ones can open",
            "the quote is- Be gentle with the person you were yesterday.and video is of a train window":
                "Be gentle with the person you were yesterday",
        }
        for script, quote in cases.items():
            with self.subTest(script=script):
                self.assertEqual(build_creator_brief(script=script)["exact_quote"], quote)

    def test_every_reader_uses_the_same_quote_and_threshold(self):
        # A 9-character quote: the gate required it (6) while the writer, the
        # pacing check and the auditor looked only for 12 or more.
        script = 'Quote: "Stay kind." #shorts'
        self.assertEqual(source_quote(script), "Stay kind")
        package = _sanitize_generated_package(
            {"title": "A gentle reminder for hard days #shorts", "variants": [],
             "description": "A calm reminder for hard days.", "tags": [], "hashtags": ["#shorts"]},
            script, None,
        )
        self.assertIn("Stay kind", package["description"])
        gate = evaluate_package_quality(package, script=script, creator_brief=None, enforce_final_tag_rules=False)
        self.assertNotIn("quote_fidelity", [item["code"] for item in gate["issues"]])
        self.assertEqual(analyze_script_pacing(script, video_format="youtube_shorts")["analysis_type"], "quote_short")
        retention = analyze_retention_assistant(script, creator_brief=None)
        self.assertEqual(retention["quote_presentation"]["status"], "available")

    def test_the_auditor_treats_a_long_form_story_with_a_quote_as_long_form(self):
        script = 'Background video: a quiet harbour. On-screen quote: "Some doors close so the right ones can open".'
        audit = audit_content_package(script, "When the right doors open", "doors closing", "", video_format="story")
        # The long-form audit states its basis; the quote-Short audit does not.
        self.assertIn("basis", audit["hook_audit"])
        self.assertEqual(analyze_script_pacing(script, video_format="story")["analysis_type"], "spoken_script")


class VisualRequirementTests(unittest.TestCase):
    """AN-3: visuals come only from an explicit label and never remove content words."""

    def test_prose_mentioning_visual_or_video_is_not_a_visual_requirement(self):
        for script in (
            "In this Visual Studio Code tutorial I show you how to set up Python debugging with breakpoints.",
            "This video is about budgeting for college students who share an apartment.",
            "the quote on the video is- the quieter you become, the more you can hear",
        ):
            with self.subTest(script=script):
                self.assertEqual(build_creator_brief(script=script)["visual_requirements"], "")

    def test_an_explicit_label_is_a_visual_requirement(self):
        self.assertEqual(labelled_visual("Background video: harbour lights at dusk. On-screen quote: \"x y z\""), "harbour lights at dusk")
        self.assertEqual(labelled_visual("This is a Short.\n\nBackground visual:\nA lighthouse beam over calm water. Gulls circle."),
                         "A lighthouse beam over calm water")
        self.assertEqual(labelled_visual("Visual: Rain drops on window pane at dusk\nVoice-over: none"), "Rain drops on window pane at dusk")
        self.assertEqual(labelled_visual("B-roll: city lights at night"), "city lights at night")
        self.assertEqual(labelled_visual("Background:\n\nRainy road with vehicles."), "Rainy road with vehicles")
        self.assertEqual(labelled_visual("The background-free logo pack"), "")

    def test_inferred_visual_words_stay_content_terms(self):
        script = "Background: budgeting spreadsheet on a laptop. This video is about budgeting for college students."
        brief = build_creator_brief(script=script)
        self.assertEqual(brief["visual_requirements"], "budgeting spreadsheet on a laptop")
        self.assertEqual(brief["field_provenance"]["visual_requirements"]["source"], "inferred")
        research = build_keyword_research(
            script=script, semantic={}, youtube_results=[], research_queries=[], entity_signals=[], creator_brief=brief,
        )
        self.assertTrue({"budgeting", "spreadsheet", "laptop"} <= set(research["content_terms"]))
        vscode = "In this Visual Studio Code tutorial I show you how to set up Python debugging."
        research = build_keyword_research(
            script=vscode, semantic={}, youtube_results=[], research_queries=[], entity_signals=[],
            creator_brief=build_creator_brief(script=vscode),
        )
        self.assertTrue({"studio", "code", "debugging"} <= set(research["content_terms"]))


class ResearchPlanTests(unittest.TestCase):
    """AN-19: no stock concepts; queries come from the creator's own words."""

    def test_a_quote_plans_no_opposite_meaning_query(self):
        script = "I can't get enough of you"
        brief = build_creator_brief(script=script, exact_quote=script, video_format="youtube_shorts")
        with patch.object(gemini_client, "is_available", return_value=False):
            semantic = analyze_script_semantics(script, brief)
        queries = plan_research_queries(script=script, creator_brief=brief, semantic_analysis=semantic)
        text = " ".join(item["query"].casefold() for item in queries)
        self.assertNotIn("let go", text)
        self.assertNotIn("exhaustion", text)
        allowed = {"i", "can't", "get", "enough", "of", "you", "quotes", "about"}
        for item in queries:
            self.assertLessEqual(set(item["query"].casefold().split()), allowed, item)

    def test_the_genuine_in_genuinely_is_not_being_misunderstood(self):
        quote = "My mentor genuinely believed in me long before I believed in myself"
        brief = build_creator_brief(script=f"the quote is- {quote}")
        with patch.object(gemini_client, "is_available", return_value=False):
            semantic = analyze_script_semantics(brief["content"], brief)
        queries = plan_research_queries(script=brief["content"], creator_brief=brief, semantic_analysis=semantic)
        self.assertNotIn("misunderstood", " ".join(item["query"] for item in queries))


class InventedContentTests(unittest.TestCase):
    """AN-20: no titles, meanings or hashtags written for particular test quotes."""

    def _fallback(self, quote: str) -> dict:
        return _content_specific_fallback(quote.casefold(), [], {
            "content": quote, "exact_quote": quote, "video_format": "youtube_shorts",
        })

    def test_need_and_choose_do_not_invent_a_title(self):
        package = self._fallback("Choose your battles, you need rest more than approval")
        self.assertNotIn("Needed, But Never Chosen", package["variants"])
        self.assertTrue(package["title"].startswith("Choose your battles, you need rest"))

    def test_silence_does_not_invent_titles_or_hashtags(self):
        package = self._fallback("Silence says everything about respect")
        self.assertNotIn("#DeepThoughts", package["hashtags"])
        self.assertNotIn("#Solitude", package["hashtags"])
        self.assertEqual(len(package["variants"]), 1)
        self.assertNotIn("Thoughts I Only Share", package["title"])
        self.assertNotIn("silence described", package["description"])

    def test_semantic_primary_topic_is_not_overridden(self):
        source = "Grief is the silence that absence leaves behind."
        answer = (
            '{"primary_topic": "missing someone", "secondary_topics": [], "entities": [], "audience": [], '
            '"search_intents": [], "keyword_clusters": [], "viewer_intent": "emotional_relatable", '
            '"concept_evidence": [{"concept": "missing someone", "source_phrase": "absence leaves behind", '
            '"relationship": "paraphrase"}]}'
        )
        with patch.object(gemini_client, "is_available", return_value=True), \
             patch.object(gemini_client, "generate", return_value=answer):
            semantic = analyze_script_semantics(source, {"content": source})
        self.assertEqual(semantic["primary_topic"], "missing someone")
        self.assertNotIn("grief quotes", semantic["search_intents"])


class UnmeasuredScoreTests(unittest.TestCase):
    """AN-46: an unmeasurable score is None with a reason, never a floor."""

    def test_tamil_title_and_description_scores_are_not_measured(self):
        script = "இந்த வீடியோவில் செட்டிநாடு சிக்கன் பிரியாணி செய்வது எப்படி என்று பார்க்கலாம்."
        gate = evaluate_package_quality(
            {"title": "செட்டிநாடு சிக்கன் பிரியாணி", "variants": [], "description": "வீட்டிலேயே செட்டிநாடு சிக்கன் பிரியாணி.",
             "tags": [], "hashtags": []},
            script=script, language="tamil", enforce_final_tag_rules=False,
        )
        quality = gate["final_seo_quality"]
        self.assertIsNone(quality["title_score"])
        self.assertIsNone(quality["description_score"])
        self.assertIn("title_score", quality["not_measured"])
        self.assertIn("description_score", quality["not_measured"])
        target = enforce_quality_target(gate)["quality_target"]
        self.assertIn("title_score", target["not_measured"])
        self.assertIn("title_score (not measured)", enforce_quality_target(gate)["warnings"][-1]["message"])

    def test_a_sparse_source_description_is_not_measured(self):
        gate = evaluate_package_quality(
            {"title": "Rain on the window at night", "variants": [], "description": "Rain on the window at night.",
             "tags": [], "hashtags": []},
            script="Rain.", enforce_final_tag_rules=False,
        )
        self.assertIsNone(gate["final_seo_quality"]["description_score"])
        self.assertIn("description_score", gate["final_seo_quality"]["not_measured"])

    def test_a_searched_tag_keeps_its_measured_score(self):
        quote = "There is nothing more painful than to be in love with something that never can be"
        evidence = {"subject_terms": ["love"], "selected_keywords": [
            {"keyword": "love quotes", "keyword_relevance_score": 60, "demand_validated": True,
             "source_support_score": 100, "classification": "long_tail"},
        ]}
        gate = evaluate_package_quality(
            {"title": "Painful love that never can be #shorts", "variants": [],
             "description": f"“{quote}”", "tags": ["love quotes"], "hashtags": []},
            script=quote, creator_brief=build_creator_brief(script=quote), tag_evidence=evidence,
            enforce_final_tag_rules=False,
        )
        self.assertEqual(gate["final_seo_quality"]["tag_score"], 60.0)


if __name__ == "__main__":
    unittest.main()
