"""Eligibility and personalization messages say what was used, and no more.

A cohort's size is not a pattern, a pooled cohort is not one comparable
cohort, and a video generation counts must not read as one it ignores.
"""

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from win_engine.analysis.audit_experiment import build_published_audit
from win_engine.analysis.generation_quality import evidence_trace
from win_engine.api import routes
from win_engine.core.config import Settings
from win_engine.feedback.evidence_policy import confidence_payload, evidence_level
from win_engine.feedback.history_store import HistoryStore
from win_engine.generation.strategy_engine import build_seo_package

NOW = datetime.now(timezone.utc)


def _learning(sample_size: int, pattern_status: str, best_videos: list[dict] | None = None) -> dict:
    level = evidence_level(sample_size)
    return {
        "learning_allowed": level.learning_allowed,
        "confidence_label": level.label,
        "pattern_signal": {"status": pattern_status, "reason": f"the reason for {pattern_status}."},
        "best_videos": best_videos or [],
        "cohort": {
            "learning_allowed": level.learning_allowed, "sample_size": sample_size,
            "confidence_label": level.label, "snapshot_window": "24h",
        },
    }


class TierLabelTests(unittest.TestCase):
    def test_labels_describe_the_sample_size_only(self):
        self.assertEqual(
            [(evidence_level(n).key, evidence_level(n).label) for n in (0, 5, 10, 38)],
            [
                ("display_only", "Collecting evidence"),
                ("early_signal", "Early signal (5+ videos)"),
                ("moderate_evidence", "Moderate sample (10+ videos)"),
                ("strong_evidence", "Large sample (20+ videos)"),
            ],
        )
        self.assertNotIn("pattern", confidence_payload(38)["confidence_label"].lower())


class EvidenceTraceTests(unittest.TestCase):
    def test_a_large_cohort_without_a_pattern_supplies_context_only(self):
        # The user's channel: 38 comparable Shorts whose leaders are within noise.
        trace = evidence_trace(_learning(38, "no_pattern"), generation_source="gemini")
        self.assertEqual(trace["status"], "context_only")
        self.assertEqual(trace["pattern_status"], "no_pattern")
        self.assertEqual(trace["examples_supplied"], 0)
        self.assertEqual(trace["sample_size"], 38)
        self.assertEqual(trace["generation_source"], "gemini")
        self.assertNotIn("pattern", trace["confidence"].lower())
        self.assertIn("No example videos were shown to the writer", trace["message"])

    def test_context_only_names_only_what_the_writer_was_given(self):
        learning = _learning(38, "no_pattern")
        bare = evidence_trace(learning, generation_source="gemini")["message"]
        self.assertTrue(bare.endswith("It was given only the cohort's size."), bare)
        learning.update(recommendation="No linked-video pattern was applied: noise.", recent_titles=["Old title"])
        full = evidence_trace(learning, generation_source="gemini")["message"]
        self.assertTrue(full.endswith(
            "It was given only the cohort's size, the pattern check's finding and your recent titles to avoid repeating."
        ), full)

    def test_insufficient_evidence_names_the_window_counted(self):
        trace = evidence_trace(_learning(3, "insufficient_sample"), generation_source="gemini")
        self.assertIn("have a completed 24h window (3)", trace["message"])

    def test_examples_are_counted_only_when_the_pattern_gate_passed(self):
        leaders = [{"title": "First"}, {"title": "Second"}, {"title": " "}]
        trace = evidence_trace(_learning(12, "pattern", leaders), generation_source="gemini")
        self.assertEqual((trace["status"], trace["examples_supplied"]), ("examples_supplied", 2))
        self.assertEqual(trace["evidence_source"], "comparable_owned_video_cohort")

    def test_a_small_cohort_is_insufficient_evidence(self):
        trace = evidence_trace(_learning(4, "insufficient_sample"), generation_source="gemini")
        self.assertEqual((trace["status"], trace["examples_supplied"]), ("insufficient_evidence", 0))
        self.assertEqual(trace["evidence_source"], "none")

    def test_a_package_the_local_fallback_wrote_applied_no_evidence(self):
        leaders = [{"title": "First"}, {"title": "Second"}, {"title": "Third"}]
        trace = evidence_trace(_learning(25, "pattern", leaders), generation_source="fallback")
        self.assertEqual((trace["status"], trace["examples_supplied"]), ("not_applied", 0))
        self.assertEqual(trace["generation_source"], "fallback")
        self.assertEqual(trace["evidence_source"], "none")


