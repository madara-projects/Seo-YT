"""Permanent Phase 2G source-fidelity and final-package regression corpus.

The audit deliberately forces the local fallback.  It is repeatable, does not
consume Gemini quota, does not call YouTube, and still exercises the same final
tag selector and semantic package gate used after Gemini generation.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from win_engine.analysis.creator_brief import build_creator_brief
from win_engine.analysis.keyword_research import build_keyword_research, select_final_tags
from win_engine.feedback.history_store import HistoryStore
from win_engine.generation.strategy_engine import build_seo_package


CASES = [
    # silent quote
    ("silent_quote", "Being misunderstood is the price we pay for being genuine.", "being misunderstood", {"video_format": "youtube_shorts", "voice_over": "none", "exact_quote": "Being misunderstood is the price we pay for being genuine."}),
    ("silent_quote", "Some people only value you when they need you.", "being valued", {"video_format": "youtube_shorts", "voice_over": "none", "exact_quote": "Some people only value you when they need you."}),
    ("silent_quote", "Keep going.", "keep going", {"video_format": "youtube_shorts", "voice_over": "none", "exact_quote": "Keep going."}),
    # tutorial
    ("tutorial", "How to fix a bicycle chain that keeps slipping. Inspect chain tension, align the rear wheel, then test the repair.", "bicycle chain repair", {"video_format": "tutorial", "voice_over": "present"}),
    ("tutorial", "How to clean a burr coffee grinder: unplug it, brush the burrs, and remove stale grounds.", "clean burr coffee grinder", {"video_format": "tutorial", "voice_over": "present"}),
    ("tutorial", "How to stop a leaking tap by checking the washer and tightening the fitting.", "fix leaking tap", {"video_format": "tutorial", "voice_over": "present"}),
    ("tutorial", "How to parse CSV files safely in Python by using newline handling and DictReader.", "python csv parsing", {"video_format": "tutorial", "voice_over": "present"}),
    # comparison
    ("comparison", "TCP establishes a connection before data transfer, while UDP sends packets without the same connection setup.", "tcp vs udp", {"video_format": "educational", "voice_over": "present"}),
    ("comparison", "Mechanical keyboards are tactile; membrane keyboards are quieter.", "mechanical vs membrane keyboards", {"video_format": "comparison", "voice_over": "present"}),
    ("comparison", "A manual coffee grinder needs hand power; a burr grinder gives more consistent grounds.", "manual vs burr coffee grinder", {"video_format": "comparison", "voice_over": "present"}),
    # educational
    ("educational", "DNS translates domain names to IP addresses before a browser reaches a website.", "dns explained", {"video_format": "educational", "voice_over": "present"}),
    ("educational", "An availability zone is an isolated location used for resilient cloud workloads.", "availability zone explained", {"video_format": "educational", "voice_over": "present"}),
    ("educational", "Salt crystals form as water evaporates and leaves dissolved salt behind.", "salt crystal growth", {"video_format": "educational", "voice_over": "present"}),
    # narrative
    ("narrative", "The message was only three words long, but he read it ten times before putting his phone down.", "three word message", {"video_format": "youtube_shorts", "voice_over": "present", "creator_intent": "Cinematic story"}),
    ("narrative", "We used to talk every day. Then neither of us knew how to start the conversation anymore.", "conversations fade away", {"video_format": "youtube_shorts", "voice_over": "present", "creator_intent": "Cinematic story"}),
    ("narrative", "She kept checking the same empty road every evening, even after she knew no one was coming.", "waiting on an empty road", {"video_format": "youtube_shorts", "voice_over": "present", "creator_intent": "Cinematic story"}),
    # sparse
    ("sparse", "Start again.", "start again", {"video_format": "youtube_shorts", "voice_over": "none", "exact_quote": "Start again."}),
    ("sparse", "Breathe.", "breathe", {"video_format": "youtube_shorts", "voice_over": "none", "exact_quote": "Breathe."}),
    # visual-heavy
    ("visual_heavy", "Background visual is a rainy highway. On-screen quote: \"Some people keep you close enough to need you, but never close enough to choose you.\"", "being needed but not chosen", {"video_format": "youtube_shorts", "voice_over": "none", "exact_quote": "Some people keep you close enough to need you, but never close enough to choose you.", "visual_requirements": "rainy highway"}),
    ("visual_heavy", "Background visual is sunset beach waves. On-screen quote: \"We sat beneath the same sky, while my heart quietly imagined a life you never knew existed.\"", "unspoken feelings", {"video_format": "youtube_shorts", "voice_over": "none", "exact_quote": "We sat beneath the same sky, while my heart quietly imagined a life you never knew existed.", "visual_requirements": "sunset beach waves"}),
]


def _research(script: str, topic: str, brief: dict[str, object]) -> dict[str, object]:
    semantic = {
        "primary_topic": topic,
        "secondary_topics": [],
        "search_intents": [topic] if brief.get("video_format") in {"tutorial", "comparison", "educational"} else [],
        "keyword_clusters": [],
        "entities": [],
        "source": "phase2g_fixture",
    }
    keyword_research = build_keyword_research(
        script=script,
        semantic=semantic,
        creator_brief=brief,
        research_queries=[],
        entity_signals=[],
        youtube_results=[],
        search_opportunities={"opportunities": []},
    )
    return {
        "main_topic": topic,
        "keyword_signals": [{"keyword": item["keyword"]} for item in keyword_research["research_targets"]],
        "keyword_research": keyword_research,
        "entity_signals": [],
        "top_opportunities": [],
        "youtube_results": [],
        "research_queries": [],
        "category": "quotes" if brief.get("exact_quote") else "education",
        "creator_brief": brief,
        "language_context": {"language": "english", "region": "global", "audience_type": "general"},
    }


class Phase2GSeoQualityTests(unittest.TestCase):
    def test_twenty_case_offline_final_quality_audit(self):
        self.assertEqual(len(CASES), 20)
        results = []
        with patch("win_engine.generation.strategy_engine.write_multilang_packages_with_source", return_value=({"english": None}, "fallback")):
            for content_type, script, topic, options in CASES:
                with self.subTest(content_type=content_type, topic=topic):
                    brief = build_creator_brief(script=script, **options)
                    package = build_seo_package("generate seo", script, _research(script, topic, brief), HistoryStore(":memory:"))
                    gate = package["generation_quality"]
                    results.append(gate["verdict"])
                    self.assertNotEqual(gate["verdict"], "RED")
                    self.assertEqual(package["generation_source"], "fallback")
                    self.assertFalse(any(tag in {"shorts", "yt", "youtube shorts", "viral shorts"} for tag in package["tags"]))
                    codes = {item["code"] for item in gate["issues"]}
                    self.assertFalse(codes & {
                        "unsupported_instructional_framing", "invented_story_detail", "creator_instruction_leakage",
                        "competitor_title_copy", "quote_fidelity", "platform_tag_filler", "package_consistency_failure",
                    })
                    self.assertIn("final_tag_provenance", package["generation_trace"])
                    self.assertIn("final_quality_verdict", package["generation_trace"])
        self.assertGreaterEqual(results.count("GREEN"), 19, results)
        self.assertEqual(results.count("RED"), 0, results)

    def test_adversarial_research_cannot_enter_final_tags(self):
        script = "Being misunderstood is the price we pay for being genuine."
        brief = build_creator_brief(script=script, video_format="youtube_shorts", voice_over="none", exact_quote=script)
        research = build_keyword_research(
            script=script,
            semantic={"primary_topic": "being misunderstood", "secondary_topics": ["being genuine"], "search_intents": [], "keyword_clusters": []},
            creator_brief=brief,
            research_queries=[],
            entity_signals=[],
            youtube_results=[{"title": "Gaming workplace therapy product review", "description": "competitor language"}],
            search_opportunities={"opportunities": []},
        )
        tags, evidence = select_final_tags(
            research,
            generated_tags=["gaming performance", "workplace therapy", "being misunderstood", "being genuine"],
            title="Being Genuine Can Feel Misunderstood #shorts",
            script=script,
            creator_brief=brief,
        )
        self.assertTrue(set(tags).issubset({"being misunderstood", "being genuine"}))
        self.assertTrue(all(item["provenance"] in {"script_derived", "combined", "research_discovered"} for item in evidence["tag_provenance"]))
        self.assertTrue(any(item["reason"] in {"missing_semantic_support", "irrelevant"} for item in evidence["rejected_candidates"]))


if __name__ == "__main__":
    unittest.main()
