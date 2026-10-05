"""Regression tests: a quote Short is packaged as a Short, not as a small long-form video.

A live run ranked the keyword-led "Alone quotes for ..." first although the
quote is not about being alone, wrote production notes ("This video features
... in slow motion, accompanied by the exact on-screen text") as the viewer's
description, and turned YELLOW only because the tag score missed 90, though
tags play a minimal role for a Short.
"""

import json
import unittest
from unittest.mock import patch

from win_engine.analysis.creator_brief import build_creator_brief
from win_engine.analysis.generation_quality import (
    evaluate_package_quality,
    production_note_sentences,
    short_title_fit,
    strip_production_notes,
    title_fluency_issues,
)
from win_engine.generation.quality_refinement import enforce_quality_target, refine_package
from win_engine.generation.strategy_engine import _content_specific_fallback, _safe_minimal_package
from win_engine.llm import seo_writer

SCRIPT = (
    "the quote is- Stop explaining yourself to people who already decided to misunderstand you. "
    "and the video is- a person walking alone on a rainy street at night, neon reflections, slow motion"
)
QUOTE = "Stop explaining yourself to people who already decided to misunderstand you"
# Gemini's four variants, in the order it returned them.
ALONE = "Alone quotes for when people misunderstand you 🌧️ #shorts"
STOP = "Stop explaining yourself to people who refuse to listen 🚶‍♂️ #shorts"
WHEN = "When someone has already decided to misunderstand you 🌃 #shorts"
RAINY = "A rainy night walk for anyone tired of being misunderstood ☔ #shorts"
LIVE_DESCRIPTION = (
    "Alone quotes offer a quiet reflection for moments when people have already decided to misunderstand you. "
    "This video features a person walking alone on a rainy street at night, surrounded by neon reflections "
    "moving in slow motion, accompanied by the exact on-screen text: Stop explaining yourself…"
)
PRODUCTION_WORDS = ("this video features", "on-screen text", "slow motion", "accompanied by", "the video is",
                    "background is", "a lone person walks", "the video follows")


def _brief():
    return build_creator_brief(script=SCRIPT, video_format="youtube_shorts")


def _row(keyword, score, *, demand=False, platform=False):
    return {
        "keyword": keyword, "classification": "platform_format" if platform else "core_topic",
        "keyword_relevance_score": score, "source_support_score": 100,
        "source_support": "direct creator-source support",
        "source_classification": "creator_strategy" if platform else "combined",
        "demand_validated": demand,
    }


def _evidence(tag_score=95):
    # "alone quotes" is what viewers search, so it is the main search phrase.
    return {
        "selected_keywords": [_row("alone quotes", tag_score, demand=True), _row("misunderstood quotes", tag_score),
                              _row("yt", 0, platform=True), _row("shorts", 0, platform=True)],
        "subject_terms": ["alone", "misunderstood"],
        "search_demand": {"validated_keywords": ["alone quotes"]},
    }


def _package(*titles):
    return {
        "title": titles[0], "variants": list(titles),
        "description": f"“{QUOTE}.”\n\nWho are you still trying to convince?",
        "tags": ["alone quotes", "misunderstood quotes", "yt", "shorts"], "hashtags": ["#shorts"],
    }