class StoreFixture(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        self.path = handle.name
        self.store = HistoryStore(self.path)
        self.count = 0
        # Learning counts only the connected channel's videos, so the channel
        # these links are verified for is the connected one.
        with self.store._connect() as connection:
            connection.execute(
                "INSERT INTO youtube_channel_connection (id, encrypted_refresh_token, channel_id, channel_title, connected_at, updated_at) "
                "VALUES (1, 'token', 'owner', 'Owner', '2026-08-01T00:00:00Z', '2026-08-01T00:00:00Z')"
            )

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(self.path + suffix)
            except OSError:
                pass

    def linked(self, *, format_val: str = "youtube_shorts", language: str = "english", views: int = 100,
               labels: dict | None = None) -> tuple[int, int, str]:
        self.count += 1
        run_id = self.store.record_analysis_run(
            f"query {self.count}", "SEARCH", "story", f"Upload {self.count}", 7, "LOW", "WORKABLE", 50,
            payload={"title": f"Upload {self.count}", "tags": ["alpha"]},
        )
        video_id = f"truth{self.count:06d}"
        link_id = self.store.link_published_video(
            run_id, video_id, (NOW - timedelta(days=40)).isoformat(), format_val=format_val, language=language,
            ownership_state="verified", ownership_verified=True, verified_channel_id="owner",
            ownership_verified_at=NOW.isoformat(),
        )
        if labels:
            self.store.update_comparable_metadata(link_id, labels)
        self.store.record_performance_snapshot(
            video_id, 24, views=views, likes=5, comments=1, avg_view_percentage=60.0, snapshot_window="24h",
        )
        return run_id, link_id, video_id


class DiagnosisTests(StoreFixture):
    def test_a_video_generation_counts_says_so_without_a_peer_baseline(self):
        # Format and language known, length and topic not: generation's rule
        # counts it, the stricter peer baseline cannot be computed.
        run_id, _, _ = self.linked()
        diagnosis = self.store.linked_package_report(run_id)["diagnosis"]
        self.assertTrue(diagnosis["counts_toward_generation"])
        self.assertFalse(diagnosis["learning_eligible"])
        self.assertFalse(diagnosis["peer_baseline_available"])
        self.assertEqual(diagnosis["window"], "24h")
        self.assertIsNone(diagnosis["baseline_sample_size"])
        self.assertIn("comparable label is unknown", diagnosis["verdict"])

    def test_known_labels_with_too_few_peers_report_the_peer_count(self):
        labels = {"duration_bucket": "under_60s", "topic_category": "quotes"}
        for _ in range(2):
            self.linked(labels=labels)
        run_id, _, _ = self.linked(labels=labels)
        diagnosis = self.store.linked_package_report(run_id)["diagnosis"]
        self.assertTrue(diagnosis["counts_toward_generation"])
        self.assertEqual(diagnosis["baseline_sample_size"], 2)
        self.assertFalse(diagnosis["peer_baseline_available"])
        # Peers count only at the same completed window, so the message names it.
        self.assertIn("at the same completed 24h window (2 do)", " ".join(diagnosis["needs_improvement"]))
        self.assertEqual(
            diagnosis["verdict"],
            "NO PEER BASELINE — too few peers of the same format, language, length and topic at the 24h window",
        )

    def test_five_matching_peers_give_a_baseline(self):
        labels = {"duration_bucket": "under_60s", "topic_category": "quotes"}
        for _ in range(5):
            self.linked(labels=labels)
        run_id, _, _ = self.linked(labels=labels, views=1000)
        diagnosis = self.store.linked_package_report(run_id)["diagnosis"]
        self.assertTrue(diagnosis["peer_baseline_available"])
        self.assertTrue(diagnosis["learning_eligible"])
        self.assertEqual(diagnosis["baseline_sample_size"], 5)
        self.assertEqual(diagnosis["verdict"], "ABOVE BASELINE")

    def test_an_unverified_video_does_not_count_toward_generation(self):
        run_id, link_id, _ = self.linked()
        with self.store._connect() as connection:
            connection.execute("UPDATE published_video_links SET ownership_state = 'unverified', ownership_verified = 0 WHERE id = ?", (link_id,))
        self.assertFalse(self.store.linked_package_report(run_id)["diagnosis"]["counts_toward_generation"])


class CohortRouteTests(StoreFixture):
    def cohorts(self, **filters):
        with patch.object(routes, "get_settings", return_value=Settings(database_path=self.path)):
            return routes.get_cohort_analytics(**{
                "format": None, "language": None, "duration_bucket": None, "topic_category": None,
                "window": "24h", "traffic_source": None, **filters,
            })

    def test_a_pooled_cohort_says_it_is_mixed_and_lists_its_parts(self):
        for _ in range(3):
            self.linked(format_val="youtube_shorts", language="english")
        for _ in range(2):
            self.linked(format_val="youtube_shorts", language="tamil")
        pooled = self.cohorts()
        self.assertEqual(pooled["sample_size"], 5)
        self.assertEqual(pooled["cohort_scope"], "mixed")
        self.assertEqual(
            [(item["format"], item["language"], item["sample_size"]) for item in pooled["cohorts"]],
            [("youtube_shorts", "english", 3), ("youtube_shorts", "tamil", 2)],
        )
        self.assertTrue(all(item["cohort_scope"] == "single" for item in pooled["cohorts"]))
        self.assertEqual(
            {key for key in pooled["cohorts"][0]} - {"cohort_scope"},
            {key for key in self.cohorts(format="youtube_shorts", language="english")} - {"cohort_scope"},
        )

    def test_one_format_and_language_is_a_single_cohort(self):
        for _ in range(2):
            self.linked()
        self.assertEqual(self.cohorts()["cohort_scope"], "single")
        filtered = self.cohorts(format="youtube_shorts", language="english")
        self.assertEqual((filtered["cohort_scope"], filtered["sample_size"]), ("single", 2))
        self.assertNotIn("cohorts", filtered)

    def test_one_filter_splits_by_the_other(self):
        self.linked(format_val="youtube_shorts", language="english")
        self.linked(format_val="youtube_shorts", language="tamil")
        self.linked(format_val="tutorial", language="english")
        by_language = self.cohorts(format="youtube_shorts")
        self.assertEqual(by_language["sample_size"], 2)
        self.assertEqual(by_language["cohort_scope"], "mixed")
        self.assertEqual({item["language"] for item in by_language["cohorts"]}, {"english", "tamil"})

    def test_long_form_kinds_are_separate_cohorts_as_generation_compares_them(self):
        # Generation for a tutorial brief compares only with tutorials, so the
        # pool of tutorials and vlogs is two cohorts, not one long-form cohort.
        for _ in range(3):
            self.linked(format_val="tutorial")
        for _ in range(3):
            self.linked(format_val="vlog")
        pooled = self.cohorts()
        self.assertEqual(pooled["sample_size"], 6)
        self.assertEqual(pooled["cohort_scope"], "mixed")
        self.assertEqual(
            [(item["format"], item["language"], item["sample_size"]) for item in pooled["cohorts"]],
            [("tutorial", "english", 3), ("vlog", "english", 3)],
        )
        generation = self.store.cohort_analytics(format_filter="tutorial", language_filter="english")
        self.assertEqual((generation["sample_size"], generation["learning_allowed"]), (3, False))
        self.assertFalse(pooled["cohorts"][0]["learning_allowed"])

    def test_an_other_long_form_cohort_does_not_make_one_kind_mixed(self):
        # A "long_form" filter selects every long-form kind, so its cohort holds
        # the tutorials too; with no eligible video of its own it adds no format.
        for _ in range(3):
            self.linked(format_val="tutorial")
        _, link_id, _ = self.linked(format_val="long_form")
        with self.store._connect() as connection:
            connection.execute("UPDATE published_video_links SET ownership_state = 'unverified', ownership_verified = 0 WHERE id = ?", (link_id,))
        pooled = self.cohorts()
        self.assertEqual(pooled["cohort_scope"], "single")
        # Listing it would show the same three tutorials twice for a pool of three.
        self.assertEqual(
            [(item["format"], item["sample_size"]) for item in pooled["cohorts"]], [("tutorial", 3)],
        )
        with self.store._connect() as connection:
            connection.execute("UPDATE published_video_links SET ownership_state = 'verified', ownership_verified = 1 WHERE id = ?", (link_id,))
        pooled = self.cohorts()
        self.assertEqual(pooled["cohort_scope"], "mixed")
        self.assertEqual(
            {(item["format"], item["sample_size"]) for item in pooled["cohorts"]},
            {("long_form", 4), ("tutorial", 3)},
        )

    def test_a_language_filter_lists_no_long_form_cohort_of_another_language(self):
        # The Tamil long-form videos give a ("long_form", "english") pair, whose
        # cohort is only the English tutorials again.
        for _ in range(3):
            self.linked(format_val="tutorial", language="english")
        for _ in range(2):
            self.linked(format_val="long_form", language="tamil")
        english = self.cohorts(language="english")
        self.assertEqual((english["sample_size"], english["cohort_scope"]), (3, "single"))
        self.assertEqual(
            [(item["format"], item["language"], item["sample_size"]) for item in english["cohorts"]],
            [("tutorial", "english", 3)],
        )


class AuditPersonalEvidenceTests(unittest.TestCase):
    def test_the_audit_reads_the_trace_generation_saves(self):
        trace = {"status": "context_only", "pattern_status": "no_pattern", "examples_supplied": 0, "sample_size": 38}
        package = {"title": "Title", "description": "Description", "tags": [], "hashtags": [], "personalization": trace}
        link = {"id": 1, "youtube_video_id": "video", "format": "youtube_shorts", "language": "english",
                "youtube_metadata": {"title": "Title", "description": "Description", "tags": []},
                "metadata_synced_at": NOW.isoformat()}
        audit = build_published_audit({
            "run": {"id": 1, "query": "q", "package": package, "selected_package": None}, "link": link,
            "snapshots": [], "linked_report": {}, "cohort": {}, "comparable": {},
        })
        self.assertEqual(audit["before_publication"]["personal_evidence"], trace)

    def test_an_older_trace_is_not_repeated_as_a_current_claim(self):
        old = {"status": "mature_evidence_used", "sample_size": 38, "message": "Mature comparable channel evidence was available."}
        package = {"title": "Title", "description": "Description", "tags": [], "hashtags": [], "personalization": old}
        audit = build_published_audit({
            "run": {"id": 1, "query": "q", "package": package, "selected_package": None},
            "link": {"id": 1, "youtube_video_id": "video", "format": "youtube_shorts", "language": "english"},
            "snapshots": [], "linked_report": {}, "cohort": {}, "comparable": {},
        })
        evidence = audit["before_publication"]["personal_evidence"]
        self.assertEqual(
            (evidence["status"], evidence["saved_status"], evidence["sample_size"]),
            ("legacy_trace", "mature_evidence_used", 38),
        )
        self.assertNotIn("Mature comparable", evidence["message"])


class GenerationWiringTests(StoreFixture):
    @patch("win_engine.generation.strategy_engine.write_multilang_packages_with_source")
    def test_a_fallback_package_reports_the_evidence_as_not_applied(self, mocked_writer):
        mocked_writer.return_value = ({"english": None}, "fallback")
        research = {
            "main_topic": "street food in Chennai", "keyword_signals": [{"keyword": "chennai street food"}],
            "entity_signals": [], "top_opportunities": [], "youtube_results": [], "category": "cooking",
            "creator_brief": {"content": "A short about Chennai street food", "video_format": "youtube_shorts"},
            "language_context": {"language": "english", "region": "india"},
        }
        package = build_seo_package("generate seo", "A short about Chennai street food", research, self.store)
        self.assertEqual(package["personalization"]["status"], "not_applied")
        self.assertEqual(package["personalization"]["generation_source"], "fallback")
        self.assertEqual(package["personalization"]["examples_supplied"], 0)


if __name__ == "__main__":
    unittest.main()
