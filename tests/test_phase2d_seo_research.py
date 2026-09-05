from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from win_engine.analysis.keyword_research import build_keyword_research, select_final_tags
from win_engine.analysis.research_planner import plan_research_queries
from win_engine.analysis.semantic_research import analyze_script_semantics
from win_engine.analysis.search_opportunities import discover_search_opportunities
from win_engine.analysis.research_insights import build_research_decision
from win_engine.ingestion.research_service import ResearchService


class Phase2DKeywordResearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.quote = "In the end, I wasn't abandoned. I was erased."
        self.script = (
            "A reflective YouTube Short about emotional distance and feeling forgotten. "
            "The on-screen quote is: " + self.quote
        )
        self.semantic = {
            "primary_topic": "emotional distance",
            "secondary_topics": ["feeling forgotten", "emotional absence"],
            "entities": [],
            "audience": ["viewers processing emotional distance"],
            "search_intents": ["how to cope with feeling forgotten"],
            "keyword_clusters": [{"cluster": "emotional reflection", "candidates": ["emotional healing quotes", "feeling unseen"]}],
            "source": "gemini",
        }
        self.results = [
            {"title": "Feeling unseen and emotionally distant", "description": "A reflection on emotional distance and healing."},
            {"title": "How to cope with feeling forgotten", "description": "Emotional healing and self worth."},
            {"title": "Emotional distance in relationships", "description": "Feeling unseen and emotional absence."},
        ]

    def test_query_plan_uses_semantic_topic_not_exact_quote(self):
        queries = plan_research_queries(
            script=self.script,
            creator_brief={"content": self.script, "video_format": "youtube_shorts"},
            semantic_analysis=self.semantic,
        )
        text = " ".join(item["query"] for item in queries).casefold()
        self.assertIn("emotional distance", text)
        self.assertNotIn("wasn't abandoned", text)

    def test_quote_marker_brief_uses_natural_concept_queries(self):
        queries = plan_research_queries(
            script="You don't give up overnight on someone.",
            creator_brief={
                "content": "You don't give up overnight on someone.",
                "exact_quote": "You don't give up overnight on someone. Your heart quietly says enough.",
                "topic": "you don't give up overnight on someone",
                "video_format": "youtube_shorts",
            },
            semantic_analysis={"primary_topic": "don't give overnight someone reach"},
        )
        text = " | ".join(item["query"] for item in queries).casefold()
        self.assertIn("knowing when to let go", text)
        self.assertIn("emotional exhaustion", text)
        self.assertNotIn("don't give overnight someone reach", text)

    @patch("win_engine.analysis.semantic_research.gemini_client.is_available", return_value=False)
    def test_rarity_quote_gets_natural_semantic_profile_and_queries(self, _available):
        quote = "You deserve somebody who knows how hard it is to find somebody like you"
        brief = {
            "content": quote,
            "exact_quote": quote,
            "video_format": "youtube_shorts",
            "creator_intent": "A reflection about recognizing a person's rarity and worth.",
        }
        semantic = analyze_script_semantics(quote, brief)
        self.assertEqual(semantic["primary_topic"], "recognizing your worth")
        self.assertIn("being valued for who you are", semantic["secondary_topics"])
        self.assertIn("know your worth", semantic["keyword_clusters"][0]["candidates"])
        queries = plan_research_queries(script=quote, creator_brief=brief, semantic_analysis=semantic)
        query_text = " | ".join(item["query"] for item in queries)
        self.assertIn("knowing your worth quotes", query_text)
        self.assertIn("being valued for who you are", query_text)
        self.assertNotIn("deserve somebody knows hard find", query_text)

    def test_rarity_quote_semantic_tags_survive_without_copying_quote(self):
        quote = "You deserve somebody who knows how hard it is to find somebody like you"
        brief = {
            "exact_quote": quote,
            "creator_intent": "A reflection about recognizing a person's rarity and worth.",
            "field_provenance": {"creator_intent": {"source": "creator_supplied"}},
        }
        research = build_keyword_research(
            script=quote,
            semantic={
                "primary_topic": "recognizing your worth",
                "secondary_topics": ["being valued for who you are", "genuine appreciation"],
                "search_intents": ["knowing your worth quotes"],
                "keyword_clusters": [{"cluster": "personal worth", "candidates": ["know your worth", "being valued", "hard to replace"]}],
                "source": "local_profile",
            },
            youtube_results=[
                {"title": "Know your worth", "description": "Being valued for who you are"},
                {"title": "Hard to replace quotes", "description": "Genuine appreciation"},
            ],
            research_queries=[{"type": "primary", "query": "knowing your worth quotes"}],
            entity_signals=[], creator_brief=brief,
        )
        tags, _ = select_final_tags(
            research, generated_tags=["know your worth", "being valued", "hard to replace", quote],
            title="You're Rarer Than You Realize ✨ #shorts", script=quote, creator_brief=brief,
        )
        self.assertGreaterEqual(len(tags), 3)
        self.assertIn("know your worth", tags)
        self.assertTrue(any(tag.startswith("being valued") for tag in tags))
        self.assertNotIn(quote.casefold(), tags)

    def test_irrelevant_youtube_results_are_removed_before_scoring(self):
        rows = [
            {"title": "It's Just A Prank", "description": "Comedy", "research_query": "emotional exhaustion"},
            {"title": "Obsession Spell", "description": "Manifestation", "research_query": "knowing when to let go"},
            {"title": "How Emotional Exhaustion Feels", "description": "Knowing when to let go", "research_query": "emotional exhaustion"},
        ]
        filtered = ResearchService._filter_relevant_results(rows)
        self.assertEqual([row["title"] for row in filtered], ["How Emotional Exhaustion Feels"])

    def test_short_research_rejects_long_form_and_generic_quote_matches(self):
        rows = [
            {"title": "Quiet Solitude Ambient Mix", "description": "silence", "duration": "PT1H6S", "research_query": "solitude silence inner thoughts"},
            {"title": "Sad anime quote edit", "description": "quotes shorts", "duration": "PT25S", "research_query": "reflective shorts solitude quotes lonely walking"},
            {"title": "Walking Alone on an Empty Road", "description": "quiet thoughts and solitude", "duration": "PT12S", "research_query": "quiet streets walking solitude inner thoughts"},
        ]
        filtered = ResearchService._filter_relevant_results(rows, {"video_format": "youtube_shorts"})
        self.assertEqual([row["title"] for row in filtered], ["Walking Alone on an Empty Road"])
        self.assertGreaterEqual(filtered[0]["research_relevance_score"], 60)

    def test_research_confidence_uses_relevance_not_only_result_count(self):
        weak = [{"title": f"Result {index}", "research_relevance_score": 20} for index in range(10)]
        decision = build_research_decision({"exact_quote": "Silence knows everything."}, weak)
        self.assertEqual(decision["confidence"], "low")
        self.assertEqual(decision["average_relevance_score"], 20.0)

    def test_explicit_visual_concept_can_survive_with_research_support(self):
        brief = {
            "exact_quote": "Silence knows everything.",
            "visual_requirements": "One person walking alone in quiet streets.",
            "creator_intent": "A reflective Short about solitude and private thoughts.",
            "field_provenance": {"creator_intent": {"source": "creator_supplied"}},
        }
        research = build_keyword_research(
            script="Silence knows everything.",
            semantic={"primary_topic": "inner silence", "secondary_topics": ["inner thoughts", "solitude"], "search_intents": [], "keyword_clusters": [], "source": "gemini"},
            youtube_results=[{"title": "Walking alone on quiet streets", "description": "solitude and inner thoughts"}],
            research_queries=[{"type": "visual", "query": "walking alone quiet streets"}],
            entity_signals=[],
            creator_brief=brief,
        )
        tags, _ = select_final_tags(
            research, generated_tags=["inner silence", "inner thoughts", "solitude", "walking alone"],
            title="Some Things Only Silence Knows 🌙 #shorts", script="Silence knows everything.",
            creator_brief=brief, is_short=True,
        )
        self.assertIn("walking alone", tags)
        self.assertGreaterEqual(len(tags), 3)

    def test_search_instruction_and_invented_action_tags_are_rejected(self):
        brief = {
            "exact_quote": "Silence knows everything.",
            "creator_intent": "A reflective Short about solitude and private thoughts.",
            "field_provenance": {"creator_intent": {"source": "creator_supplied"}},
        }
        research = build_keyword_research(
            script="Silence knows everything.",
            semantic={
                "primary_topic": "solitude", "secondary_topics": ["private thoughts"],
                "search_intents": ["discover content about solitude"],
                "keyword_clusters": [{"cluster": "solitude", "candidates": ["embracing solitude"]}],
                "source": "gemini",
            },
            youtube_results=[{"title": "Solitude and private thoughts", "description": "silence"}],
            research_queries=[{"type": "topic", "query": "solitude silence private thoughts"}],
            entity_signals=[], creator_brief=brief,
        )
        tags, evidence = select_final_tags(
            research, generated_tags=["discover content about solitude", "embracing solitude", "private thoughts"],
            title="When It's Only Me and the Silence #shorts", script="Silence knows everything.", creator_brief=brief,
        )
        self.assertNotIn("discover content about solitude", tags)
        self.assertNotIn("embracing solitude", tags)
        self.assertIn("private thoughts", tags)
        reasons = {item["reason"] for item in evidence["rejected_candidates"]}
        self.assertIn("unsupported_action_framing", reasons)

    def test_final_tags_reject_title_and_quote_copies_and_keep_youtube_evidence(self):
        research = build_keyword_research(
            script=self.script,
            semantic=self.semantic,
            youtube_results=self.results,
            research_queries=[{"type": "topic", "query": "emotional distance"}],
            entity_signals=[],
            creator_brief={"exact_quote": self.quote},
        )
        tags, evidence = select_final_tags(
            research,
            generated_tags=[self.quote, "emotional distance", "feeling forgotten", "viral shorts"],
            title="In the end, I wasn't abandoned. I was erased. #shorts",
            script=self.script,
            creator_brief={"exact_quote": self.quote},
            is_short=True,
        )
        self.assertNotIn("shorts", tags)
        self.assertNotIn("in the end i wasn't abandoned i was erased", tags)
        self.assertTrue(any(tag in {"emotional distance", "feeling forgotten", "emotional healing quotes", "feeling unseen"} for tag in tags))
        self.assertEqual(len(tags), len(set(tags)))
        self.assertEqual(evidence["status"], "youtube_evidence")
        self.assertTrue(all(item["classification"] not in {"generic", "malformed"} for item in evidence["selected_keywords"]))

    def test_generic_and_near_duplicate_candidates_are_filtered(self):
        research = build_keyword_research(
            script="A Python tutorial showing CSV parsing and data validation.",
            semantic={
                "primary_topic": "python csv parsing",
                "secondary_topics": ["data validation"],
                "search_intents": ["how to parse csv files in python"],
                "keyword_clusters": [{"cluster": "python data", "candidates": ["python csv parsing tutorial", "csv parsing python"]}],
            },
            youtube_results=[
                {"title": "Python CSV parsing tutorial", "description": "Validate CSV data in Python."},
                {"title": "How to parse CSV files in Python", "description": "Python data validation tutorial."},
            ],
            research_queries=[{"type": "topic", "query": "python csv parsing"}],
            entity_signals=[],
        )
        tags, _ = select_final_tags(
            research,
            generated_tags=["python csv parsing", "csv parsing python", "youtube", "viral"],
            title="How to Parse CSV Files Safely in Python",
            script="A Python tutorial showing CSV parsing and data validation.",
        )
        self.assertNotIn("youtube", tags)
        self.assertNotIn("viral", tags)
        self.assertLessEqual(sum("csv parsing" in tag for tag in tags), 1)

    def test_unrelated_repeated_result_phrase_cannot_outrank_the_semantic_topic(self):
        research = build_keyword_research(
            script="A reflective quote Short about emotional absence and feeling forgotten.",
            semantic={
                "primary_topic": "emotional absence and feeling forgotten",
                "secondary_topics": ["emotional distance"],
                "search_intents": ["relatable emotional quotes"],
                "keyword_clusters": [],
                "source": "gemini",
            },
            youtube_results=[
                {"title": "Best friend is really there", "description": "best friend is really there"},
                {"title": "Best friend is really there", "description": "best friend is really there"},
            ],
            research_queries=[{"query": "emotional absence feeling forgotten"}],
            entity_signals=[],
            creator_brief={"exact_quote": "I was erased."},
        )
        keywords = [item["keyword"] for item in research["candidates"]]
        self.assertNotIn("best friend is", keywords)
        self.assertIn("emotional absence", keywords)
        self.assertIn("feeling forgotten", keywords)

    def test_broad_mood_words_do_not_admit_competitor_spam_as_tags(self):
        research = build_keyword_research(
            script="A quote Short about loneliness and heartbreak.",
            semantic={
                "primary_topic": "emotional reflection loneliness heartbreak pain relationships",
                "secondary_topics": ["feeling forgotten"],
                "search_intents": ["watching aesthetic emotional mood"],
                "keyword_clusters": [],
                "source": "gemini",
            },
            youtube_results=[
                {"title": "Best friend aesthetic reality", "description": "WhatsApp sad status aesthetic"},
                {"title": "Best friend aesthetic reality", "description": "WhatsApp sad status aesthetic"},
            ],
            research_queries=[{"query": "emotional reflection loneliness heartbreak"}],
            entity_signals=[],
            creator_brief={"exact_quote": "I was erased."},
        )
        keywords = [item["keyword"] for item in research["candidates"]]
        self.assertNotIn("best friend aesthetic", keywords)
        self.assertFalse(any("status" in keyword or "aesthetic" in keyword for keyword in keywords))

    def test_golden_run_42_quality_properties(self):
        quote = "In the end, I wasn't abandoned. I was erased."
        research = build_keyword_research(
            script="A reflective quote Short about feeling forgotten and emotional rejection.",
            semantic={
                "primary_topic": "emotional reflection heartbreak loneliness personal rejection",
                "secondary_topics": ["feeling forgotten", "emotional absence"],
                "search_intents": ["coping with feeling forgotten"],
                "keyword_clusters": [{"cluster": "emotional loss", "candidates": ["being forgotten by someone", "heartbreak sayings", "moody sunset footage"]}],
                "source": "gemini",
            },
            youtube_results=[
                {"title": "Best friend aesthetic reality", "description": "WhatsApp sad status aesthetic"},
                {"title": "Best friend aesthetic reality", "description": "WhatsApp sad status aesthetic"},
                {"title": "Coping with feeling forgotten", "description": "A reflection on emotional rejection."},
            ],
            research_queries=[{"query": "emotional rejection feeling forgotten"}],
            entity_signals=[],
            creator_brief={"exact_quote": quote, "visual_requirements": "Evening road traffic under cloudy sky."},
        )
        tags, evidence = select_final_tags(
            research,
            generated_tags=["when you weren't abandoned just erased", "moody sunset footage", "heartbreak loneliness emotional rejection healing"],
            title="When you weren't abandoned, just erased #shorts",
            script="A reflective quote Short about feeling forgotten and emotional rejection.",
            creator_brief={"exact_quote": quote, "visual_requirements": "Evening road traffic under cloudy sky."},
        )
        forbidden = {"emotional reflection heartbreak loneliness personal rejection", "best friend aesthetic", "whatsapp sad status", "when you weren't abandoned just erased", "moody sunset footage", "shorts"}
        self.assertFalse(set(tags) & forbidden)
        self.assertTrue(any(term in " ".join(tags) for term in ("forgotten", "rejection", "heartbreak", "loneliness")))
        self.assertTrue(all(len(tag.split()) <= 7 and len(tag) <= 80 for tag in tags))
        self.assertEqual(len(tags), len(set(tags)))
        self.assertTrue(all(item["diversity_score"] is not None for item in evidence["selected_keywords"]))

    def test_quote_heavy_script_does_not_turn_quote_lines_into_tags(self):
        quote = "I wasn't abandoned. I was erased."
        research = build_keyword_research(
            script=f"Quote Short: {quote}",
            semantic={"primary_topic": "feeling forgotten", "secondary_topics": ["emotional absence"], "search_intents": [], "keyword_clusters": []},
            youtube_results=[], research_queries=[], entity_signals=[], creator_brief={"exact_quote": quote},
        )
        tags, _ = select_final_tags(research, generated_tags=["i wasn't abandoned", "i was erased", "feeling forgotten"], title="A quiet emotional quote #shorts", script=quote, creator_brief={"exact_quote": quote})
        self.assertNotIn("i wasn't abandoned", tags)
        self.assertNotIn("i was erased", tags)
        self.assertIn("feeling forgotten", tags)

    def test_short_quote_fragment_is_rejected_even_when_it_has_one_content_word(self):
        quote = "I wasn't abandoned. I was erased."
        research = build_keyword_research(
            script=f"A quote Short: {quote}",
            semantic={"primary_topic": "loneliness", "secondary_topics": [], "search_intents": [], "keyword_clusters": []},
            youtube_results=[], research_queries=[], entity_signals=[], creator_brief={"exact_quote": quote},
        )
        tags, _ = select_final_tags(research, generated_tags=["i was erased"], title="A loneliness quote #shorts", script=quote, creator_brief={"exact_quote": quote})
        self.assertNotIn("i was erased", tags)

    def test_concatenated_gemini_candidate_is_decomposed_not_selected_as_one_tag(self):
        research = build_keyword_research(
            script="A Short about heartbreak, loneliness, and personal rejection.",
            semantic={"primary_topic": "heartbreak loneliness emotional rejection healing", "secondary_topics": [], "search_intents": [], "keyword_clusters": []},
            youtube_results=[], research_queries=[], entity_signals=[], creator_brief={},
        )
        keywords = [item["keyword"] for item in research["candidates"]]
        self.assertNotIn("heartbreak loneliness emotional rejection healing", keywords)
        self.assertTrue({"heartbreak", "loneliness", "rejection"} & set(keywords))

    def test_comparison_phrase_is_not_broken_at_its_essential_and(self):
        research = build_keyword_research(
            script="A comparison of manual and burr coffee grinders for apartment kitchens.",
            semantic={"primary_topic": "manual and burr coffee grinders", "secondary_topics": [], "search_intents": [], "keyword_clusters": []},
            youtube_results=[], research_queries=[], entity_signals=[], creator_brief={},
        )
        keywords = [item["keyword"] for item in research["candidates"]]
        self.assertIn("manual and burr coffee grinders", keywords)
        self.assertNotIn("compare manual", keywords)

    def test_sparse_research_remains_honest_without_fabricating_specific_terms(self):
        research = build_keyword_research(
            script="A broad reflection about starting over.",
            semantic={"primary_topic": "starting over", "secondary_topics": [], "search_intents": [], "keyword_clusters": [], "source": "local_fallback"},
            youtube_results=[], research_queries=[], entity_signals=[], creator_brief={},
        )
        tags, evidence = select_final_tags(research, generated_tags=["viral shorts", "starting over"], title="Starting over #shorts", script="A broad reflection about starting over.")
        self.assertEqual(research["status"], "semantic_only")
        self.assertNotIn("viral shorts", tags)
        self.assertTrue(all(item["research_evidence_score"] == 0 for item in evidence["selected_keywords"]))

    def test_semantic_cluster_is_not_its_own_relevance_proof(self):
        research = build_keyword_research(
            script="A reflective quote about feeling forgotten.",
            semantic={
                "primary_topic": "feeling forgotten",
                "secondary_topics": [],
                "search_intents": [],
                "keyword_clusters": [{"cluster": "unverified", "candidates": ["being left behind"]}],
            },
            youtube_results=[], research_queries=[], entity_signals=[], creator_brief={},
        )
        self.assertNotIn("being left behind", [item["keyword"] for item in research["candidates"]])

    def test_specific_long_tail_can_survive_and_visual_only_terms_do_not_outrank_content(self):
        research = build_keyword_research(
            script="A guide to cope with emotional burnout at work, filmed on a rainy road.",
            semantic={
                "primary_topic": "emotional burnout at work",
                "secondary_topics": [],
                "search_intents": ["how to cope with emotional burnout at work"],
                "keyword_clusters": [{"cluster": "visual", "candidates": ["rainy road footage"]}],
            },
            youtube_results=[], research_queries=[], entity_signals=[],
            creator_brief={"visual_requirements": "rainy road footage"},
        )
        tags, _ = select_final_tags(research, generated_tags=[], title="How to cope with burnout at work", script="A guide to cope with emotional burnout at work.", creator_brief={"visual_requirements": "rainy road footage"})
        self.assertIn("how to cope with emotional burnout at work", tags)
        self.assertNotIn("rainy road footage", tags)

    @patch("win_engine.analysis.semantic_research.gemini_client.is_available", return_value=False)
    def test_semantic_failure_uses_marked_local_fallback(self, _available):
        result = analyze_script_semantics("A tutorial on repairing a bicycle chain.")
        self.assertEqual(result["source"], "local_fallback")
        self.assertTrue(result["primary_topic"])

    @patch("win_engine.analysis.semantic_research.gemini_client.generate")
    @patch("win_engine.analysis.semantic_research.gemini_client.is_available", return_value=True)
    def test_unseen_metaphors_keep_only_source_anchored_meanings_and_generate_tags(self, _available, generate):
        cases = [
            (
                "Be grateful that you slipped through the hands of people who had no idea how to hold you",
                ["knowing your worth", "being valued", "moving on with gratitude"],
                "slipped through the hands",
            ),
            (
                "Some doors closing are protection you cannot see yet",
                ["hidden protection", "new beginnings", "accepting closed paths"],
                "doors closing are protection",
            ),
            (
                "You cannot pour from an empty cup",
                ["rest and self care", "protecting your energy", "personal boundaries"],
                "pour from an empty cup",
            ),
        ]
        for quote, concepts, anchor in cases:
            with self.subTest(quote=quote):
                generate.return_value = json.dumps({
                    "primary_topic": concepts[0],
                    "secondary_topics": concepts[1:],
                    "entities": [],
                    "audience": [],
                    "search_intents": concepts,
                    "keyword_clusters": [{"cluster": "meaning", "candidates": concepts}],
                    "viewer_intent": "emotional_relatable",
                    "concept_evidence": [
                        {"concept": concept, "source_phrase": anchor, "relationship": "metaphor"}
                        for concept in concepts
                    ],
                })
                semantic = analyze_script_semantics(quote, {"exact_quote": quote})
                self.assertTrue(semantic["concept_evidence_validated"])
                self.assertEqual(semantic["primary_topic"], concepts[0])
                research = build_keyword_research(
                    script=quote, semantic=semantic, youtube_results=[], research_queries=[],
                    entity_signals=[], creator_brief={"exact_quote": quote},
                )
                tags, evidence = select_final_tags(
                    research, generated_tags=concepts, title=concepts[0].title(),
                    script=quote, creator_brief={"exact_quote": quote},
                )
                self.assertGreaterEqual(len(tags), 3)
                self.assertTrue(all(row["source_support_score"] >= 70 for row in evidence["selected_keywords"]))

    @patch("win_engine.analysis.semantic_research.gemini_client.generate")
    @patch("win_engine.analysis.semantic_research.gemini_client.is_available", return_value=True)
    def test_semantic_evidence_cannot_smuggle_in_an_unsupported_relationship_event(self, _available, generate):
        quote = "Some doors closing are protection you cannot see yet"
        generate.return_value = json.dumps({
            "primary_topic": "hidden protection",
            "secondary_topics": ["healing after a toxic breakup"],
            "entities": [], "audience": [], "search_intents": ["hidden protection"],
            "keyword_clusters": [], "viewer_intent": "emotional_relatable",
            "concept_evidence": [
                {"concept": "hidden protection", "source_phrase": "doors closing are protection", "relationship": "metaphor"},
                {"concept": "healing after a toxic breakup", "source_phrase": "doors closing", "relationship": "metaphor"},
            ],
        })
        semantic = analyze_script_semantics(quote, {"exact_quote": quote})
        self.assertEqual(semantic["primary_topic"], "hidden protection")
        self.assertNotIn("healing after a toxic breakup", semantic["secondary_topics"])
        self.assertNotIn("toxic breakup", json.dumps(semantic).casefold())


