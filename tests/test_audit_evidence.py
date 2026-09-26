"""Regression tests for audit evidence labels, peer cohorts and experiment updates."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone

from win_engine.feedback.audit_experiment_store import AuditExperimentStore
from win_engine.feedback.history_store import HistoryStore


class AuditFixture(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.path = handle.name
        handle.close()
        self.history = HistoryStore(self.path)
        self.store = AuditExperimentStore(self.history)
        self.counter = 0

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(self.path + suffix)
            except OSError:
                pass

    def link(self, *, published_at: str = "2026-08-20T00:00:00+00:00", verified: bool = True) -> tuple[int, int, str]:
        self.counter += 1
        video_id = f"fixfaudit{self.counter:02d}"
        run_id = self.history.record_analysis_run(
            f"camera script {self.counter}", "SEARCH", "camera", f"Title {self.counter}", 8, "medium", "WORKABLE", 60,
            payload={"title": f"Title {self.counter}"},
        )
        link_id = self.history.link_published_video(
            run_id, video_id, published_at, format_val="youtube_shorts", language="english",
            ownership_state="verified" if verified else "unverified", ownership_verified=verified,
            verified_channel_id="owner" if verified else None,
            ownership_verified_at=datetime.now(timezone.utc).isoformat() if verified else None,
        )
        return run_id, link_id, video_id

    def complete_24h(self, video_id: str, views: int = 100) -> None:
        self.history.record_performance_snapshot(
            video_id, 24, views=views, likes=5, comments=1, avg_view_percentage=60, snapshot_window="24h"
        )

    def evidence_state(self, link_id: int) -> str:
        return next(item for item in self.store.audit_candidates() if item["id"] == link_id)["evidence_state"]


class AuditEvidenceStateTests(AuditFixture):
    def test_failed_retry_after_current_counts_is_observed_not_mature(self):
        _, link_id, video_id = self.link()
        self.history.record_performance_snapshot(video_id, 190, views=50, snapshot_window="current", replace_window=True)
        self.history.record_snapshot_attempt(video_id, "7d", status="failed_retryable", failure_reason="analytics_request_failed")

        self.assertEqual(self.evidence_state(link_id), "observed")

    def test_completed_window_stays_mature_after_a_later_current_refresh(self):
        _, link_id, video_id = self.link()
        self.complete_24h(video_id)
        self.history.record_performance_snapshot(video_id, 900, views=5000, snapshot_window="current", replace_window=True)

        self.assertEqual(self.evidence_state(link_id), "mature")

    def test_attempts_without_any_views_are_unavailable(self):
        _, link_id, video_id = self.link()
        self.history.record_snapshot_attempt(video_id, "24h", status="failed_retryable", failure_reason="analytics_request_failed")

        self.assertEqual(self.evidence_state(link_id), "unavailable")

    def test_evidence_state_filter_uses_completed_windows(self):
        _, mature_link, mature_video = self.link()
        self.complete_24h(mature_video)
        _, observed_link, observed_video = self.link()
        self.history.record_performance_snapshot(observed_video, 5, views=20, snapshot_window="current")
        self.history.record_snapshot_attempt(observed_video, "24h", status="empty_retryable", failure_reason="analytics_returned_no_rows")

        self.assertEqual([item["id"] for item in self.store.audit_candidates(evidence_state="mature")], [mature_link])
        self.assertEqual([item["id"] for item in self.store.audit_candidates(evidence_state="observed")], [observed_link])


class AuditPeerCohortTests(AuditFixture):
    def mature_links(self, count: int) -> list[int]:
        links = []
        for index in range(count):
            _, link_id, video_id = self.link()
            self.complete_24h(video_id, views=100 + index)
            links.append(link_id)
        return links

    def test_audited_video_does_not_count_toward_its_own_threshold(self):
        audited = self.mature_links(5)[-1]

        cohort = self.store._audit_context(audited)["cohort"]
        self.assertEqual(cohort["sample_size"], 4)
        self.assertFalse(cohort["learning_allowed"])
        self.assertEqual(cohort["confidence_label"], "Collecting evidence")

        audit = self.store.refresh_audit(audited)
        self.assertEqual(audit["evidence"]["cohort"]["sample_size"], 4)
        self.assertNotEqual(audit["summary"]["state"], "actionable_observation")

    def test_five_peers_allow_learning(self):
        audited = self.mature_links(6)[-1]

        cohort = self.store._audit_context(audited)["cohort"]
        self.assertEqual(cohort["sample_size"], 5)
        self.assertTrue(cohort["learning_allowed"])
        self.assertEqual(cohort["confidence_level"], "early_signal")

    def test_video_outside_the_cohort_keeps_the_full_peer_count(self):
        self.mature_links(5)
        _, collecting, _ = self.link()  # no completed window yet
        _, unverified, unverified_video = self.link(verified=False)
        self.complete_24h(unverified_video)

        for link_id in (collecting, unverified):
            cohort = self.store._audit_context(link_id)["cohort"]
            self.assertEqual(cohort["sample_size"], 5)
            self.assertTrue(cohort["learning_allowed"])


class AuditPrePublishResearchTests(AuditFixture):
    def research_at(self, run_id: int, *captured: str) -> None:
        with sqlite3.connect(self.path) as connection:
            idea_id = connection.execute(
                "INSERT INTO content_ideas(topic,analysis_run_id,created_at,updated_at) VALUES('topic',?,'t','t')", (run_id,)
            ).lastrowid
            for captured_at in captured:
                connection.execute(
                    "INSERT INTO content_idea_research_snapshots(content_idea_id,captured_at,evidence_json) VALUES(?,?,'{}')",
                    (idea_id, captured_at),
                )
                connection.execute(
                    "INSERT INTO demand_research_snapshots(idea_id,topic,classification,evidence_json,captured_at) VALUES(?,?,?,?,?)",
                    (idea_id, "topic", "active_topic", "{}", captured_at),
                )

    def test_offset_publish_time_is_compared_as_an_instant(self):
        # 10:00+05:30 is 04:30Z, so research saved at 06:00Z came after publication.
        run_id, link_id, _ = self.link(published_at="2026-08-01T10:00:00+05:30")
        self.research_at(run_id, "2026-08-01T06:00:00+00:00")

        context = self.store._audit_context(link_id)
        self.assertIsNone(context["idea_research"])
        self.assertIsNone(context["demand_research"])

    def test_latest_research_before_publication_is_used(self):
        run_id, link_id, _ = self.link(published_at="2026-08-01T10:00:00+05:30")
        self.research_at(run_id, "2026-08-01T03:00:00+00:00", "2026-08-01T04:00:00+00:00", "2026-08-01T06:00:00+00:00")

        context = self.store._audit_context(link_id)
        self.assertEqual(context["idea_research"]["captured_at"], "2026-08-01T04:00:00+00:00")
        self.assertEqual(context["demand_research"]["captured_at"], "2026-08-01T04:00:00+00:00")

    def test_unreadable_publish_time_claims_no_pre_publish_research(self):
        run_id, link_id, _ = self.link(published_at="sometime last week")
        self.research_at(run_id, "2026-08-01T04:00:00+00:00")

        context = self.store._audit_context(link_id)
        self.assertIsNone(context["idea_research"])
        self.assertIsNone(context["demand_research"])


class ExperimentUpdateValidationTests(AuditFixture):
    def experiment(self, **overrides):
        values = {
            "name": "Title test", "hypothesis": "Specific titles hold attention.", "variable": "title_mechanism",
            "control_definition": "descriptive", "variant_definition": "specific", "minimum_sample_size": 5,
            "target_sample_size": 10,
        }
        values.update(overrides)
        return self.store.create_experiment(values)

    def advance(self, experiment_id: int, *statuses: str) -> None:
        for status in statuses:
            self.store.update_experiment(experiment_id, {"status": status})

    def test_target_sample_size_must_cover_both_groups(self):
        item = self.experiment()
        with self.assertRaisesRegex(ValueError, "Target sample size"):
            self.store.update_experiment(item["id"], {"target_sample_size": 2})
        self.assertEqual(self.store.experiment(item["id"])["target_sample_size"], 10)
        self.assertEqual(self.store.update_experiment(item["id"], {"target_sample_size": 12})["target_sample_size"], 12)

    def test_hypothesis_can_change_only_before_the_experiment_runs(self):
        item = self.experiment()
        self.assertEqual(self.store.update_experiment(item["id"], {"hypothesis": "Draft wording."})["hypothesis"], "Draft wording.")
        self.advance(item["id"], "planned")
        self.assertEqual(self.store.update_experiment(item["id"], {"hypothesis": "Planned wording."})["hypothesis"], "Planned wording.")
        self.advance(item["id"], "active")

        with self.assertRaisesRegex(ValueError, "hypothesis cannot change"):
            self.store.update_experiment(item["id"], {"hypothesis": "Rewritten while running."})
        # Sending the unchanged hypothesis back, as a full form save would, is not a change.
        self.assertEqual(self.store.update_experiment(item["id"], {"hypothesis": "Planned wording.", "notes": "n"})["notes"], "n")

        self.advance(item["id"], "completed")
        with self.assertRaisesRegex(ValueError, "hypothesis cannot change"):
            self.store.update_experiment(item["id"], {"hypothesis": "Rewritten after completion."})
        self.assertEqual(self.store.experiment(item["id"])["hypothesis"], "Planned wording.")

    def test_dates_must_be_iso_and_ordered(self):
        item = self.experiment()
        with self.assertRaisesRegex(ValueError, "ISO date"):
            self.store.update_experiment(item["id"], {"start_date": "next Monday"})
        with self.assertRaisesRegex(ValueError, "end date cannot be before"):
            self.store.update_experiment(item["id"], {"start_date": "2026-09-10", "end_date": "2026-09-01"})

        updated = self.store.update_experiment(item["id"], {"start_date": "2026-09-01", "end_date": "2026-09-10T18:00:00+05:30"})
        self.assertEqual((updated["start_date"], updated["end_date"]), ("2026-09-01", "2026-09-10T18:00:00+05:30"))
        # The stored start date still bounds a later change to the end date alone.
        with self.assertRaisesRegex(ValueError, "end date cannot be before"):
            self.store.update_experiment(item["id"], {"end_date": "2026-08-31"})

    def test_duplicate_assignment_is_reported_and_other_integrity_errors_are_not_masked(self):
        item = self.experiment()
        _, link_id, _ = self.link()
        self.store.assign_video(item["id"], link_id, "control")
        with self.assertRaisesRegex(ValueError, "already assigned"):
            self.store.assign_video(item["id"], link_id, "variant")

        _, other_link, _ = self.link()
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.assign_video(item["id"], other_link, "not_a_role")


if __name__ == "__main__":
    unittest.main()