class ShortTitleRankingTests(unittest.TestCase):
    def test_the_quote_outranks_the_keyword(self):
        fit = {title: short_title_fit(title, QUOTE, SCRIPT) for title in (ALONE, STOP, WHEN, RAINY)}
        self.assertGreater(fit[STOP], fit[ALONE])
        self.assertGreater(fit[WHEN], fit[ALONE])
        self.assertGreater(fit[STOP], fit[RAINY])
        # Deterministic: the same inputs always rank the same way.
        self.assertEqual(fit, {title: short_title_fit(title, QUOTE, SCRIPT) for title in fit})

    def test_keyword_quotes_constructions_and_scene_words_rank_lower(self):
        self.assertGreater(short_title_fit("Stop explaining yourself to people who misread you #shorts", QUOTE, SCRIPT),
                           short_title_fit("Misunderstood quotes for people who misread you #shorts", QUOTE, SCRIPT))
        self.assertGreater(short_title_fit("Stop explaining yourself to people who misread you #shorts", QUOTE, SCRIPT),
                           short_title_fit("Neon rainy street for people who misread you #shorts", QUOTE, SCRIPT))
        # A title cut short with an ellipsis is less clear than a whole one.
        self.assertGreater(short_title_fit("Stop explaining yourself to people who misread you #shorts", QUOTE, SCRIPT),
                           short_title_fit("Stop explaining yourself to people who already…  #shorts", QUOTE, SCRIPT))

    def test_a_title_about_something_else_never_outranks_a_faithful_one(self):
        quote, script = "I can't get enough of you", "the quote is- I can't get enough of you. the video is- a rainy night walk"
        faithful = short_title_fit("Can't get enough of you, even on the quiet nights #shorts", quote, script)
        for unfaithful in ("Why you should never text your ex again #shorts", "You deserve peace, not more pain #shorts"):
            with self.subTest(title=unfaithful):
                self.assertLessEqual(short_title_fit(unfaithful, quote, script), 30)
                self.assertGreater(faithful, short_title_fit(unfaithful, quote, script))

    def test_refinement_puts_the_quote_led_title_first(self):
        with patch("win_engine.generation.quality_refinement.gemini_client.is_available", return_value=False):
            refined, _ = refine_package(_package(ALONE, STOP, WHEN, RAINY), script=SCRIPT, brief=_brief(),
                                        language="english", region="global", evidence=_evidence(), competitors=[])
        self.assertIn(refined["title"], (STOP, WHEN))
        self.assertLess(refined["variants"].index(STOP), refined["variants"].index(ALONE))
        self.assertLess(refined["variants"].index(WHEN), refined["variants"].index(ALONE))

    def test_a_missing_search_phrase_does_not_cost_a_quote_short_its_title_score(self):
        brief = _brief()
        scores = {}
        for title in (STOP, ALONE):
            gate = evaluate_package_quality(_package(title), script=SCRIPT, creator_brief=brief,
                                            tag_evidence=_evidence())
            quality = gate["final_seo_quality"]
            scores[title] = quality["title_score"]
            notes = {item["code"]: item["severity"] for item in quality["warnings"]}
            if title == STOP:
                self.assertEqual(notes.get("primary_keyword_missing_from_title"), "info")
        self.assertGreaterEqual(scores[STOP], 90)


class ShortTitleGateTests(unittest.TestCase):
    def rejected(self, *titles):
        gate = evaluate_package_quality(_package(STOP, *titles), script=SCRIPT, creator_brief=_brief(),
                                        tag_evidence=_evidence())
        return {item["title"]: {issue["code"] for issue in item.get("issues") or []}
                for item in gate["rejected_candidates"]}

    def test_another_form_of_the_quotes_word_anchors_a_title(self):
        # "explanation" and "explaining", "misunderstood" and "misunderstand" are one word.
        rejected = self.rejected("You don't owe everyone an explanation #shorts",
                                 "Tired of being misunderstood on purpose? #shorts")
        for codes in rejected.values():
            self.assertNotIn("title_not_source_specific", codes)

    def test_a_modal_verb_is_not_a_topic_word_the_source_must_support(self):
        # A live title scored 88.8 because "should" counted as an unsupported word.
        title = "Why you should stop explaining yourself to everyone #shorts"
        gate = evaluate_package_quality(_package(title), script=SCRIPT, creator_brief=_brief(), tag_evidence=_evidence())
        self.assertGreaterEqual(gate["final_seo_quality"]["title_score"], 90)

    def test_a_title_ending_in_who_you_are_is_complete(self):
        self.assertEqual(title_fluency_issues("Some people already decided who you are #shorts"), [])
        # A copula after anything but a subject pronoun still reads as cut off.
        self.assertTrue(title_fluency_issues("Why this is"))
        self.assertTrue(title_fluency_issues("The reason people are"))
        self.assertTrue(title_fluency_issues("Stop explaining yourself to"))


