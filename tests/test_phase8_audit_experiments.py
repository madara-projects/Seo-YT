from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from win_engine.analysis.audit_experiment import compare_experiment
from win_engine.core.schemas import CreateStructuredExperimentRequest
from win_engine.feedback.audit_experiment_store import AuditExperimentStore
from win_engine.feedback.history_store import HistoryStore
from win_engine.feedback.migrations import CURRENT_SCHEMA_VERSION, prepare_database


class Phase8Fixture(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.path = handle.name
        handle.close()
        self.history = HistoryStore(self.path)
        self.store = AuditExperimentStore(self.history)
        self.counter = 0

    def tearDown(self):
        try:
            os.remove(self.path)
        except OSError:
            pass

    def add_video(self, *, selected=True, metadata=True, mature=True, views=100, retention=60, verified=True):
        self.counter += 1
        title = f"Generated Title {self.counter}"
        payload = {
            "title": title, "description": "Generated description", "tags": ["topic", "shorts"],
            "hashtags": ["#Shorts"], "generation_quality": {"status": "pass"},
            "retention_assistant": {"risk_level": "medium", "rule_version": "phase5-v1"},
            "creator_brief": {"topic": "camera", "video_format": "youtube_shorts", "language": "english"},
            "title_thumbnail_packages": [{"package_id": "package-a", "title": title, "mechanism": "specific_curiosity", "surface": "browse"}],
        }
        run_id = self.history.record_analysis_run("camera script", "SEARCH", "camera", title, 8, "medium", "WORKABLE", 60, payload=payload)
        if selected:
            self.history.select_generated_package(run_id, "package-a")
        video_id = f"phase8vid{self.counter:02d}"
        link_id = self.history.link_published_video(
            run_id, video_id, "2026-08-20T00:00:00+00:00", format_val="youtube_shorts", language="english",
            ownership_state="verified" if verified else "unverified", ownership_verified=verified,
            verified_channel_id="owner" if verified else None,
            ownership_verified_at=datetime.now(timezone.utc).isoformat() if verified else None,
        )
        if metadata:
            self.history.update_linked_video_metadata(link_id, {"title": title if selected else "Published Title", "description": "Published description #Shorts", "tags": ["topic", "shorts"], "duration": "PT30S"})
        if mature:
            self.history.record_performance_snapshot(video_id, 24, views=views, likes=max(1, views // 20), comments=2, avg_view_percentage=retention, snapshot_window="24h")
        return run_id, link_id, video_id

    def experiment(self, **overrides):
        values = {"name": "Title mechanism test", "description": "", "hypothesis": "Specific curiosity may be associated with stronger observed retention.", "mode": "controlled", "status": "draft", "variable": "title_mechanism", "variable_category": "packaging", "control_definition": "descriptive title", "variant_definition": "specific curiosity title", "success_metric": "average_view_percentage", "secondary_metrics": ["views"], "target_sample_size": 10, "minimum_sample_size": 5, "observation_window": "24h", "notes": ""}
        values.update(overrides)
        return self.store.create_experiment(values)


class Phase8MigrationTests(Phase8Fixture):
    def test_schema_v6_tables_and_integrity(self):
        with self.history._connect() as c:
            names = {row[0] for row in c.execute("select name from sqlite_master where type='table'")}
            self.assertEqual(c.execute("pragma user_version").fetchone()[0], CURRENT_SCHEMA_VERSION)
            self.assertEqual(c.execute("pragma integrity_check").fetchone()[0], "ok")
            self.assertEqual(c.execute("pragma foreign_key_check").fetchall(), [])
        self.assertTrue({"published_video_audits", "experiments", "experiment_video_assignments", "experiment_result_snapshots"} <= names)

    def test_v5_to_v6_backup_preserves_existing_history(self):
        run_id, _, _ = self.add_video()
        with sqlite3.connect(self.path) as c:
            for table in ("experiment_result_snapshots", "experiment_video_assignments", "experiments", "published_video_audits"):
                c.execute(f"drop table {table}")
            c.execute("delete from schema_migrations where version=6")
            c.execute("pragma user_version=5")
        result = prepare_database(self.path)
        self.assertEqual((result.old_version, result.new_version), (5, CURRENT_SCHEMA_VERSION))
        self.assertTrue(Path(result.backup_path).exists())
        self.assertIsNotNone(HistoryStore(self.path).history_run(run_id))
        Path(result.backup_path).unlink(missing_ok=True)


class PublishedAuditTests(Phase8Fixture):
    def test_audit_preserves_generated_selected_and_published_states(self):
        run_id, link_id, _ = self.add_video()
        self.history.update_linked_video_metadata(link_id, {"title": "Published Different", "description": "Actual #Real", "tags": "actual legacy tag string"})
        audit = self.store.refresh_audit(link_id)
        title = next(item for item in audit["comparisons"] if item["field"] == "title")
        self.assertEqual(title["generated"], "Generated Title 1")
        self.assertEqual(title["selected"], "Generated Title 1")
        self.assertEqual(title["published"], "Published Different")
        self.assertEqual(title["selected_to_published"], "changed")
        tags = next(item for item in audit["comparisons"] if item["field"] == "tags")
        self.assertEqual(tags["published"], ["actual legacy tag string"])
        self.assertEqual(audit["video"]["analysis_run_id"], run_id)

    def test_unknown_selection_is_not_inferred(self):
        _, link_id, _ = self.add_video(selected=False)
        audit = self.store.refresh_audit(link_id)
        self.assertEqual(audit["intent"]["selection_attribution"], "unknown")
        self.assertIn("selection_unknown", {item["code"] for item in audit["findings"]})

    def test_unavailable_published_metadata_stays_unavailable(self):
        _, link_id, _ = self.add_video(metadata=False, mature=False)
        audit = self.store.refresh_audit(link_id)
        self.assertFalse(audit["published_reality"]["available"])
        self.assertEqual(audit["summary"]["state"], "not_enough_data")
        self.assertEqual(audit["comparisons"][0]["selected_to_published"], "unavailable")

    def test_current_only_snapshot_is_collecting_or_observable(self):
        _, link_id, video_id = self.add_video(mature=False)
        self.history.record_performance_snapshot(video_id, 4, views=20, snapshot_window="current")
        audit = self.store.refresh_audit(link_id)
        self.assertEqual(audit["summary"]["state"], "observable")
        self.assertEqual(audit["observed_performance"]["maturity"], "collecting_evidence")

    def test_mature_observation_never_claims_causality(self):
        _, link_id, _ = self.add_video()
        audit = self.store.refresh_audit(link_id)
        self.assertEqual(audit["summary"]["state"], "mature_observation")
        self.assertEqual(audit["observed_performance"]["causality"], "not_established")
        self.assertTrue(all("not caus" in text.lower() or "does not" in text.lower() for text in audit["limitations"][-1:]))

    def test_audit_refresh_is_immutable(self):
        _, link_id, _ = self.add_video()
        first = self.store.refresh_audit(link_id)
        self.history.update_linked_video_metadata(link_id, {"title": "Later Title", "description": "Later", "tags": []})
        second = self.store.refresh_audit(link_id)
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(len(self.store.audit_versions(link_id)), 2)
        old = self.store.audit(link_id, first["id"])
        self.assertNotEqual(old["published_reality"]["title"], second["published_reality"]["title"])

    def test_audit_contains_historical_quality_retention_and_provenance(self):
        _, link_id, _ = self.add_video()
        audit = self.store.refresh_audit(link_id)
        self.assertEqual(audit["before_publication"]["generation_quality"]["status"], "pass")
        self.assertEqual(audit["before_publication"]["retention_assistant"]["risk_level"], "medium")
        self.assertIn("saved_analysis_payload", audit["evidence"]["provenance"])
        self.assertTrue(all(item.get("evidence") and item.get("recommended_interpretation") for item in audit["findings"]))

    def test_candidate_list_exposes_selection_and_audit_state(self):
        _, link_id, _ = self.add_video(selected=False)
        self.store.refresh_audit(link_id)
        candidate = self.store.audit_candidates()[0]
        self.assertEqual(candidate["selection_state"], "unknown")
        self.assertEqual(candidate["audit_state"], "mature_observation")

    def test_five_comparable_videos_enable_actionable_observation_not_causality(self):
        link_id = None
        for index in range(5):
            _, link_id, _ = self.add_video(views=100 + index, retention=60 + index)
        audit = self.store.refresh_audit(link_id)
        self.assertEqual(audit["summary"]["state"], "actionable_observation")
        self.assertTrue(all(item["evidence_state"] == "mature_comparable_evidence" for item in audit["learning_candidates"]))
        self.assertTrue(all("causal proof" in item["interpretation"] for item in audit["learning_candidates"]))

    def test_saved_prepublication_idea_and_demand_trace_is_used(self):
        run_id, link_id, _ = self.add_video()
        idea = self.history.create_content_idea({"topic": "Historical camera topic"})
        self.history.attach_content_idea_analysis(idea["id"], run_id)
        evidence = {"matching_watchlist": [{"video_id": "public-one", "status": "possible_outlier"}], "reasons": ["Dated public observation"]}
        with self.history._connect() as connection:
            connection.execute("UPDATE content_ideas SET published_video_link_id=?,status='published' WHERE id=?", (link_id, idea["id"]))
            connection.execute("INSERT INTO content_idea_research_snapshots(content_idea_id,captured_at,evidence_json) VALUES (?,?,?)", (idea["id"], "2026-08-19T00:00:00+00:00", '{"source":"saved idea research"}'))
            connection.execute("INSERT INTO demand_research_snapshots(idea_id,topic,classification,evidence_json,captured_at) VALUES (?,?,?,?,?)", (idea["id"], "Historical camera topic", "active_topic", __import__("json").dumps(evidence), "2026-08-19T01:00:00+00:00"))
        audit = self.store.refresh_audit(link_id)
        self.assertEqual(audit["before_publication"]["idea"]["topic"], "Historical camera topic")
        self.assertEqual(audit["before_publication"]["demand_research"]["classification"], "active_topic")
        self.assertEqual(audit["before_publication"]["watchlist_context"][0]["status"], "possible_outlier")


class StructuredExperimentTests(Phase8Fixture):
    def test_experiment_creation_and_validation(self):
        item = self.experiment()
        self.assertEqual(item["mode"], "controlled")
        self.assertEqual(item["assignment_counts"]["control"], 0)
        with self.assertRaises(ValueError):
            CreateStructuredExperimentRequest(name="x", hypothesis="h", variable="v", control_definition="c", variant_definition="v", minimum_sample_size=5, target_sample_size=8)

    def test_status_lifecycle_enforced(self):
        item = self.experiment()
        planned = self.store.update_experiment(item["id"], {"status": "planned"})
        self.assertEqual(planned["status"], "planned")
        with self.assertRaisesRegex(ValueError, "Invalid"):
            self.store.update_experiment(item["id"], {"status": "completed"})

    def test_control_variant_assignment_and_duplicate_prevention(self):
        item = self.experiment()
        _, control, _ = self.add_video()
        _, variant, _ = self.add_video()
        self.store.assign_video(item["id"], control, "control")
        updated = self.store.assign_video(item["id"], variant, "variant")
        self.assertEqual(updated["assignment_counts"], {"control": 1, "variant": 1, "observational_reference": 0})
        with self.assertRaisesRegex(ValueError, "already"):
            self.store.assign_video(item["id"], control, "variant")

    def test_invalid_assignment_prevention(self):
        item = self.experiment()
        _, unverified, _ = self.add_video(verified=False)
        with self.assertRaisesRegex(ValueError, "verified"):
            self.store.assign_video(item["id"], unverified, "control")
        _, verified, _ = self.add_video()
        with self.assertRaisesRegex(ValueError, "controlled"):
            self.store.assign_video(item["id"], verified, "observational_reference")

    def test_small_sample_is_insufficient(self):
        item = self.experiment()
        for role, retention in (("control", 60), ("variant", 70)):
            _, link_id, _ = self.add_video(retention=retention)
            self.store.assign_video(item["id"], link_id, role)
        result = self.store.refresh_experiment_result(item["id"])
        self.assertEqual(result["state"], "insufficient_evidence")
        self.assertIsNone(result["learning_candidate"])

    def add_groups(self, item, *, control_retention=60, variant_retention=75, control_views=100, variant_views=150):
        for index in range(5):
            _, link_id, _ = self.add_video(retention=control_retention + index, views=control_views + index)
            self.store.assign_video(item["id"], link_id, "control")
        for index in range(5):
            _, link_id, _ = self.add_video(retention=variant_retention + index, views=variant_views + index)
            self.store.assign_video(item["id"], link_id, "variant")

    def test_directional_variant_result_and_learning_candidate(self):
        item = self.experiment(secondary_metrics=[])
        self.add_groups(item)
        result = self.store.refresh_experiment_result(item["id"])
        self.assertEqual(result["state"], "directional_variant")
        self.assertEqual(result["learning_candidate"]["evidence_state"], "directional")
        self.assertIn("associated", result["interpretation"].lower())

    def test_directional_control_result(self):
        item = self.experiment(secondary_metrics=[])
        self.add_groups(item, control_retention=80, variant_retention=60)
        self.assertEqual(self.store.refresh_experiment_result(item["id"])["state"], "directional_control")

    def test_inconclusive_result(self):
        item = self.experiment(secondary_metrics=[])
        self.add_groups(item, control_retention=70, variant_retention=71)
        self.assertEqual(self.store.refresh_experiment_result(item["id"])["state"], "inconclusive")

    def test_mixed_result(self):
        item = self.experiment(success_metric="average_view_percentage", secondary_metrics=["views"])
        self.add_groups(item, control_retention=60, variant_retention=80, control_views=200, variant_views=100)
        self.assertEqual(self.store.refresh_experiment_result(item["id"])["state"], "mixed_results")

    def test_observational_comparison_is_explicit(self):
        item = self.experiment(mode="observational", secondary_metrics=[])
        self.add_groups(item)
        result = self.store.refresh_experiment_result(item["id"])
        self.assertEqual(result["state"], "observational_pattern")
        self.assertIn("NOT A CONTROLLED", result["label"])
        self.assertEqual(result["learning_candidate"]["evidence_state"], "observed_association")

    def test_missing_metric_and_incomplete_window_excluded(self):
        item = self.experiment()
        _, link_id, _ = self.add_video(mature=False)
        self.store.assign_video(item["id"], link_id, "control")
        result = self.store.refresh_experiment_result(item["id"])
        self.assertEqual(result["sample"]["eligible_control"], 0)
        self.assertTrue(result["sample"]["missing_metrics"])

    def test_result_refresh_preserves_versions(self):
        item = self.experiment()
        first = self.store.refresh_experiment_result(item["id"])
        second = self.store.refresh_experiment_result(item["id"])
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(len(self.store.result_versions(item["id"])), 2)

    def test_pure_comparison_rejects_fake_significance(self):
        result = compare_experiment({"id": 1, "mode": "controlled", "success_metric": "views", "secondary_metrics": [], "minimum_sample_size": 5, "observation_window": "24h", "variable": "title"}, [])
        self.assertEqual(result["state"], "insufficient_evidence")
        self.assertNotIn("significant", str(result).lower())
        self.assertIn("not causal proof", result["label"].lower())


if __name__ == "__main__":
    unittest.main()