class Phase2EResearchDiscoveryTests(unittest.TestCase):
    def _research(self, *, script: str, semantic: dict, opportunities: list[dict], results: list[dict] | None = None):
        return build_keyword_research(
            script=script,
            semantic=semantic,
            youtube_results=results if results is not None else [{"title": "Reflection on emotional distance", "description": "A thoughtful perspective."}],
            research_queries=[{"type": "primary", "query": semantic["primary_topic"]}],
            entity_signals=[],
            search_opportunities={"status": "gemini_confirmed", "opportunities": opportunities},
            query_diagnostics={"queries_generated": 1, "queries_successful": 1, "youtube_results_unique": len(results if results is not None else [1])},
        )

    def test_research_discovered_concept_cannot_turn_a_quote_into_coping_advice(self):
        research = self._research(
            script="A quote Short about the pain of being emotionally erased.",
            semantic={"primary_topic": "emotional abandonment", "secondary_topics": [], "search_intents": [], "keyword_clusters": []},
            opportunities=[{
                "concept": "coping with emotional abandonment", "intent": "emotional_relatable", "cluster": "emotional abandonment",
                "script_relevance_score": 88, "research_relevance_score": 76, "semantic_confirmed": True,
            }],
        )
        tags, evidence = select_final_tags(
            research, generated_tags=[], title="Being erased hurts #shorts",
            script="A quote Short about the pain of being emotionally erased.",
        )
        self.assertNotIn("coping with emotional abandonment", tags)
        self.assertEqual(evidence["research_contribution"]["research_discovered_selected_count"], 0)

    @patch("win_engine.analysis.search_opportunities.gemini_client.generate")
    @patch("win_engine.analysis.search_opportunities.gemini_client.is_available", return_value=True)
    def test_raw_competitor_phrase_is_rejected_even_when_gemini_returns_it(self, _available, generate):
        generate.return_value = '''{"viewer_intent":"emotional_relatable","opportunities":[{"concept":"feeling invisible after heartbreak","intent":"emotional_relatable","cluster":"absence","script_relevance":90,"research_relevance":80}]}'''
        discovered = discover_search_opportunities(
            script="A Short about emotional absence.", semantic={"primary_topic": "emotional absence"},
            youtube_results=[{"title": "Feeling Invisible After Heartbreak", "description": "A reflective video."}],
        )
        self.assertEqual(discovered["status"], "gemini_confirmed")
        self.assertEqual(discovered["opportunities"], [])
        self.assertEqual(discovered["rejected_count"], 1)

    @patch("win_engine.analysis.semantic_research.gemini_client.generate")
    @patch("win_engine.analysis.semantic_research.gemini_client.is_available", return_value=True)
    def test_semantic_analysis_drops_unsupported_life_history_and_clinical_labels(self, _available, generate):
        generate.return_value = '''{"primary_topic":"emotional exclusion","secondary_topics":["feeling left out","childhood trauma"],"entities":[],"audience":["people feeling excluded","people with chronic loneliness"],"search_intents":["coping with exclusion","healing trauma"],"keyword_clusters":[{"cluster":"exclusion","candidates":["feeling left out","abandonment trauma"]}],"viewer_intent":"emotional_relatable"}'''
        semantic = analyze_script_semantics(
            "A Short about being left out of the story.",
            {"creator_intent": "A reflection on emotional exclusion."},
        )
        text = json.dumps(semantic).casefold()
        self.assertIn("emotional exclusion", text)
        self.assertNotIn("childhood trauma", text)
        self.assertNotIn("chronic loneliness", text)
        self.assertNotIn("abandonment trauma", text)

    def test_research_cannot_promote_an_unstated_repair_mechanism(self):
        research = self._research(
            script="A practical tutorial for repairing a bicycle chain that keeps slipping.",
            semantic={"primary_topic": "bicycle chain repair", "secondary_topics": ["chain slipping"], "search_intents": ["fix a slipping bicycle chain"], "keyword_clusters": []},
            opportunities=[{
                "concept": "bicycle chain alignment", "intent": "how_to", "cluster": "chain repair",
                "script_relevance_score": 82, "research_relevance_score": 78, "semantic_confirmed": True,
            }],
            results=[{"title": "Bike chain maintenance", "description": "Keep a bicycle drivetrain aligned."}],
        )
        _, evidence = select_final_tags(
            research, generated_tags=[], title="Fix a Slipping Bicycle Chain", script="A practical tutorial for repairing a bicycle chain that keeps slipping.",
        )
        comparison = evidence["research_contribution"]
        self.assertNotIn("bicycle chain alignment", comparison["research_enhanced_tags"])
        self.assertNotIn("bicycle chain alignment", comparison["script_only_tags"])

    def test_sparse_or_unavailable_research_has_no_discovered_final_concepts(self):
        research = self._research(
            script="A niche explainer about repairing a vintage slide projector.",
            semantic={"primary_topic": "vintage slide projector repair", "secondary_topics": [], "search_intents": ["repair vintage slide projector"], "keyword_clusters": []},
            opportunities=[], results=[],
        )
        _, evidence = select_final_tags(research, generated_tags=[], title="Repair a Vintage Slide Projector", script="A niche explainer about repairing a vintage slide projector.")
        self.assertEqual(evidence["research_contribution"]["research_discovered_selected_count"], 0)
        self.assertEqual(evidence["diagnostics"]["concepts_discovered"], 0)

    @patch("win_engine.analysis.search_opportunities.gemini_client.generate")
    @patch("win_engine.analysis.search_opportunities.gemini_client.is_available", return_value=True)
    def test_research_opportunity_cannot_invent_a_workplace_or_other_life_context(self, _available, generate):
        generate.return_value = '''{"viewer_intent":"emotional_relatable","opportunities":[{"concept":"coping with workplace exclusion","intent":"emotional_relatable","cluster":"exclusion","script_relevance":90,"research_relevance":80}]}'''
        discovered = discover_search_opportunities(
            script="A quote about being left out of the story.",
            semantic={"primary_topic": "emotional exclusion"},
            creator_brief={"creator_intent": "A reflection on emotional exclusion."},
            youtube_results=[{"title": "Emotional exclusion reflection", "description": "A thoughtful Short."}],
        )
        self.assertEqual(discovered["opportunities"], [])

    def test_query_plan_only_adds_supported_angles_for_each_content_type(self):
        cases = [
            ("A tutorial on cleaning a coffee grinder.", {"primary_topic": "coffee grinder cleaning", "search_intents": ["how to clean coffee grinder"], "keyword_clusters": [], "entities": [], "viewer_intent": "how_to"}),
            ("A current update on a local transit strike.", {"primary_topic": "local transit strike", "search_intents": ["transit strike update"], "keyword_clusters": [], "entities": ["city transit"], "viewer_intent": "current_event"}),
            ("A visual quote about moving on after rejection.", {"primary_topic": "moving on after rejection", "search_intents": [], "keyword_clusters": [{"cluster": "healing", "candidates": ["emotional recovery"]}], "entities": [], "viewer_intent": "emotional_relatable"}),
        ]
        for script, semantic in cases:
            with self.subTest(script=script):
                queries = plan_research_queries(script=script, semantic_analysis=semantic, max_queries=5)
                self.assertLessEqual(len(queries), 5)
                self.assertTrue(queries)
                self.assertEqual(len({item["query"].casefold() for item in queries}), len(queries))


if __name__ == "__main__":
    unittest.main()