class ShortDescriptionScoreTests(unittest.TestCase):
    def score(self, description):
        package = {**_package(STOP), "description": description}
        gate = evaluate_package_quality(package, script=SCRIPT, creator_brief=_brief(), tag_evidence=_evidence())
        return gate["final_seo_quality"]["description_score"]

    def test_the_quote_and_a_reflection_in_new_words_is_a_full_description(self):
        # The live description scored 83.5 for its reflective line.
        self.assertGreaterEqual(self.score(f"💭 {QUOTE}.\n\nSome minds are already made up.\n\n#shorts"), 90)
        self.assertGreaterEqual(self.score(f"“{QUOTE}.”\n\nWho are you still trying to convince? Save this for later."), 90)

    def test_without_the_quote_or_with_a_long_new_passage_it_is_scored_as_before(self):
        self.assertLess(self.score("Some minds are already made up. Protect your peace and walk away."), 90)
        essay = ("Some minds are already made up, and no speech, text, apology, argument, proof, "
                 "timeline, screenshot, witness, receipt, promise, or sacrifice will reopen them tonight.")
        self.assertLess(self.score(f"{QUOTE}.\n\n{essay}"), 90)


class ShortDescriptionTests(unittest.TestCase):
    def test_production_note_sentences_are_found_and_removed(self):
        self.assertEqual(len(production_note_sentences(LIVE_DESCRIPTION, QUOTE)), 1)
        cleaned = strip_production_notes(LIVE_DESCRIPTION, QUOTE)
        self.assertEqual(cleaned, "Alone quotes offer a quiet reflection for moments when people have already "
                                  "decided to misunderstand you.")
        for note in ("The background is a rainy street.", "The video is a slow walk.",
                     "Accompanied by soft piano.", "Shot in slow motion."):
            with self.subTest(note=note):
                self.assertEqual(strip_production_notes(f"{QUOTE}.\n\n{note}", QUOTE), f"{QUOTE}.")

    def test_a_subject_the_creator_named_is_not_a_production_note(self):
        text = "Lightning in slow motion, frame by frame."
        self.assertEqual(strip_production_notes(text, "slow motion lightning"), text)

    def test_the_writers_description_reaches_viewers_without_production_notes(self):
        brief = _brief()
        cleaned = seo_writer._sanitize_generated_package(
            {"title": STOP, "variants": [STOP], "description": LIVE_DESCRIPTION, "tags": [], "hashtags": []},
            SCRIPT, brief,
        )
        description = cleaned["description"]
        self.assertIn(f"“{QUOTE}”", description)
        for note in PRODUCTION_WORDS:
            with self.subTest(note=note):
                self.assertNotIn(note, description.casefold())
        self.assertLessEqual(len([line for line in description.splitlines() if line.strip()]), 3)

    def test_the_gate_flags_production_notes_in_a_short(self):
        brief = _brief()
        package = {**_package(STOP), "description": f"“{QUOTE}.”\n\n{LIVE_DESCRIPTION}"}
        gate = evaluate_package_quality(package, script=SCRIPT, creator_brief=brief, tag_evidence=_evidence())
        self.assertIn("production_notes", [item["code"] for item in gate["issues"]])
        clean = evaluate_package_quality(_package(STOP), script=SCRIPT, creator_brief=brief, tag_evidence=_evidence())
        self.assertNotIn("production_notes", [item["code"] for item in clean["issues"]])

    def test_the_local_fallback_keeps_the_whole_quote_and_only_a_feeling_emoji(self):
        # New contract: the fallback title is the whole quote, never cut and
        # never given #shorts; an emoji follows only for a feeling the quote
        # names ("miss"), never for the footage (green hills, rain).
        quote = "You can miss someone and still know you're better without them"
        script = f"YouTube Short, a man walking alone through green hills. On-screen quote: '{quote}.'"
        brief = build_creator_brief(script=script, video_format="youtube_shorts")
        self.assertEqual(brief["exact_quote"], quote)
        for title in (_content_specific_fallback("", [], brief)["title"], _safe_minimal_package("", brief)["title"]):
            with self.subTest(title=title):
                self.assertEqual(title, f"{quote} 🥀")
        short = build_creator_brief(script="YouTube Short, rain at night. On-screen quote: 'Some storms bring you home.'",
                                    video_format="youtube_shorts")
        self.assertEqual(_safe_minimal_package("", short)["title"], "Some storms bring you home")
        # The emoji goes first when it is all that stops the whole quote fitting.
        longer = "You can miss someone deeply and still know you're better off without them"
        brief = build_creator_brief(script=f"YouTube Short. On-screen quote: '{longer}.'", video_format="youtube_shorts")
        self.assertEqual(_content_specific_fallback("", [], brief)["title"], longer)

    def test_the_local_fallback_writes_no_production_notes(self):
        brief = build_creator_brief(script=SCRIPT, video_format="youtube_shorts",
                                    visual_requirements="A person walking alone on a rainy street at night, slow motion")
        for description in (_content_specific_fallback(brief["topic"], [], brief)["description"],
                            _safe_minimal_package(brief["topic"], brief)["description"]):
            with self.subTest(description=description):
                self.assertIn(f"“{QUOTE}”", description)
                for note in PRODUCTION_WORDS:
                    self.assertNotIn(note, description.casefold())
                self.assertFalse(production_note_sentences(description, QUOTE))

    def test_the_writer_asks_for_viewer_lines_not_production_notes(self):
        prompt = seo_writer._build_user_prompt(SCRIPT, "", "english", "global", "general", creator_brief=_brief())
        self.assertIn("1-3 short lines", prompt)
        self.assertIn("no production notes", prompt.casefold())
        self.assertNotIn("single-quote Short: 45-100 words", prompt)
        long_form = seo_writer._build_user_prompt(
            "How to set up OBS Studio for your first stream.", "", "english", "global", "general",
            creator_brief=build_creator_brief(script="How to set up OBS Studio for your first stream.",
                                              video_format="tutorial"),
        )
        self.assertNotIn("1-3 short lines", long_form)
        self.assertIn("120-220 words", long_form)

    def test_a_quote_shorts_search_phrases_do_not_lead_its_title(self):
        brief = {**_brief(), "search_demand_phrases": ["alone quotes"]}
        prompt = seo_writer._build_user_prompt(SCRIPT, "", "english", "global", "general", creator_brief=brief)
        self.assertIn("never build a '<phrase> quotes for", prompt)
        self.assertNotIn("in the title's first words", prompt)


