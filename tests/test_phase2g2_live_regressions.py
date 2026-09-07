"""Phase 2G.2 regression and live contract test suite.

Validates:
1. Negation-aware voice-over parsing (no false contradiction warnings).
2. Metadata header prefix stripping (no false quote delay warnings).
3. Atmospheric/cinematic quote Short retention analysis.
4. Preservation of 'yt' and 'shorts' as intentional format tags.
5. Tag score integrity (platform tags do not inflate semantic tag score).
6. Shorts prefer 5-6 strong semantic tags over weak padding.
7. Quality refinement rank includes tag score.
8. Quality refinement repairs tag score shortfalls.
9. Strict 90/90/90 quality target enforcement for GREEN verdict.
10. End-to-end quote package generation reaching GREEN with all constraints met.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from win_engine.analysis.content_auditor import audit_content_package
from win_engine.analysis.creator_brief import build_creator_brief
from win_engine.analysis.generation_quality import evaluate_package_quality
from win_engine.analysis.keyword_research import (
    build_keyword_research,
    select_final_tags,
)
from win_engine.analysis.retention_assistant import analyze_retention_assistant
from win_engine.feedback.history_store import HistoryStore
from win_engine.generation.quality_refinement import (
    TARGET,
    enforce_quality_target,
    refine_package,
)
from win_engine.generation.seo_generator import generate_seo_suggestions


class Phase2G2LiveRegressionTests(unittest.TestCase):
    def test_01_voice_over_negated_patterns(self):
        """Negation patterns like 'Voice-over: none' must be recognized as none without contradiction."""
        test_scripts = [
            "Format: YouTube Shorts\nVisual: Rain at dusk\nVoice-over: none\nOn-screen text: A silent truth.",
            "Visual: Sunset beach\nVoice-over: absent\nQuote: Quiet waves.",
            "Visual: Mountains\nno voice-over\nQuote: High peaks.",
            "Visual: City rain\nVoice-over: silent\nQuote: Empty streets.",
        ]
        for script in test_scripts:
            with self.subTest(script=script[:30]):
                brief = build_creator_brief(script=script)
                self.assertEqual(brief["voice_over"], "none")
                retention = analyze_retention_assistant(script, creator_brief=brief)
                all_risks = [
                    r for stage in retention.get("risk_map", [])
                    for r in stage.get("risks", [])
                ]
                contradiction_risks = [
                    r for r in all_risks
                    if r.get("risk_code") == "voice_over_visual_contradiction"
                ]
                self.assertEqual(contradiction_risks, [], f"False contradiction for: {script}")

    def test_02_metadata_prefix_stripping(self):
        """Metadata lines (Format, Visual, Voice-over) before quote must not trigger quote_context_delay."""
        script = (
            "Format: YouTube Shorts\n"
            "Visual: Rain drops on window pane at dusk, melancholic lofi mood\n"
            "Voice-over: none\n"
            "On-screen text: Hope can be cruel when it keeps you waiting for a person who will never return."
        )
        brief = build_creator_brief(script=script)
        retention = analyze_retention_assistant(script, creator_brief=brief)
        quote_summary = retention["quote_presentation"]
        self.assertEqual(quote_summary["context_words_before_quote"], 0)
        all_risks = [
            r for stage in retention.get("risk_map", [])
            for r in stage.get("risks", [])
        ]
        delay_risks = [
            r for r in all_risks
            if r.get("risk_code") == "quote_context_delay"
        ]
        self.assertEqual(delay_risks, [])

    def test_03_quote_short_atmospheric_hook(self):
        """Atmospheric and cinematic quote Shorts must not get LOW hook strength or HIGH dropoff risk."""
        script = (
            "Format: YouTube Shorts\n"
            "Visual: Rain drops on window pane at dusk, melancholic lofi mood\n"
            "Voice-over: none\n"
            "On-screen text: Hope can be cruel when it keeps you waiting for a person who will never return."
        )
        audit = audit_content_package(
            script=script,
            title="When false hope keeps you waiting 🌧️ #shorts",
            primary_topic="false hope",
            secondary_topic="letting go",
            content_angle="Story",
            video_format="youtube_shorts",
        )
        hook_strength = audit["hook_audit"]["hook_strength"]
        dropoff_risk = audit["first_30_second_simulator"]["predicted_dropoff_risk"]
        self.assertIn(hook_strength, {"MEDIUM", "HIGH"})
        self.assertIn(dropoff_risk, {"LOW", "MEDIUM"})
        self.assertNotEqual(dropoff_risk, "HIGH")

    def test_04_yt_and_shorts_preserved_in_final_tags(self):
        """yt and shorts are intentionally required for Shorts packages and must be preserved."""
        script = "Hope can be cruel when it keeps you waiting for a person who will never return."
        brief = build_creator_brief(script=script, video_format="youtube_shorts")
        research = build_keyword_research(
            script=script,
            semantic={"primary_topic": "false hope", "secondary_topics": ["waiting on someone"], "search_intents": [], "keyword_clusters": []},
            creator_brief=brief,
            research_queries=[],
            entity_signals=[],
            youtube_results=[],
            search_opportunities={"opportunities": []},
        )
        tags, evidence = select_final_tags(
            research,
            generated_tags=["false hope", "moving on", "letting go"],
            title="When false hope keeps you waiting #shorts",
            script=script,
            creator_brief=brief,
        )
        self.assertIn("yt", tags)
        self.assertIn("shorts", tags)
        # Verify classification is platform_format
        prov_map = {item["tag"]: item for item in evidence["tag_provenance"]}
        self.assertEqual(prov_map["yt"]["provenance"], "creator_strategy")
        self.assertEqual(prov_map["shorts"]["provenance"], "creator_strategy")

    def test_05_tag_score_integrity_platform_tags_not_inflated(self):
        """Platform tags yt/shorts must not artificially inflate a weak semantic tag set."""
        package = {
            "title": "When false hope keeps you waiting 🌧️ #shorts",
            "variants": ["When false hope keeps you waiting 🌧️ #shorts"],
            "description": '"Hope can be cruel when it keeps you waiting for a person who will never return." A reflection on moving on.',
            "tags": ["weak tag", "another weak tag", "yt", "shorts"],
            "hashtags": ["#shorts", "#Hope"],
        }
        evidence = {
            "selected_keywords": [
                {"keyword": "weak tag", "classification": "topic", "source_classification": "combined", "source_support_score": 85, "keyword_relevance_score": 60.0},
                {"keyword": "another weak tag", "classification": "topic", "source_classification": "combined", "source_support_score": 85, "keyword_relevance_score": 65.0},
                {"keyword": "yt", "classification": "platform_format", "source_classification": "creator_strategy", "source_support_score": 100, "keyword_relevance_score": 0},
                {"keyword": "shorts", "classification": "platform_format", "source_classification": "creator_strategy", "source_support_score": 100, "keyword_relevance_score": 0},
            ]
        }
        gate = evaluate_package_quality(
            package,
            script='Quote: "Hope can be cruel when it keeps you waiting for a person who will never return." Shorts',
            creator_brief={"exact_quote": "Hope can be cruel when it keeps you waiting for a person who will never return.", "video_format": "youtube_shorts"},
            tag_evidence=evidence,
        )
        semantic_quality = gate["final_seo_quality"]
        # Tag score should reflect average of weak tags (62.5), NOT inflated by yt/shorts
        self.assertEqual(semantic_quality["tag_score"], 62.5)
        self.assertNotEqual(gate["verdict"], "GREEN")

    def test_06_shorts_prefers_5_to_6_strong_semantic_tags(self):
        """Shorts tag selection should prioritize 5-6 strong semantic tags over weak padding."""
        script = "Hope can be cruel when it keeps you waiting for a person who will never return."
        brief = build_creator_brief(script=script, video_format="youtube_shorts")
        candidates = [
            {"keyword": "false hope", "sources": ["model"], "classification": "core_topic", "content_relevance_score": 30, "keyword_relevance_score": 96, "source_support_score": 100},
            {"keyword": "painful truth", "sources": ["model"], "classification": "core_topic", "content_relevance_score": 30, "keyword_relevance_score": 94, "source_support_score": 100},
            {"keyword": "moving on", "sources": ["model"], "classification": "core_topic", "content_relevance_score": 30, "keyword_relevance_score": 92, "source_support_score": 100},
            {"keyword": "heartbreak quotes", "sources": ["model"], "classification": "core_topic", "content_relevance_score": 30, "keyword_relevance_score": 90, "source_support_score": 100},
            {"keyword": "unrequited love", "sources": ["model"], "classification": "core_topic", "content_relevance_score": 30, "keyword_relevance_score": 90, "source_support_score": 100},
            {"keyword": "wrong person", "sources": ["model"], "classification": "core_topic", "content_relevance_score": 30, "keyword_relevance_score": 68, "source_support_score": 70},
            {"keyword": "quiet comfort", "sources": ["model"], "classification": "core_topic", "content_relevance_score": 30, "keyword_relevance_score": 72, "source_support_score": 70},
        ]
        research = {
            "candidates": candidates,
            "content_terms": ["hope", "cruel", "waiting", "person", "return", "false", "painful", "truth", "moving", "heartbreak", "quotes", "unrequited", "love", "comfort"],
            "visual_terms": [],
            "research_targets": [],
            "queries": [],
            "results": [],
        }
        tags, evidence = select_final_tags(
            research,
            generated_tags=[],
            title="When false hope keeps you waiting #shorts",
            script=script,
            creator_brief=brief,
        )
        # Should not contain the weak tags 68 and 72
        self.assertNotIn("wrong person", tags)
        self.assertNotIn("quiet comfort", tags)
        # Should contain the strong tags and platform tags
        self.assertIn("false hope", tags)
        self.assertIn("yt", tags)
        self.assertIn("shorts", tags)
        # Total semantic tags should be <= 6
        semantic_tags = [t for t in tags if t not in {"yt", "shorts"}]
        self.assertLessEqual(len(semantic_tags), 6)
        self.assertGreaterEqual(len(semantic_tags), 3)

    def test_07_quality_refinement_rank_includes_tag_score(self):
        """quality_refinement.rank evaluates title, description, and tag scores together."""
        pkg_low_tag = {
            "title": "Title #shorts",
            "variants": ["Title #shorts"],
            "description": "Description text.",
            "tags": ["weak1", "weak2", "weak3", "yt", "shorts"],
            "hashtags": ["#shorts"],
        }
        evidence = {
            "selected_keywords": [
                {"keyword": "weak1", "keyword_relevance_score": 70.0, "source_support_score": 80},
                {"keyword": "weak2", "keyword_relevance_score": 70.0, "source_support_score": 80},
                {"keyword": "weak3", "keyword_relevance_score": 70.0, "source_support_score": 80},
                {"keyword": "yt", "classification": "platform_format", "keyword_relevance_score": 0, "source_support_score": 100},
                {"keyword": "shorts", "classification": "platform_format", "keyword_relevance_score": 0, "source_support_score": 100},
            ]
        }
        with patch("win_engine.generation.quality_refinement.gemini_client.is_available", return_value=False):
            refined, trace = refine_package(
                pkg_low_tag,
                script="Some script text",
                brief={"video_format": "youtube_shorts"},
                language="english",
                region="global",
                evidence=evidence,
                competitors=[],
            )
            self.assertIn("before", trace)
            self.assertIn("after", trace)

    def test_08_quality_refinement_repairs_tag_score(self):
        """quality_refinement prunes weak tags when tag_score is below target."""
        pkg = {
            "title": "When false hope keeps you waiting 🌧️ #shorts",
            "variants": ["When false hope keeps you waiting 🌧️ #shorts"],
            "description": '"Hope can be cruel when it keeps you waiting for a person who will never return." A reflection on moving on and finding peace.',
            "tags": ["false hope", "painful truth", "moving on", "heartbreak quotes", "wrong person", "let go", "yt", "shorts"],
            "hashtags": ["#shorts", "#Hope"],
        }
        evidence = {
            "selected_keywords": [
                {"keyword": "false hope", "classification": "topic", "keyword_relevance_score": 96.0, "source_support_score": 100},
                {"keyword": "painful truth", "classification": "topic", "keyword_relevance_score": 94.0, "source_support_score": 100},
                {"keyword": "moving on", "classification": "topic", "keyword_relevance_score": 92.0, "source_support_score": 100},
                {"keyword": "heartbreak quotes", "classification": "topic", "keyword_relevance_score": 90.0, "source_support_score": 100},
                {"keyword": "wrong person", "classification": "topic", "keyword_relevance_score": 68.0, "source_support_score": 70},
                {"keyword": "let go", "classification": "topic", "keyword_relevance_score": 72.0, "source_support_score": 70},
                {"keyword": "yt", "classification": "platform_format", "keyword_relevance_score": 0, "source_support_score": 100},
                {"keyword": "shorts", "classification": "platform_format", "keyword_relevance_score": 0, "source_support_score": 100},
            ]
        }
        script = 'Quote: "Hope can be cruel when it keeps you waiting for a person who will never return." Shorts'
        brief = {
            "exact_quote": "Hope can be cruel when it keeps you waiting for a person who will never return.",
            "video_format": "youtube_shorts",
            "voice_over": "none",
        }
        with patch("win_engine.generation.quality_refinement.gemini_client.is_available", return_value=False):
            refined, trace = refine_package(
                pkg,
                script=script,
                brief=brief,
                language="english",
                region="global",
                evidence=evidence,
                competitors=[],
            )
            # The weak tags 68 and 72 should have been pruned locally
            self.assertNotIn("wrong person", refined["tags"])
            self.assertNotIn("let go", refined["tags"])
            self.assertIn("false hope", refined["tags"])
            self.assertIn("yt", refined["tags"])
            self.assertIn("shorts", refined["tags"])
            # After repair, the gate tag score must be >= 90
            after_scores = trace["after"]
            self.assertGreaterEqual(after_scores["tag_score"], TARGET)

    def test_09_enforce_quality_target_requires_all_three_90(self):
        """Strict 90/90/90 quality target: any score below 90 denies GREEN."""
        cases = [
            ((95, 92, 91), True, "GREEN"),
            ((89.9, 95, 95), False, "YELLOW"),
            ((95, 89.9, 95), False, "YELLOW"),
            ((95, 95, 89.9), False, "YELLOW"),
            ((95, 95, None), False, "YELLOW"),
        ]
        for (t, d, tg), expected_met, expected_verdict in cases:
            with self.subTest(title=t, desc=d, tag=tg):
                gate = {
                    "verdict": "GREEN",
                    "final_seo_quality": {
                        "title_score": t,
                        "description_score": d,
                        "tag_score": tg,
                        "verdict": "GREEN",
                    },
                }
                result = enforce_quality_target(gate)
                self.assertEqual(result["quality_target"]["met"], expected_met)
                self.assertEqual(result["verdict"], expected_verdict)

    def test_10_live_quote_contract_end_to_end(self):
        """Live quote script must produce GREEN package with title>=90, desc>=90, tag>=90 and yt/shorts preserved."""
        script = (
            "Format: YouTube Shorts\n"
            "Visual: Rain drops on window pane at dusk, melancholic lofi mood\n"
            "Voice-over: none\n"
            "On-screen text: Hope can be cruel when it keeps you waiting for a person who will never return."
        )
        brief = build_creator_brief(script=script)
        self.assertEqual(brief["voice_over"], "none")
        self.assertEqual(brief["video_format"], "youtube_shorts")
        self.assertIn("Hope can be cruel", brief["exact_quote"])

        research_data = {
            "main_topic": "false hope",
            "keyword_signals": [{"keyword": "false hope"}, {"keyword": "moving on"}, {"keyword": "letting go"}],
            "keyword_research": {
                "candidates": [
                    {"keyword": "false hope", "sources": ["model", "research_query"], "classification": "core_topic", "keyword_relevance_score": 96, "content_relevance_score": 42, "source_support_score": 100, "source_support": "support", "source_classification": "combined"},
                    {"keyword": "painful truth", "sources": ["model"], "classification": "secondary_topic", "keyword_relevance_score": 94, "content_relevance_score": 42, "source_support_score": 100, "source_support": "support", "source_classification": "script_derived"},
                    {"keyword": "moving on", "sources": ["model", "research_query"], "classification": "secondary_topic", "keyword_relevance_score": 92, "content_relevance_score": 42, "source_support_score": 100, "source_support": "support", "source_classification": "combined"},
                    {"keyword": "heartbreak quotes", "sources": ["model"], "classification": "secondary_topic", "keyword_relevance_score": 90, "content_relevance_score": 42, "source_support_score": 100, "source_support": "support", "source_classification": "script_derived"},
                ],
                "selected_keywords": [
                    {"keyword": "false hope", "classification": "topic", "source_classification": "combined", "source_support_score": 100, "source_support": "support", "keyword_relevance_score": 95},
                    {"keyword": "painful truth", "classification": "topic", "source_classification": "script_derived", "source_support_score": 100, "source_support": "support", "keyword_relevance_score": 95},
                    {"keyword": "moving on", "classification": "topic", "source_classification": "combined", "source_support_score": 100, "source_support": "support", "keyword_relevance_score": 95},
                    {"keyword": "heartbreak quotes", "classification": "topic", "source_classification": "script_derived", "source_support_score": 100, "source_support": "support", "keyword_relevance_score": 95},
                    {"keyword": "yt", "classification": "platform_format", "source_classification": "creator_strategy", "source_support_score": 100, "source_support": "support", "keyword_relevance_score": 0},
                    {"keyword": "shorts", "classification": "platform_format", "source_classification": "creator_strategy", "source_support_score": 100, "source_support": "support", "keyword_relevance_score": 0},
                ],
                "content_terms": ["hope", "cruel", "waiting", "person", "never", "return", "false", "moving", "painful", "truth", "heartbreak", "quotes", "peace", "letting", "go", "rain", "dusk", "window"],
                "visual_terms": ["rain", "dusk", "window", "pane"],
                "research_targets": [],
                "queries": [],
                "results": [],
            },
            "entity_signals": [],
            "top_opportunities": [],
            "youtube_results": [],
            "research_queries": [],
            "category": "quotes",
            "creator_brief": brief,
            "language_context": {"language": "english", "region": "global", "audience_type": "general"},
            "history_store": HistoryStore(":memory:"),
        }
        context = {
            "language": "english",
            "video_language": "english",
            "region": "global",
            "audience_type": "general",
            "creator_brief": brief,
        }

        quote_text = brief["exact_quote"]
        generated_pkg = {
            "title": "When false hope keeps you waiting #shorts",
            "variants": [
                "When false hope keeps you waiting #shorts",
                "Hope becomes painful when they never return #shorts",
                "The quiet heartbreak of false hope #shorts",
            ],
            "description": f'"{quote_text}" A reflection on quiet heartbreak and knowing when to let go.',
            "tags": ["false hope", "painful truth", "moving on", "heartbreak quotes", "yt", "shorts"],
            "hashtags": ["#shorts", "#FalseHope", "#HeartbreakQuotes"],
        }

        with patch("win_engine.llm.gemini_client.is_available", return_value=True), \
             patch("win_engine.generation.strategy_engine.write_multilang_packages_with_source", return_value=({"english": generated_pkg}, "gemini")), \
             patch("win_engine.generation.quality_refinement.gemini_client.is_available", return_value=True):
            response = generate_seo_suggestions(script, research_data, context=context)

        quality = response["generation_quality"]["final_seo_quality"]
        self.assertGreaterEqual(quality["title_score"], 90.0, f"Title score {quality['title_score']} < 90")
        self.assertGreaterEqual(quality["description_score"], 90.0, f"Description score {quality['description_score']} < 90")
        self.assertGreaterEqual(quality["tag_score"], 90.0, f"Tag score {quality['tag_score']} < 90")
        self.assertEqual(response["generation_quality"]["verdict"], "GREEN")

        # Verify yt and shorts presence
        pkg_tags = response["tags"]
        self.assertIn("yt", pkg_tags)
        self.assertIn("shorts", pkg_tags)

        # Verify no false warnings
        warnings = [w["code"] for w in quality.get("warnings", [])]
        self.assertNotIn("voice_over_contradiction", warnings)
        self.assertNotIn("weak_tag_usefulness", warnings)
        self.assertNotIn("quality_target_not_met", warnings)


if __name__ == "__main__":
    unittest.main()
