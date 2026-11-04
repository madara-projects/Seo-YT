"""Personal learning reads only the linked videos of the channel connected now.

A link keeps its verification when the creator switches channels or
disconnects (reconnecting and cloud sync rely on it), so every learning read
has to check whose channel it was verified for: learning_summary, the cohort,
the comparable baseline, retention learning, score calibration, the writer's
prompt and the anti-repetition title history.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from win_engine.feedback.channel_learning import learning_summary
from win_engine.feedback.evidence_policy import sample_is_eligible, verified_for_another_channel, verified_ownership
from win_engine.feedback.history_store import NO_CONNECTED_CHANNEL_REASON, HistoryStore
from win_engine.feedback.score_calibration import opportunity_score_calibration
from win_engine.generation import strategy_engine
from win_engine.llm import seo_writer

NOW = datetime.now(timezone.utc)
OLD, NEW = "UC-OLDCHAN", "UC-NEWCHAN"
# Ten videos whose top three lead the rest by far more than the pattern margin,
# so the old channel's leading videos reach the writer while it is connected.
SPLIT = (100, 110, 120, 130, 140, 150, 160, 400, 420, 450)
PHASE5 = {"rule_version": "phase5-v1", "opening": {"clarity": "clear"},
          "pacing": {"format_assessment": "fits_short"}, "quote_presentation": {"status": "available"}}
COMPARABLE = {"duration_bucket": "under_60s", "topic_category": "habits"}


class _ChannelScopeFixture(unittest.TestCase):
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

    def connect(self, channel_id: str) -> None:
        # What YouTubeChannelService._save_connection stores, without OAuth.
        with self.store._connect() as connection:
            connection.execute(
                """INSERT INTO youtube_channel_connection
                   (id, encrypted_refresh_token, channel_id, channel_title, connected_at, updated_at)
                   VALUES (1, 'token', ?, 'Channel', ?, ?)
                   ON CONFLICT(id) DO UPDATE SET channel_id = excluded.channel_id""",
                (channel_id, NOW.isoformat(), NOW.isoformat()),
            )

    def disconnect(self) -> None:
        # What YouTubeChannelService.disconnect does to the connection.
        with self.store._connect() as connection:
            connection.execute("DELETE FROM youtube_channel_connection WHERE id = 1")

    def linked(self, views: int, channel: str, label: str) -> dict:
        """A link verified for `channel` with a completed 24h window and full comparable labels."""
        self.counter += 1
        title = f"{label} video {self.counter}"
        run_id = self.store.record_analysis_run(
            f"query {self.counter}", "SEARCH", "story", title, 7, "LOW", "WORKABLE", 40 + self.counter,
            payload={"title": title, "retention_assistant": PHASE5},
        )
        video_id = f"{label.lower()}vid{self.counter:03d}"
        link_id = self.store.link_published_video(
            run_id, video_id, (NOW - timedelta(days=4)).isoformat(), format_val="youtube_shorts",
            language="english", ownership_state="verified", ownership_verified=True,
            verified_channel_id=channel, ownership_verified_at=NOW.isoformat(),
        )
        self.store.update_comparable_metadata(link_id, COMPARABLE)
        self.store.update_linked_video_metadata(link_id, {"title": title, "tags": [f"{label.lower()}tag"]})
        self.store.record_performance_snapshot(
            video_id, 24, views=views, likes=3, comments=1, avg_view_percentage=50.0 + self.counter,
            snapshot_window="24h",
        )
        return self.store.published_video_link(link_id) or {}

    def old_channel_history(self) -> list[dict]:
        self.connect(OLD)
        return [self.linked(views, OLD, "OLD") for views in SPLIT]

    def baseline(self, link: dict) -> dict:
        latest = self.store.completed_evidence_snapshot(link["youtube_video_id"], "24h")
        comparable = self.store.comparable_metadata(int(link["id"])) or {}
        return self.store._comparable_snapshot_baseline(link, latest, comparable)

    def writer_inputs(self) -> tuple[dict, str]:
        """The channel learning build_seo_package hands the writer, and the prompt built from it."""
        captured: dict = {}

        class Stop(Exception):
            pass

        def fake_writer(script, **kwargs):
            captured["channel_learning"] = kwargs["channel_learning"]
            captured["prompt"] = seo_writer._build_user_prompt(
                script, "", "english", "global", "general",
                creator_brief=kwargs.get("creator_brief"), channel_learning=kwargs["channel_learning"],
            )
            raise Stop()

        research = {"language_context": {"language": "english"},
                    "creator_brief": {"video_format": "youtube_shorts", "topic": "morning habits"},
                    "main_topic": "morning habits"}
        with patch.object(strategy_engine, "write_multilang_packages_with_source", side_effect=fake_writer):
            with self.assertRaises(Stop):
                strategy_engine.build_seo_package(
                    "SEARCH", "A short about morning habits that stick.", research, self.store,
                )
        return captured["channel_learning"], captured["prompt"]

    def assert_no_old_channel_learning(self, old_links: list[dict], *, baseline_reason: str) -> None:
        summary = learning_summary(self.path, format_filter="youtube_shorts", language_filter="english")
        self.assertEqual(summary["sample_size"], 0)
        self.assertFalse(summary["learning_allowed"])
        self.assertEqual(summary["linked_evidence"], [])
        self.assertEqual((summary["best_videos"], summary["weakest_videos"]), ([], []))
        self.assertEqual(summary["linked_video_count"], 0)

        cohort = self.store.cohort_analytics(format_filter="youtube_shorts", language_filter="english")
        self.assertEqual(cohort["sample_size"], 0)
        self.assertFalse(cohort["learning_allowed"])
        self.assertIsNone(cohort["median_views"])
        # Another channel's links are not ones this channel's cohort left out.
        self.assertEqual((cohort["total_links_considered"], cohort["excluded_count"]), (0, 0))

        baseline = self.baseline(old_links[0])
        self.assertEqual(baseline["sample_size"], 0)
        self.assertIsNone(baseline["median_views"])
        # Why there are no peers, so the report does not say "not yet five".
        self.assertEqual(baseline["unavailable_reason"], baseline_reason)

        retention = self.store.retention_learning_summary(format_filter="youtube_shorts", language_filter="english")
        self.assertEqual((retention["status"], retention["sample_size"]), ("insufficient_evidence", 0))
        self.assertFalse(retention["learning_allowed"])
        self.assertEqual(retention["patterns"], [])

        self.assertEqual(self.store.recent_published_titles(), [])

        calibration = opportunity_score_calibration(self.store, "24h")
        self.assertEqual(calibration["windows"]["24h"], 0)
        # Another channel's links are neither considered nor called "not
        # ownership-verified": they are verified, for that channel.
        self.assertEqual(calibration["links_considered"], 0)
        self.assertEqual(set(calibration["excluded"].values()), {0})

        channel_learning, prompt = self.writer_inputs()
        self.assertEqual(channel_learning["best_videos"], [])
        self.assertEqual(channel_learning["published_titles"], [])
        self.assertEqual(channel_learning["cohort"]["sample_size"], 0)
        self.assertNotIn("OLD video", prompt)
        self.assertNotIn("oldtag", prompt)

        # Nothing was unverified or deleted: reconnecting must count them again.
        for link in old_links:
            stored = self.store.published_video_link(int(link["id"])) or {}
            self.assertEqual((stored["ownership_state"], stored["verified_channel_id"]), ("verified", OLD))
            self.assertTrue(stored["ownership_verified"])


class ConnectedChannelScopeTests(_ChannelScopeFixture):
    def test_the_connected_channels_history_is_learned_from(self):
        old_links = self.old_channel_history()
        summary = learning_summary(self.path, format_filter="youtube_shorts", language_filter="english")
        self.assertEqual(summary["sample_size"], 10)
        self.assertTrue(summary["learning_allowed"])
        self.assertEqual(len(summary["best_videos"]), 3)
        self.assertEqual(self.store.cohort_analytics(format_filter="youtube_shorts", language_filter="english")["sample_size"], 10)
        baseline = self.baseline(old_links[0])
        self.assertEqual((baseline["sample_size"], baseline["unavailable_reason"]), (9, None))
        self.assertEqual(self.store.retention_learning_summary(format_filter="youtube_shorts", language_filter="english")["sample_size"], 10)
        self.assertEqual(len(self.store.recent_published_titles()), 10)
        channel_learning, prompt = self.writer_inputs()
        self.assertEqual(len(channel_learning["best_videos"]), 3)
        self.assertIn("OLD video", prompt)

    def test_switching_channels_leaves_the_old_channel_out_of_learning(self):
        old_links = self.old_channel_history()
        self.connect(NEW)
        self.assert_no_old_channel_learning(old_links, baseline_reason="verified_for_another_channel")
        summary = learning_summary(self.path, format_filter="youtube_shorts", language_filter="english")
        self.assertNotEqual(summary["recommendation"], NO_CONNECTED_CHANNEL_REASON)

    def test_disconnecting_leaves_no_personal_learning_with_an_honest_reason(self):
        old_links = self.old_channel_history()
        self.disconnect()
        self.assert_no_old_channel_learning(old_links, baseline_reason="no_channel_connected")
        summary = learning_summary(self.path, format_filter="youtube_shorts", language_filter="english")
        self.assertEqual(summary["recommendation"], NO_CONNECTED_CHANNEL_REASON)
        self.assertEqual(summary["confidence"], "collecting")
        retention = self.store.retention_learning_summary(format_filter="youtube_shorts", language_filter="english")
        self.assertEqual(retention["message"], NO_CONNECTED_CHANNEL_REASON)
        cohort = self.store.cohort_analytics(format_filter="youtube_shorts", language_filter="english")
        self.assertEqual(cohort["recommendation"], NO_CONNECTED_CHANNEL_REASON)

    def test_reconnecting_the_original_channel_restores_its_evidence(self):
        old_links = self.old_channel_history()
        self.connect(NEW)
        self.disconnect()
        self.connect(OLD)
        summary = learning_summary(self.path, format_filter="youtube_shorts", language_filter="english")
        self.assertEqual(summary["sample_size"], 10)
        self.assertEqual(len(summary["best_videos"]), 3)
        self.assertEqual(self.store.cohort_analytics(format_filter="youtube_shorts", language_filter="english")["sample_size"], 10)
        self.assertEqual(self.baseline(old_links[0])["sample_size"], 9)
        self.assertEqual(self.store.retention_learning_summary(format_filter="youtube_shorts", language_filter="english")["sample_size"], 10)
        self.assertEqual(len(self.store.recent_published_titles()), 10)
        self.assertEqual(opportunity_score_calibration(self.store, "24h")["windows"]["24h"], 10)

    def test_the_new_channel_learns_only_from_its_own_videos(self):
        old_links = self.old_channel_history()
        self.connect(NEW)
        new_links = [self.linked(views, NEW, "NEW") for views in (90, 95)]
        # Nor is an old-channel video compared with the new channel's videos,
        # and its report's baseline says why rather than that peers are too few.
        report = self.store.linked_package_report(int(old_links[0]["analysis_run_id"]))
        self.assertEqual(
            (report["baseline"]["sample_size"], report["baseline"]["unavailable_reason"]),
            (0, "verified_for_another_channel"),
        )
        summary = learning_summary(self.path, format_filter="youtube_shorts", language_filter="english")
        self.assertEqual({item["video_id"] for item in summary["linked_evidence"]},
                         {link["youtube_video_id"] for link in new_links})
        self.assertEqual(summary["linked_video_count"], 2)
        cohort = self.store.cohort_analytics(format_filter="youtube_shorts", language_filter="english")
        self.assertEqual((cohort["sample_size"], cohort["total_links_considered"]), (2, 2))
        baseline = self.baseline(new_links[0])
        self.assertEqual((baseline["sample_size"], baseline["unavailable_reason"]), (1, None))
        self.assertEqual(sorted(self.store.recent_published_titles()), ["NEW video 11", "NEW video 12"])
        channel_learning, prompt = self.writer_inputs()
        self.assertEqual(sorted(channel_learning["published_titles"]), ["NEW video 11", "NEW video 12"])
        self.assertNotIn("OLD video", prompt)

    def test_the_sql_and_python_other_channel_rules_agree(self):
        links = self.old_channel_history() + [self.linked(90, NEW, "NEW")]
        for state in (OLD, NEW, f"  {OLD}  ", "", None):
            with self.subTest(connected=state):
                if state is None:
                    self.disconnect()
                else:
                    self.connect(state)
                channel_id = self.store.connected_channel_id()
                expected = {
                    int(link["analysis_run_id"]) for link in links
                    if verified_for_another_channel(link, connected_channel_id=channel_id)
                }
                self.assertEqual(self.store.runs_published_on_other_channels(), expected)


class OwnershipPolicyTests(unittest.TestCase):
    LINK = {"ownership_state": "verified", "ownership_verified": True, "verified_channel_id": OLD,
            "ownership_verified_at": NOW.isoformat(), "format": "youtube_shorts", "language": "english"}
    SNAPSHOT = {"snapshot_window": "24h", "snapshot_status": "complete", "completed_at": NOW.isoformat(), "views": 10}

    def test_ownership_counts_only_for_the_connected_channel(self):
        self.assertTrue(verified_ownership(self.LINK, connected_channel_id=OLD))
        self.assertTrue(verified_ownership(self.LINK, connected_channel_id=f" {OLD} "))
        self.assertFalse(verified_ownership(self.LINK, connected_channel_id=NEW))
        self.assertFalse(verified_ownership(self.LINK, connected_channel_id=None))
        self.assertFalse(verified_ownership(self.LINK, connected_channel_id=""))
        self.assertFalse(verified_ownership({**self.LINK, "verified_channel_id": ""}, connected_channel_id=""))

    def test_only_a_link_verified_for_another_channel_is_another_channels(self):
        self.assertFalse(verified_for_another_channel(self.LINK, connected_channel_id=f" {OLD} "))
        self.assertTrue(verified_for_another_channel(self.LINK, connected_channel_id=NEW))
        self.assertTrue(verified_for_another_channel(self.LINK, connected_channel_id=None))
        # An unverified link is most likely the creator's own, whatever is connected.
        for channel in (OLD, None):
            self.assertFalse(verified_for_another_channel({**self.LINK, "verified_channel_id": " "}, connected_channel_id=channel))

    def test_a_sample_is_eligible_only_for_the_connected_channel(self):
        self.assertTrue(sample_is_eligible(self.LINK, self.SNAPSHOT, expected_window="24h", connected_channel_id=OLD))
        self.assertFalse(sample_is_eligible(self.LINK, self.SNAPSHOT, expected_window="24h", connected_channel_id=NEW))
        self.assertFalse(sample_is_eligible(self.LINK, self.SNAPSHOT, expected_window="24h", connected_channel_id=None))


if __name__ == "__main__":
    unittest.main()
