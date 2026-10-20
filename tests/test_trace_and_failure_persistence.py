"""The trace names the delivered tags, and a failed package stage leaves nothing in History.

Two audit findings. A Creator run delivered five tags while its
generation_trace.final_tags listed seven: the writer stage recorded its own
selection, and refinement, the risk filter and the final gate trimmed it
afterwards without the trace following (only AI Shorts re-synced it). And a
forced refinement failure left one saved run: the writer stage records its
run before the package stage finishes, and nothing removed it.
"""

import unittest
from unittest.mock import patch

from win_engine.analysis.creator_brief import build_creator_brief
from win_engine.feedback.history_store import HistoryStore
from win_engine.generation import seo_generator
from win_engine.generation.quality_refinement import refine_package
from win_engine.generation.seo_generator import generate_seo_suggestions
from win_engine.llm import gemini_client

COLD_BREW = (
    "How to make cold brew coffee at home without any special equipment. First, grind the beans coarse. "
    "Then mix one part coffee with four parts water in a jar and steep it in the fridge for 18 hours. "
    "Finally strain it through a paper filter and dilute it with milk or water."
)
# The local writer selects two tags for this script, so refinement has one to trim.
OBS_STREAM = (
    "How to set up OBS Studio for YouTube live streaming on a budget laptop. I cover the best OBS settings "
    "for 1080p streaming, the bitrate and encoder to pick, how to add a webcam overlay and alerts, and how to "
    "fix dropped frames and audio desync. Everything here is free, no capture card needed."
)


def _generate(script, store):
    brief = build_creator_brief(script=script, video_format="tutorial")
    research = {"history_store": store, "youtube_results": [], "keyword_signals": [], "entity_signals": [],
                "top_opportunities": [], "upload_timing": {}, "thumbnail_intelligence": {}}
    with patch.object(gemini_client, "is_available", return_value=False):
        return generate_seo_suggestions(script, research, context={
            "language": "english", "video_language": "english", "region": "global", "creator_brief": brief,
        })


class FinalTagsTraceTests(unittest.TestCase):
    def test_final_tags_name_the_delivered_tags_after_a_trim(self):
        seen = {}

        def trimming_refinement(package, **kwargs):
            # The real refinement, then one tag fewer: the trim a live run showed.
            refined, trace = refine_package(package, **kwargs)
            tags = list(refined.get("tags") or package.get("tags") or [])
            seen["before"] = tags
            if len(tags) > 1:
                refined = {**refined, "tags": tags[:-1]}
            return refined, trace

        with patch.object(seo_generator, "refine_package", side_effect=trimming_refinement):
            response = _generate(OBS_STREAM, HistoryStore(":memory:"))

        before = seen.get("before") or []
        self.assertGreater(len(before), 1, "the package stage selected tags for refinement to trim")
        dropped = before[-1]
        trace = response["generation_trace"]
        self.assertNotIn(dropped, response["tags"])
        self.assertEqual(trace["final_tags"], response["tags"])
        self.assertNotIn(dropped.casefold(), [
            str(item.get("tag") or item.get("keyword") or "").casefold()
            for item in trace.get("final_tag_provenance") or []
        ])
        self.assertNotIn(dropped.casefold(), [
            str(item.get("keyword") or "").casefold() for item in trace.get("final_tag_scores") or []
        ])

    def test_final_tags_match_without_a_trim(self):
        response = _generate(COLD_BREW, HistoryStore(":memory:"))
        self.assertTrue(response["tags"])
        self.assertEqual(response["generation_trace"]["final_tags"], response["tags"])


class FailedRunPersistenceTests(unittest.TestCase):
    def test_a_refinement_failure_leaves_no_saved_run(self):
        store = HistoryStore(":memory:")
        with patch.object(seo_generator, "refine_package", side_effect=RuntimeError("forced refinement failure")):
            with self.assertRaises(RuntimeError):
                _generate(COLD_BREW, store)
        self.assertEqual(store.history_run_count(), 0)
        self.assertEqual(store.history_runs(limit=5), [])

    def test_a_successful_run_is_saved_once(self):
        store = HistoryStore(":memory:")
        response = _generate(COLD_BREW, store)
        self.assertIsInstance(response["history_run_id"], int)
        self.assertEqual(store.history_run_count(), 1)
        saved = store.history_run(response["history_run_id"])
        self.assertEqual(saved["title"], response["title"])


if __name__ == "__main__":
    unittest.main()