class ShortTagTargetTests(unittest.TestCase):
    """support.google.com/youtube/answer/146402: tags play a minimal role in discovery."""

    GATE = {"verdict": "GREEN", "final_seo_quality": {
        "title_score": 95, "description_score": 92, "tag_score": 80.7, "verdict": "GREEN"}}

    def test_the_tag_score_does_not_decide_a_shorts_target(self):
        short = enforce_quality_target(self.GATE, short_form=True)
        self.assertTrue(short["quality_target"]["met"])
        self.assertEqual(short["verdict"], "GREEN")
        self.assertEqual(short["final_seo_quality"]["tag_score"], 80.7)  # still reported
        self.assertIn("tag_score", short["quality_target"]["not_counted"])
        long_form = enforce_quality_target(self.GATE)
        self.assertFalse(long_form["quality_target"]["met"])
        self.assertEqual(long_form["verdict"], "YELLOW")

    @patch("win_engine.generation.quality_refinement.generate_one", return_value=None)
    @patch("win_engine.generation.quality_refinement.gemini_client.provider_health", return_value={})
    @patch("win_engine.generation.quality_refinement.gemini_client.is_available", return_value=True)
    @patch("win_engine.generation.quality_refinement.evaluate_package_quality")
    def test_a_low_tag_score_does_not_ask_gemini_to_repair_a_short(self, evaluate, _available, _health, generate):
        evaluate.return_value = {"passed": True, "final_seo_quality": {
            "title_score": 95, "description_score": 92, "tag_score": 80.7}}
        package = {"title": STOP, "variants": [STOP], "description": QUOTE, "tags": ["yt", "shorts"], "hashtags": []}
        _, trace = refine_package(package, script=SCRIPT, brief=_brief(), language="english", region="global",
                                  evidence={}, competitors=[])
        generate.assert_not_called()
        self.assertFalse(trace["attempted"])
        long_form = {"video_format": "tutorial", "content": "How to set up OBS Studio."}
        refine_package({**package, "title": "Set up OBS Studio", "variants": []}, script="How to set up OBS Studio.",
                       brief=long_form, language="english", region="global", evidence={}, competitors=[])
        generate.assert_called_once()

    def test_weak_tags_are_reported_but_do_not_make_a_short_yellow(self):
        gate = evaluate_package_quality(_package(STOP, WHEN), script=SCRIPT, creator_brief=_brief(),
                                        tag_evidence=_evidence(tag_score=65))
        quality = gate["final_seo_quality"]
        self.assertEqual(quality["tag_score"], 65)
        notes = {item["code"]: item["severity"] for item in quality["warnings"]}
        self.assertEqual(notes.get("weak_tag_usefulness"), "info")
        self.assertEqual(gate["verdict"], "GREEN")


