"""Regression tests for channel-learning gating, window counts, titles and the shared evidence policy."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from win_engine.feedback.channel_learning import learning_summary
from win_engine.feedback.evidence_policy import comparable_metadata, pattern_signal, sample_is_eligible
from win_engine.feedback.history_store import ANALYTICS_ZONE, HistoryStore, window_covered_hours
from win_engine.llm import seo_writer

NOW = datetime.now(timezone.utc)
PUBLISHED = NOW - timedelta(days=3)
# The last Pacific day of a 24h window for a video published at PUBLISHED.
LAST_DAY = (PUBLISHED + timedelta(hours=24)).astimezone(ANALYTICS_ZONE).date().isoformat()


class ChannelLearningFixture(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.path = handle.name
        handle.close()
        self.store = HistoryStore(self.path)
        self.counter = 0
        # Learning reads only the connected channel's linked videos.
        with self.store._connect() as connection:
            connection.execute(
                "INSERT INTO youtube_channel_connection (id, encrypted_refresh_token, channel_id, channel_title, connected_at, updated_at) "
                "VALUES (1, 'token', ?, 'Owner', '2026-08-01T00:00:00Z', '2026-08-01T00:00:00Z')",
                ("owner",),
            )

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(self.path + suffix)
            except OSError:
                pass

    def linked(self, *, title: str | None = None, package_title: str | None = None, likes: int | None = 5,
               lifetime_likes: int | None = None, language: str | None = "english", payload: dict | None = None,
               retention: float = 60.0, views: int | None = None, format_val: str = "youtube_shorts",
               covered_hours: float | None = 24.0) -> str:
        """A verified linked video with a completed 24h window; returns its video id.

        `covered_hours` is stored as the capture records it; None leaves it
        unknown, as on rows from before version 13.
        """
        self.counter += 1
        views = 100 * self.counter if views is None else views
        title = title or f"Linked upload {self.counter}"
        run_id = self.store.record_analysis_run(
            f"query {self.counter}", "SEARCH", "story", package_title or title, 7, "LOW", "WORKABLE", 50,
            payload=payload or {"title": package_title or title},
        )
        video_id = f"fixflearn{self.counter:02d}"
        # The creator confirmed the uploaded title when linking.
        link_id = self.store.link_published_video(
            run_id, video_id, PUBLISHED.isoformat(), selected_title=title, format_val=format_val, language=language,
            ownership_state="verified", ownership_verified=True, verified_channel_id="owner",
            ownership_verified_at=NOW.isoformat(),
        )
        metadata = {"title": title}
        if lifetime_likes is not None:
            metadata["like_count"] = lifetime_likes
        self.store.update_linked_video_metadata(link_id, metadata)
        self.store.record_performance_snapshot(
            video_id, 24, views=views, likes=likes, comments=1, avg_view_percentage=retention,
            snapshot_window="24h", source_end_date=LAST_DAY,
        )
        if covered_hours is not None:
            with self.store._connect() as connection:
                connection.execute(
                    "UPDATE video_performance_snapshots SET covered_hours = ? WHERE youtube_video_id = ?",
                    (covered_hours, video_id),
                )
        return video_id

    def evidence(self, video_id: str) -> dict:
        return next(item for item in learning_summary(self.path)["linked_evidence"] if item["video_id"] == video_id)

    def set_snapshot(self, video_id: str, **columns) -> None:
        assignments = ", ".join(f"{column} = ?" for column in columns)
        with self.store._connect() as connection:
            connection.execute(
                f"UPDATE video_performance_snapshots SET {assignments} WHERE youtube_video_id = ?",
                (*columns.values(), video_id),
            )

    @staticmethod
    def prompt_block(summary: dict) -> str:
        return seo_writer._build_channel_learning_block(
            {**summary, "cohort": {"learning_allowed": True, "sample_size": summary["sample_size"]}}
        )


class LeadingVideoGatingTests(ChannelLearningFixture):
    def test_leading_videos_are_withheld_below_ten_videos(self):
        for _ in range(4):
            self.linked()
        early = learning_summary(self.path)
        self.assertFalse(early["learning_allowed"])
        self.assertEqual(early["sample_size"], 4)
        self.assertEqual((early["best_videos"], early["weakest_videos"]), ([], []))
        self.assertEqual(len(early["linked_evidence"]), 4)

        self.linked()
        five = learning_summary(self.path)
        # Five videos allow learning in general, but a leading group needs ten
        # before its lead can be told from noise; it used to be shown at five.
        self.assertTrue(five["learning_allowed"])
        self.assertEqual((five["best_videos"], five["weakest_videos"]), ([], []))
        self.assertEqual(five["pattern_signal"]["status"], "insufficient_sample")
        self.assertIn("10", five["recommendation"])
        # The prompt gets the reason, never a leading video.
        block = self.prompt_block(five)
        self.assertNotIn("linked-video pattern:", block)
        self.assertIn("No linked-video pattern was applied", block)


class PatternGateTests(ChannelLearningFixture):
    """A leading group is a pattern only when it beats the rest by more than noise."""

    FLAT = (1050, 1080, 1100, 1120, 1150, 1180, 1200, 1250, 1290, 1310)
    SPLIT = (100, 110, 120, 130, 140, 150, 160, 400, 420, 450)

    def test_a_flat_spread_sends_no_pattern_and_says_why(self):
        # The owner's Shorts sat at 1,050-1,310 views: a 12% spread is noise.
        for views in self.FLAT:
            self.linked(views=views)
        summary = learning_summary(self.path)
        self.assertTrue(summary["learning_allowed"])
        self.assertEqual(summary["sample_size"], 10)
        self.assertEqual((summary["best_videos"], summary["weakest_videos"]), ([], []))
        signal = summary["pattern_signal"]
        self.assertEqual(signal["status"], "no_pattern")
        self.assertLess(signal["margin"], signal["minimum_margin"])
        self.assertEqual((signal["leading_median"], signal["rest_median"]), (1290.0, 1120.0))
        self.assertIn("No linked-video pattern", summary["recommendation"])
        block = self.prompt_block(summary)
        self.assertNotIn("linked-video pattern:", block)
        self.assertIn("No linked-video pattern", block)

    def test_a_leading_group_a_quarter_ahead_of_the_rest_is_a_pattern(self):
        for views in self.SPLIT:
            self.linked(views=views)
        summary = learning_summary(self.path)
        signal = summary["pattern_signal"]
        self.assertEqual(signal["status"], "pattern")
        self.assertGreaterEqual(signal["margin"], signal["minimum_margin"])
        self.assertEqual([item["views"] for item in summary["best_videos"]], [450, 420, 400])
        self.assertEqual([item["views"] for item in summary["weakest_videos"]], [100, 110, 120])
        self.assertIn("linked-video pattern:", self.prompt_block(summary))

    def test_a_mixed_cohort_is_not_compared(self):
        for index, views in enumerate(self.SPLIT):
            self.linked(views=views, language="english" if index % 2 else "tamil")
        mixed = learning_summary(self.path)
        self.assertEqual(mixed["sample_size"], 10)
        self.assertEqual(mixed["pattern_signal"]["status"], "mixed_cohort")
        self.assertEqual(mixed["best_videos"], [])
        self.assertIn("mixed", mixed["recommendation"].casefold())
        english = learning_summary(self.path, language_filter="english")
        self.assertEqual(english["sample_size"], 5)
        self.assertEqual(english["pattern_signal"]["status"], "insufficient_sample")

    def test_long_form_formats_are_one_cohort(self):
        # The format filter groups tutorials, reviews and talking heads as long
        # form; counted as three cohorts, long form could never form a pattern.
        formats = ("tutorial", "review", "talking_head")
        for index, views in enumerate(self.SPLIT):
            self.linked(views=views, format_val=formats[index % 3])
        summary = learning_summary(self.path)
        self.assertEqual(summary["sample_size"], 10)
        self.assertEqual(summary["pattern_signal"]["status"], "pattern")
        self.assertEqual([item["views"] for item in summary["best_videos"]], [450, 420, 400])
        # A Short beside them is still a different cohort.
        for views in self.SPLIT:
            self.linked(views=views)
        self.assertEqual(learning_summary(self.path)["pattern_signal"]["status"], "mixed_cohort")

    def test_a_lead_over_a_rest_with_no_views_is_a_pattern_not_noise(self):
        # A median of 0 has no ratio to beat; it read "within 25% of the rest's (0)".
        signal = pattern_signal([90.0, 80.0, 70.0, *([0.0] * 7)], comparable=True)
        self.assertEqual((signal["status"], signal["margin"]), ("pattern", None))
        self.assertIn("(0)", signal["reason"])
        self.assertEqual(pattern_signal([0.0] * 10, comparable=True)["status"], "no_pattern")

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


class CoveredDayTests(ChannelLearningFixture):
    """A "24h" window is whole Pacific days: 24 to 48 hours after publication."""

    def test_videos_are_ranked_by_views_per_covered_day_not_raw_totals(self):
        long_window = self.linked(views=470, covered_hours=47.0)
        short_window = self.linked(views=300, covered_hours=25.0)
        evidence = learning_summary(self.path)["linked_evidence"]
        # 470 views in 47 hours is 240 a day; 300 in 25 hours is 288.
        self.assertEqual([item["video_id"] for item in evidence], [short_window, long_window])
        self.assertEqual([item["views_per_covered_day"] for item in evidence], [288.0, 240.0])
        self.assertEqual([item["covered_hours"] for item in evidence], [25.0, 47.0])

    def test_a_row_without_stored_coverage_uses_its_publication_time(self):
        video_id = self.linked(views=480, covered_hours=None)
        hours = window_covered_hours(PUBLISHED.isoformat(), LAST_DAY)
        self.assertTrue(24 <= hours <= 49)
        self.assertEqual(self.evidence(video_id)["covered_hours"], hours)
        self.assertEqual(self.evidence(video_id)["views_per_covered_day"], round(480 * 24 / hours, 2))

    def test_unknown_coverage_is_counted_but_never_compared_as_24_hours(self):
        for views in PatternGateTests.SPLIT:
            self.linked(views=views)
        unknown = self.linked(views=99999, covered_hours=None)
        self.set_snapshot(unknown, source_end_date=None)
        summary = learning_summary(self.path)
        self.assertEqual((summary["sample_size"], summary["compared_sample_size"]), (11, 10))
        self.assertIsNone(self.evidence(unknown)["views_per_covered_day"])
        self.assertNotIn(unknown, [item["video_id"] for item in summary["best_videos"]])
        self.assertEqual([item["views"] for item in summary["best_videos"]], [450, 420, 400])
        self.assertIn("views per covered day", summary["recommendation"])
        self.assertEqual(summary["pattern_signal"]["measure"], "views per covered day")

    def test_a_small_sample_says_how_many_windows_are_not_compared(self):
        for _ in range(3):
            self.linked()
        unknown = self.linked(covered_hours=None)
        self.set_snapshot(unknown, source_end_date=None)
        summary = learning_summary(self.path)
        self.assertEqual(summary["confidence"], "collecting")
        self.assertIn("(currently 3)", summary["recommendation"])
        self.assertIn("1 more has no known window coverage and is not compared.", summary["recommendation"])

    def test_cohort_and_baseline_medians_are_per_covered_day(self):
        comparable = {"format": "youtube_shorts", "language": "english", "duration_bucket": "under_60s",
                      "topic_category": "story"}
        videos = [self.linked(views=views, covered_hours=hours)
                  for views, hours in ((300, 25.0), (470, 47.0), (400, 48.0))]
        for link in self.store.published_video_links_list():
            self.store.update_comparable_metadata(int(link["id"]), comparable)
        cohort = self.store.cohort_analytics(format_filter="youtube_shorts", language_filter="english")
        # 300/25h, 470/47h and 400/48h are 288, 240 and 200 views per covered day.
        self.assertEqual(cohort["median_views"], 400.0)
        self.assertEqual(cohort["median_views_per_covered_day"], 240.0)
        self.assertEqual(cohort["covered_sample_size"], 3)
        link = next(item for item in self.store.published_video_links_list() if item["youtube_video_id"] == videos[0])
        baseline = self.store._comparable_snapshot_baseline(
            link, self.store.completed_evidence_snapshot(videos[0], "24h"), comparable)
        # By raw totals the video trails its peers (300 against a median of 435),
        # yet it leads them per covered day (288 against 220): a verdict on this
        # baseline must read the per-day pair.
        self.assertEqual(baseline["median_views"], 435.0)
        self.assertEqual((baseline["views_per_covered_day"], baseline["median_views_per_covered_day"]), (288.0, 220.0))
        self.assertEqual(baseline["covered_sample_size"], 2)


class ContemporaneousMetadataTests(ChannelLearningFixture):
    """A window's result is credited to the title and tags live when it ended."""

    def store_metadata(self, link_id: int, metadata: dict) -> None:
        # Written as stored (metadata observations, contract C6), whichever
        # code path records them.
        with self.store._connect() as connection:
            connection.execute(
                "UPDATE published_video_links SET youtube_metadata_json = ? WHERE id = ?", (json.dumps(metadata), link_id),
            )

    def leading_video_with_observed_metadata(self) -> tuple[str, int]:
        for views in PatternGateTests.SPLIT[:-1]:
            self.linked(views=views)
        video_id = self.linked(views=900, title="Original title")
        link = next(item for item in self.store.published_video_links_list() if item["youtube_video_id"] == video_id)
        # Seen an hour after publication, before the 24h window ended.
        self.original = {"observed_at": (PUBLISHED + timedelta(hours=1)).isoformat(), "title": "Original title",
                         "tags": ["original tag"], "description": None}
        self.store_metadata(int(link["id"]), {"title": "Original title", "tags": ["original tag"],
                                              "observations": [self.original]})
        return video_id, int(link["id"])

    def edit_after_the_window(self, link_id: int) -> None:
        edited = {"observed_at": NOW.isoformat(), "title": "Edited later", "tags": ["edited tag"], "description": None}
        self.store_metadata(link_id, {"title": "Edited later", "tags": ["edited tag"],
                                      "observations": [self.original, edited]})

    def test_editing_title_and_tags_after_the_snapshot_does_not_change_the_writer_example(self):
        video_id, link_id = self.leading_video_with_observed_metadata()
        before = learning_summary(self.path)
        self.assertEqual(before["best_videos"][0]["video_id"], video_id)
        self.assertEqual(before["best_videos"][0]["title_attribution"], "observed")

        self.edit_after_the_window(link_id)
        after = learning_summary(self.path)
        self.assertEqual(after["best_videos"][0], before["best_videos"][0])
        self.assertEqual((after["best_videos"][0]["title"], after["best_videos"][0]["actual_tags"]),
                         ("Original title", ["original tag"]))
        block = self.prompt_block(after)
        self.assertIn('"Original title"', block)
        self.assertIn("original tag", block)
        self.assertNotIn("Edited later", block)
        self.assertNotIn("edited tag", block)

    def test_the_snapshots_own_metadata_counts_when_seen_by_the_windows_end(self):
        video_id = self.linked(views=500, title="Confirmed title")
        recorded = {"observed_at": (PUBLISHED + timedelta(hours=2)).isoformat(), "title": "Live at the time",
                    "tags": ["then"], "description": None, "published_at": None, "privacy_status": None}
        self.set_snapshot(video_id, metadata_json=json.dumps(recorded))
        evidence = self.evidence(video_id)
        self.assertEqual((evidence["title"], evidence["actual_tags"], evidence["title_attribution"]),
                         ("Live at the time", ["then"], "observed"))

    def test_metadata_seen_only_after_the_window_with_a_later_edit_is_not_attributed(self):
        video_id = self.linked(views=500, title="Confirmed title")
        recorded = {"observed_at": NOW.isoformat(), "title": "Confirmed title", "tags": ["then"]}
        self.set_snapshot(video_id, metadata_json=json.dumps(recorded))
        link = next(item for item in self.store.published_video_links_list() if item["youtube_video_id"] == video_id)
        self.store.update_linked_video_metadata(int(link["id"]), {"title": "Confirmed title", "tags": ["edited"]})
        evidence = self.evidence(video_id)
        self.assertEqual((evidence["title"], evidence["actual_tags"], evidence["title_attribution"]),
                         (None, None, "unknown"))

    def test_a_legacy_link_still_showing_its_confirmed_title_is_assumed_unchanged(self):
        video_id = self.linked(views=500, title="Confirmed title")
        evidence = self.evidence(video_id)
        self.assertEqual((evidence["title"], evidence["title_attribution"]), ("Confirmed title", "assumed_unchanged"))

    def test_a_legacy_link_edited_in_one_digit_is_not_assumed_unchanged(self):
        video_id = self.linked(views=500, title="Top 5 study hacks")
        link = next(item for item in self.store.published_video_links_list() if item["youtube_video_id"] == video_id)
        # Legacy shape: the current metadata only, no observations.
        self.store_metadata(int(link["id"]), {"title": "Top 7 study hacks", "tags": ["study"]})
        evidence = self.evidence(video_id)
        self.assertEqual((evidence["title"], evidence["actual_tags"], evidence["title_attribution"]),
                         (None, None, "unknown"))

    def test_a_record_by_the_windows_end_without_a_title_credits_neither_title_nor_tags(self):
        video_id = self.linked(views=500, title="Confirmed title")
        recorded = {"observed_at": (PUBLISHED + timedelta(hours=2)).isoformat(), "title": None, "tags": ["then"]}
        self.set_snapshot(video_id, metadata_json=json.dumps(recorded))
        evidence = self.evidence(video_id)
        self.assertEqual((evidence["title"], evidence["actual_tags"], evidence["title_attribution"]),
                         (None, None, "unknown"))

    def test_a_legacy_link_retitled_since_linking_counts_but_is_not_a_writer_example(self):
        for views in PatternGateTests.SPLIT[:-1]:
            self.linked(views=views)
        video_id = self.linked(views=900, title="Confirmed title")
        link = next(item for item in self.store.published_video_links_list() if item["youtube_video_id"] == video_id)
        self.store.update_linked_video_metadata(int(link["id"]), {"title": "Retitled later", "tags": ["new tag"]})
        summary = learning_summary(self.path)
        self.assertEqual(summary["sample_size"], 10)
        leading = summary["best_videos"][0]
        self.assertEqual((leading["video_id"], leading["views"]), (video_id, 900))
        self.assertEqual((leading["title"], leading["actual_tags"], leading["title_attribution"]),
                         (None, None, "unknown"))
        block = self.prompt_block(summary)
        self.assertNotIn("Retitled later", block)
        self.assertNotIn("new tag", block)


class EvidencePolicyUnknownTests(ChannelLearningFixture):
    def test_unknown_is_not_comparable_metadata(self):
        self.assertTrue(comparable_metadata({"format": "youtube_shorts", "language": "english"}))
        for link in ({"format": "unknown", "language": "english"}, {"format": "youtube_shorts", "language": "unknown"},
                     {"format": " ", "language": "english"}, {"format": "youtube_shorts"}):
            self.assertFalse(comparable_metadata(link), link)

        verified = {"ownership_state": "verified", "ownership_verified": True, "verified_channel_id": "owner",
                    "ownership_verified_at": NOW.isoformat(), "format": "youtube_shorts", "language": "unknown"}
        snapshot = {"snapshot_window": "24h", "snapshot_status": "complete", "completed_at": NOW.isoformat(), "views": 10}
        self.assertFalse(sample_is_eligible(verified, snapshot, expected_window="24h", connected_channel_id="owner"))
        self.assertTrue(sample_is_eligible({**verified, "language": "english"}, snapshot, expected_window="24h",
                                           connected_channel_id="owner"))

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
