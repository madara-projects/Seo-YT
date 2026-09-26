"""Regression tests for channel-learning gating, window counts, titles and the shared evidence policy."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from win_engine.feedback.channel_learning import learning_summary
from win_engine.feedback.evidence_policy import comparable_metadata, sample_is_eligible
from win_engine.feedback.history_store import HistoryStore
from win_engine.llm import seo_writer

NOW = datetime.now(timezone.utc)


class ChannelLearningFixture(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.path = handle.name
        handle.close()
        self.store = HistoryStore(self.path)
        self.counter = 0

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(self.path + suffix)
            except OSError:
                pass

    def linked(self, *, title: str | None = None, package_title: str | None = None, likes: int | None = 5,
               lifetime_likes: int | None = None, language: str | None = "english", payload: dict | None = None,
               retention: float = 60.0) -> str:
        """A verified linked video with a completed 24h window; returns its video id."""
        self.counter += 1
        title = title or f"Linked upload {self.counter}"
        run_id = self.store.record_analysis_run(
            f"query {self.counter}", "SEARCH", "story", package_title or title, 7, "LOW", "WORKABLE", 50,
            payload=payload or {"title": package_title or title},
        )
        video_id = f"fixflearn{self.counter:02d}"
        link_id = self.store.link_published_video(
            run_id, video_id, (NOW - timedelta(days=3)).isoformat(), format_val="youtube_shorts", language=language,
            ownership_state="verified", ownership_verified=True, verified_channel_id="owner",
            ownership_verified_at=NOW.isoformat(),
        )
        metadata = {"title": title}
        if lifetime_likes is not None:
            metadata["like_count"] = lifetime_likes
        self.store.update_linked_video_metadata(link_id, metadata)
        self.store.record_performance_snapshot(
            video_id, 24, views=100 * self.counter, likes=likes, comments=1, avg_view_percentage=retention,
            snapshot_window="24h",
        )
        return video_id

    def evidence(self, video_id: str) -> dict:
        return next(item for item in learning_summary(self.path)["linked_evidence"] if item["video_id"] == video_id)


class LeadingVideoGatingTests(ChannelLearningFixture):
    def test_leading_videos_are_withheld_until_learning_is_allowed(self):
        for _ in range(4):
            self.linked()
        early = learning_summary(self.path)
        self.assertFalse(early["learning_allowed"])
        self.assertEqual(early["sample_size"], 4)
        self.assertEqual((early["best_videos"], early["weakest_videos"]), ([], []))
        self.assertEqual(len(early["linked_evidence"]), 4)

        self.linked()
        mature = learning_summary(self.path)
        self.assertTrue(mature["learning_allowed"])
        self.assertEqual(len(mature["best_videos"]), 3)
        self.assertEqual(len(mature["weakest_videos"]), 3)

    def test_prompt_shows_no_leading_video_from_a_small_sample_even_if_the_cohort_allows(self):
        for _ in range(4):
            self.linked()
        learning = learning_summary(self.path)
        # The cohort query is a separate computation and can disagree with the summary.
        learning["cohort"] = {"learning_allowed": True, "sample_size": 5, "confidence_label": "Early signal"}

        self.assertNotIn("linked-video pattern", seo_writer._build_channel_learning_block(learning))


class WindowCountTests(ChannelLearningFixture):
    def test_zero_likes_in_the_window_are_not_replaced_by_lifetime_likes(self):
        video_id = self.linked(likes=0, lifetime_likes=750)
        self.assertEqual(self.evidence(video_id)["likes"], 0)

    def test_a_count_the_window_did_not_report_stays_unknown(self):
        video_id = self.linked(likes=None, lifetime_likes=750)
        self.assertIsNone(self.evidence(video_id)["likes"])
        self.assertEqual(self.evidence(video_id)["comments"], 1)


class TitleComparisonTests(ChannelLearningFixture):
    def test_titles_in_any_script_are_compared_by_their_words(self):
        different = self.linked(title="அம்மா பாசம்", package_title="வேறு தலைப்பு")
        same = self.linked(title="அம்மா பாசம் கவிதை", package_title="அம்மா  பாசம் கவிதை!")
        hindi = self.linked(title="माँ का प्यार", package_title="दोस्ती की कहानी")
        english = self.linked(title="Morning Habits!", package_title="morning habits")

        self.assertFalse(self.evidence(different)["title_used"])
        self.assertTrue(self.evidence(same)["title_used"])
        self.assertFalse(self.evidence(hindi)["title_used"])
        self.assertTrue(self.evidence(english)["title_used"])


class EvidencePolicyUnknownTests(ChannelLearningFixture):
    def test_unknown_is_not_comparable_metadata(self):
        self.assertTrue(comparable_metadata({"format": "youtube_shorts", "language": "english"}))
        for link in ({"format": "unknown", "language": "english"}, {"format": "youtube_shorts", "language": "unknown"},
                     {"format": " ", "language": "english"}, {"format": "youtube_shorts"}):
            self.assertFalse(comparable_metadata(link), link)

        verified = {"ownership_state": "verified", "ownership_verified": True, "verified_channel_id": "owner",
                    "ownership_verified_at": NOW.isoformat(), "format": "youtube_shorts", "language": "unknown"}
        snapshot = {"snapshot_window": "24h", "snapshot_status": "complete", "completed_at": NOW.isoformat(), "views": 10}
        self.assertFalse(sample_is_eligible(verified, snapshot, expected_window="24h"))
        self.assertTrue(sample_is_eligible({**verified, "language": "english"}, snapshot, expected_window="24h"))

    def test_retention_learning_does_not_count_unknown_language_videos(self):
        payload = {"retention_assistant": {"rule_version": "phase5-v1", "opening": {"clarity": "clear"},
                                           "pacing": {"format_assessment": "steady"}, "quote_presentation": {}}}
        for _ in range(5):
            self.linked(language=None, payload=payload)
        self.assertEqual(self.store.retention_learning_summary()["sample_size"], 0)

        for _ in range(5):
            self.linked(language="english", payload=payload)
        summary = self.store.retention_learning_summary()
        self.assertEqual(summary["sample_size"], 5)
        self.assertTrue(summary["learning_allowed"])


if __name__ == "__main__":
    unittest.main()