class ShortTitleAlternativeTests(unittest.TestCase):
    """A live quote Short kept 2 of the 5 titles the writer asked for.

    The writer's gate discarded the other three (echoes of the quote and the
    like), the package still passed, so no repair was asked for, and the
    refinement request neither asked for alternatives nor kept any of its own.
    """

    KEPT = ["Why you should stop explaining yourself #shorts", "Stop explaining yourself #shorts"]
    NEW = ["Tired of explaining yourself to closed minds? 🌃 #shorts",
           "Some people already decided to misunderstand you 🌧️ #shorts"]
    # The whole quote is an allowed title now; a copy cut with "…" is not.
    ECHO = "Stop explaining yourself to people who already... #shorts"
    DISCARDED = [{"title": ECHO, "codes": ["quote_title_cut"]}]

    def refine(self, repaired):
        with patch("win_engine.generation.quality_refinement.gemini_client.is_available", return_value=True), \
             patch("win_engine.generation.quality_refinement.gemini_client.provider_health", return_value={}), \
             patch("win_engine.generation.quality_refinement.generate_one", return_value=repaired) as generate:
            refined, trace = refine_package(_package(*self.KEPT), script=SCRIPT, brief=_brief(), language="english",
                                            region="global", evidence=_evidence(), competitors=[],
                                            rejected_titles=self.DISCARDED)
        return refined, trace, generate

    def test_the_writer_asks_a_quote_short_for_five_distinct_angles(self):
        prompt = seo_writer._build_user_prompt(SCRIPT, "", "english", "global", "general", creator_brief=_brief())
        for angle in ("the quote's punchline clause, or the whole quote", "its core line in new words",
                      "speaking to the viewer", "naming the feeling", "a question the viewer asks themselves",
                      "cuts the quote mid-phrase, ends in '...', stops before the quote's turn, reverses its meaning"):
            self.assertIn(angle, prompt)
        self.assertIn("return exactly five distinct variants", prompt)
        self.assertNotIn("Variant 1 is SEARCH", prompt)
        script = "How to set up OBS Studio for your first stream."
        long_form = seo_writer._build_user_prompt(script, "", "english", "global", "general",
                                                  creator_brief=build_creator_brief(script=script, video_format="tutorial"))
        self.assertIn("Variant 1 is SEARCH", long_form)
        self.assertNotIn("its core line in new words", long_form)

    def test_the_writer_records_the_titles_its_gate_discarded(self):
        reply = json.dumps({"title": self.KEPT[0], "variants": [*self.KEPT, self.ECHO],
                            "description": f"“{QUOTE}.”\n\nWho are you still trying to convince?",
                            "tags": ["alone quotes", "yt", "shorts"], "hashtags": ["#shorts"]})
        with patch.object(seo_writer.gemini_client, "is_available", return_value=True), \
             patch.object(seo_writer.gemini_client, "generate", return_value=reply) as generate, \
             patch.object(seo_writer.gemini_client, "last_generation_diagnostic",
                          return_value={"status": "gemini_success", "attempts": 1, "retries": 0}):
            packages, _ = seo_writer.write_multilang_packages_with_source(SCRIPT, languages=["english"],
                                                                          creator_brief=_brief())
        package = packages["english"]
        self.assertEqual(generate.call_count, 1)  # a passing package gets no repair here
        self.assertEqual([title.casefold() for title in package["variants"]], [title.casefold() for title in self.KEPT])
        rejected = package["generation_trace"]["rejected_titles"]
        self.assertEqual([item["title"] for item in rejected], [self.ECHO])
        self.assertIn("quote_title_cut", rejected[0]["codes"])

    def test_the_one_repair_asks_for_the_missing_alternatives_and_keeps_them(self):
        # The repair's own package fails (its description drops the quote), so
        # only its passing titles can reach the creator, beside the two kept.
        repaired = {"title": self.NEW[0], "variants": [*self.NEW, self.KEPT[1]],
                    "description": "Some minds are already made up.", "tags": [], "hashtags": []}
        refined, trace, generate = self.refine(repaired)
        self.assertEqual(generate.call_count, 1)
        feedback = " ".join(item["message"] for item in generate.call_args.kwargs["repair_feedback"])
        self.assertIn("Only 2 distinct title(s) passed", feedback)
        self.assertIn("speaking to the viewer", feedback)
        self.assertIn(self.ECHO, feedback)  # named so it is not returned again
        self.assertTrue(trace["attempted"])
        self.assertEqual(trace["alternatives_added"], 2)
        self.assertEqual(set(refined["variants"]), {*self.KEPT, *self.NEW})
        self.assertEqual(refined["title"], refined["variants"][0])
        self.assertEqual(refined["description"], _package(*self.KEPT)["description"])
        gate = evaluate_package_quality(refined, script=SCRIPT, creator_brief=_brief(), tag_evidence=_evidence())
        self.assertEqual(len(gate["accepted_candidates"]), 4)
        self.assertNotIn("fewer_legitimate_alternatives", [item["code"] for item in gate["warnings"]])

    def test_a_keyword_quotes_title_from_the_repair_never_leads(self):
        repaired = {"title": ALONE, "variants": [ALONE, *self.NEW],
                    "description": "Some minds are already made up.", "tags": [], "hashtags": []}
        refined, _, _ = self.refine(repaired)
        self.assertGreaterEqual(len(refined["variants"]), 3)
        self.assertNotEqual(refined["title"], ALONE)
        if ALONE in refined["variants"]:
            self.assertEqual(refined["variants"][-1], ALONE)

    def test_a_repair_with_nothing_new_is_not_padded(self):
        repaired = {"title": self.ECHO, "variants": [self.ECHO, *self.KEPT],
                    "description": "Some minds are already made up.", "tags": [], "hashtags": []}
        refined, trace, generate = self.refine(repaired)
        self.assertEqual(generate.call_count, 1)
        self.assertEqual(set(refined["variants"]), set(self.KEPT))
        self.assertNotIn("alternatives_added", trace)

    def test_three_passing_titles_need_no_request(self):
        package = _package(STOP, WHEN, RAINY)
        with patch("win_engine.generation.quality_refinement.gemini_client.is_available", return_value=True), \
             patch("win_engine.generation.quality_refinement.gemini_client.provider_health", return_value={}), \
             patch("win_engine.generation.quality_refinement.generate_one", return_value=None) as generate:
            gate = evaluate_package_quality(package, script=SCRIPT, creator_brief=_brief(), tag_evidence=_evidence())
            self.assertGreaterEqual(len(gate["accepted_candidates"]), 3)
            _, trace = refine_package(package, script=SCRIPT, brief=_brief(), language="english", region="global",
                                      evidence=_evidence(), competitors=[])
        generate.assert_not_called()
        self.assertFalse(trace["attempted"])


if __name__ == "__main__":
    unittest.main()
