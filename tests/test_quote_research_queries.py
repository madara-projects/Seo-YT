"""A quote Short's research comes from the quote's meaning, never from the footage behind it.

A live run searched "solitary walker", the brief's visual requirement, and
"alone" reached the tags and hashtags although the quote says nothing about
being alone. The footage stays presentation context: it is labelled as such
for the semantic model, it grounds no topic of a quote, and the planner never
spends a search on it.
"""

import json
import unittest
from unittest.mock import patch

from win_engine.analysis.creator_brief import build_creator_brief
from win_engine.analysis.research_planner import _visual_only_query, plan_research_queries
from win_engine.analysis.semantic_research import analyze_script_semantics

QUOTE = "Stop explaining yourself to people who already decided to misunderstand you"
VISUAL = "a solitary walker alone on a rainy street at night, neon reflections, slow motion"
# The Creator page's script carries the footage note beside the quote.
SCRIPT = f"the quote is- {QUOTE}. and the video is- {VISUAL}"


def _brief():
    return build_creator_brief(script=SCRIPT, video_format="youtube_shorts", visual_requirements=VISUAL)


class PlannerTests(unittest.TestCase):
    def test_a_query_made_of_footage_words_is_rejected_for_a_quote(self):
        brief = _brief()
        for query in ("solitary walker", "alone quotes", "walking alone at night", "rainy night quotes",
                      "quotes about a solitary walker"):
            with self.subTest(query=query):
                self.assertTrue(_visual_only_query(query, SCRIPT, brief))
        for query in ("misunderstood quotes", "quotes about being misunderstood", "stop explaining yourself",
                      "people who misunderstand you"):
            with self.subTest(query=query):
                self.assertFalse(_visual_only_query(query, SCRIPT, brief))

    def test_a_quote_word_in_another_form_is_still_the_quotes(self):
        # "walk" in the quote is "walking" in the footage; compared word for
        # word, every query about walking away was the footage's.
        quote = "Walk away from people who drain your energy"
        visual = "a man walking away on an empty beach"
        script = f"the quote is- {quote}. and the video is- {visual}"
        brief = build_creator_brief(script=script, video_format="youtube_shorts", visual_requirements=visual)
        for query in ("walking away quotes", "walking away from draining people", "drained energy quotes"):
            with self.subTest(query=query):
                self.assertFalse(_visual_only_query(query, script, brief))
        for query in ("empty beach", "man walking on beach"):
            with self.subTest(query=query):
                self.assertTrue(_visual_only_query(query, script, brief))

    def test_a_long_form_video_about_its_scenery_keeps_the_old_rule(self):
        brief = {"content": "A walking tour through the old town's rainy streets at night.",
                 "visual_requirements": "rainy streets at night", "video_format": "vlog"}
        self.assertFalse(_visual_only_query("rainy streets at night walking tour", brief["content"], brief))

    def test_the_plan_never_searches_the_footage(self):
        semantic = {
            "primary_topic": "solitary walker",
            "secondary_topics": ["being misunderstood", "walking alone at night"],
            "search_intents": ["alone quotes"],
            "keyword_clusters": [{"cluster": "scene", "candidates": ["rainy night walk"]}],
            "entities": [], "viewer_intent": "emotional_relatable",
            "concept_evidence_validated": True, "concept_evidence": [],
        }
        queries = [item["query"] for item in plan_research_queries(
            script=SCRIPT, creator_brief=_brief(), semantic_analysis=semantic, region="india", max_queries=5,
        )]
        joined = " | ".join(queries).casefold()
        for word in ("solitary", "walker", "alone", "rainy", "night", "walk"):
            self.assertNotIn(word, joined, queries)
        self.assertIn("being misunderstood", queries)
        # The regional variant builds on a topic from the quote, not on the footage.
        self.assertTrue(all("india" not in query.casefold() or "misunderstand" in query.casefold() for query in queries), queries)


@patch("win_engine.analysis.semantic_research.gemini_client.is_available", return_value=True)
@patch("win_engine.analysis.semantic_research.gemini_client.generate")
class SemanticTests(unittest.TestCase):
    REPLY = {
        "primary_topic": "solitary walker",
        "secondary_topics": ["being misunderstood", "rainy night walk"],
        "entities": [], "audience": [], "search_intents": ["alone quotes"], "keyword_clusters": [],
        "viewer_intent": "emotional_relatable",
        "concept_evidence": [
            {"concept": "solitary walker", "source_phrase": "solitary walker", "relationship": "direct"},
            {"concept": "being misunderstood", "source_phrase": "decided to misunderstand you",
             "relationship": "paraphrase"},
        ],
    }

    def test_footage_words_ground_no_topic_of_a_quote(self, generate, _available):
        generate.return_value = json.dumps(self.REPLY)
        semantic = analyze_script_semantics(SCRIPT, _brief())
        self.assertEqual(semantic["primary_topic"], "being misunderstood")
        self.assertNotIn("rainy night walk", semantic["secondary_topics"])
        self.assertEqual(semantic["search_intents"], [])
        # The footage concept stays on record as context, so the planner can recognise it.
        scopes = {item["concept"]: item["source_scope"] for item in semantic["concept_evidence"]}
        self.assertEqual(scopes, {"solitary walker": "visual", "being misunderstood": "content"})

    def test_the_model_reads_the_quote_as_the_source_and_the_footage_as_context(self, generate, _available):
        generate.return_value = json.dumps(self.REPLY)
        analyze_script_semantics(SCRIPT, _brief())
        prompt = generate.call_args_list[0].kwargs["prompt"]
        source = prompt.split("Creator source:", 1)[1]
        self.assertIn(QUOTE, source)
        self.assertIn("Visual context", source)
        self.assertLess(source.index(QUOTE), source.index("Visual context"))
        self.assertNotIn("solitary walker", source.split("Visual context", 1)[0])

    def test_a_video_without_a_quote_keeps_its_scenery_as_a_topic(self, generate, _available):
        script = "A walking tour through the old town's rainy streets at night."
        generate.return_value = json.dumps({
            "primary_topic": "rainy night walking tour", "secondary_topics": [], "entities": [], "audience": [],
            "search_intents": [], "keyword_clusters": [], "viewer_intent": "story_experience",
            "concept_evidence": [{"concept": "rainy night walking tour", "source_phrase": "rainy streets at night",
                                  "relationship": "paraphrase"}],
        })
        semantic = analyze_script_semantics(script, {"content": script, "visual_requirements": "rainy streets at night"})
        self.assertEqual(semantic["primary_topic"], "rainy night walking tour")


# A long-form script that opens with a quote it then teaches from: the brief
# infers the quote, but the video is about the whole script.
TALK = ('Today\'s quote: "Discipline is choosing what you want most over what you want now." '
        "Here are three habits that make it easier: the two minute rule, a morning planning ritual, and tracking streaks.")
DESK = "me at my desk planning my morning"


def _talk_brief():
    return build_creator_brief(script=TALK, video_format="talking_head", visual_requirements=DESK)


@patch("win_engine.analysis.semantic_research.gemini_client.is_available", return_value=True)
@patch("win_engine.analysis.semantic_research.gemini_client.generate")
class LongFormQuoteTests(unittest.TestCase):
    REPLY = {
        "primary_topic": "discipline habits",
        "secondary_topics": ["two minute rule", "morning planning ritual", "tracking streaks"],
        "entities": [], "audience": [], "search_intents": [], "keyword_clusters": [],
        "viewer_intent": "problem_solving", "concept_evidence": [],
    }

    def test_the_model_reads_the_whole_script_of_a_long_form_video(self, generate, _available):
        generate.return_value = json.dumps(self.REPLY)
        brief = _talk_brief()
        self.assertEqual(brief["field_provenance"]["exact_quote"]["source"], "inferred")
        semantic = analyze_script_semantics(TALK, brief)
        source = generate.call_args_list[0].kwargs["prompt"].split("Creator source:", 1)[1]
        self.assertIn("morning planning ritual", source)
        self.assertIn("Visual context", source)
        self.assertEqual(semantic["secondary_topics"], self.REPLY["secondary_topics"])
        self.assertEqual(semantic["viewer_intent"], "problem_solving")

    def test_a_script_topic_the_footage_also_names_is_searched(self, _generate, _available):
        self.assertFalse(_visual_only_query("morning planning ritual", TALK, _talk_brief()))

    def test_a_long_form_plan_with_a_quote_in_it_is_not_planned_as_a_quote_video(self, _generate, _available):
        semantic = {
            "primary_topic": "discipline", "secondary_topics": ["how to build discipline", "morning planning ritual"],
            "search_intents": [], "related_concepts": [], "entities": [], "viewer_intent": "problem_solving",
        }
        queries = [item["query"] for item in plan_research_queries(
            script=TALK, creator_brief=_talk_brief(), semantic_analysis=semantic, max_queries=5,
        )]
        self.assertTrue(queries)
        # A talking head is searched for its subject, not as a quote video.
        self.assertFalse(any("quotes" in query for query in queries), queries)
        self.assertIn("how to build discipline", queries)

    def test_a_supplied_quote_is_the_content_unless_the_creator_chose_long_form(self, generate, _available):
        generate.return_value = json.dumps(self.REPLY)
        quote = "Discipline is choosing what you want most over what you want now"
        for video_format, whole_script in (("talking_head", True), ("", False)):
            with self.subTest(video_format=video_format):
                generate.reset_mock()
                brief = build_creator_brief(script=TALK, video_format=video_format, visual_requirements=DESK,
                                            exact_quote=quote)
                analyze_script_semantics(TALK, brief)
                source = generate.call_args_list[0].kwargs["prompt"].split("Creator source:", 1)[1]
                self.assertIn(quote, source)
                self.assertEqual("morning planning ritual" in source, whole_script)


if __name__ == "__main__":
    unittest.main()
