from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from win_engine.analysis.idea_workspace import build_idea_evidence, evidence_to_research, idea_script
from win_engine.api import routes
from win_engine.core.config import Settings
from win_engine.core.schemas import CreateIdeaRequest, GenerateIdeaRequest, UpdateIdeaRequest
from win_engine.feedback.history_store import HistoryStore
from win_engine.feedback.migrations import CURRENT_SCHEMA_VERSION, prepare_database


class StageG1IdeaStoreTests(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.path = handle.name
        handle.close()
        self.store = HistoryStore(self.path)

    def tearDown(self):
        try:
            os.remove(self.path)
        except OSError:
            pass

    def create(self, topic: str = "Rainy highway reflection", **values):
        return self.store.create_content_idea({"topic": topic, **values})

    def record_run(self) -> int:
        return self.store.record_analysis_run(
            "idea script", "story", "quiet reflection", "A truthful title", 8.0,
            "medium", "WORKABLE", 60.0, {"title": "A truthful title"},
        )

    def test_current_schema_contains_stage_g1_tables_and_indexes(self):
        with self.store._connect() as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], CURRENT_SCHEMA_VERSION)
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            indexes = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        self.assertIn("content_ideas", tables)
        self.assertIn("content_idea_research_snapshots", tables)
        self.assertIn("idx_content_ideas_status", indexes)
        self.assertIn("idx_content_ideas_created_at", indexes)
        self.assertIn("idx_content_ideas_cohort", indexes)

    def test_v3_to_v4_is_backup_first_and_preserves_existing_history(self):
        with sqlite3.connect(self.path) as connection:
            connection.execute("DROP TABLE content_idea_research_snapshots")
            connection.execute("DROP TABLE content_ideas")
            connection.execute("DELETE FROM schema_migrations WHERE version = 4")
            connection.execute("PRAGMA user_version = 3")
            connection.execute(
                "INSERT INTO analysis_runs(query, created_at, title) VALUES ('preserve me', '2026-08-23T00:00:00Z', 'Saved')"
            )
        result = prepare_database(self.path)
        self.assertEqual((result.old_version, result.new_version), (3, CURRENT_SCHEMA_VERSION))
        self.assertTrue(result.backup_path and Path(result.backup_path).exists())
        with sqlite3.connect(self.path) as connection:
            self.assertEqual(connection.execute("SELECT query FROM analysis_runs").fetchone()[0], "preserve me")
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        Path(result.backup_path).unlink(missing_ok=True)

    def test_idea_survives_store_restart(self):
        idea = self.create(notes="Original creator note", format="youtube_shorts")
        reopened = HistoryStore(self.path).content_idea(idea["id"])
        self.assertEqual(reopened["topic"], "Rainy highway reflection")
        self.assertEqual(reopened["notes"], "Original creator note")

    def test_idea_validation_and_creator_only_update_fields(self):
        with self.assertRaises(ValueError):
            self.store.create_content_idea({"topic": "   "})
        with self.assertRaisesRegex(ValueError, "cannot skip"):
            self.store.create_content_idea({"topic": "Impossible lifecycle", "status": "published"})
        idea = self.create()
        with self.assertRaises(ValueError):
            self.store.update_content_idea(idea["id"], {"analysis_run_id": 99})
        with self.assertRaises(ValueError):
            self.store.update_content_idea(idea["id"], {"topic": None})
        updated = self.store.update_content_idea(idea["id"], {"notes": "Creator approved", "status": "scripted"})
        self.assertEqual((updated["notes"], updated["status"]), ("Creator approved", "scripted"))

    def test_pagination_and_status_filter_with_more_than_one_hundred_ideas(self):
        for index in range(105):
            self.create(f"Idea {index:03d}", status="archived" if index % 10 == 0 else "idea")
        first = self.store.content_ideas(limit=100, offset=0)
        second = self.store.content_ideas(limit=100, offset=100)
        archived = self.store.content_ideas(status="archived", limit=100, offset=0)
        self.assertEqual((first["total"], len(first["ideas"]), len(second["ideas"])), (105, 100, 5))
        self.assertEqual(archived["total"], 11)
        self.assertEqual(first["ideas"][0]["topic"], "Idea 104")

    def test_unknown_status_filter_is_rejected(self):
        with self.assertRaises(ValueError):
            self.store.content_ideas(status="viral")

    def test_research_snapshots_are_immutable_and_dated(self):
        idea = self.create()
        first = self.store.save_content_idea_research(idea["id"], {"captured_at": "2026-08-20T00:00:00Z", "opportunity_explanation": "First"})
        second = self.store.save_content_idea_research(idea["id"], {"captured_at": "2026-08-21T00:00:00Z", "opportunity_explanation": "Second"})
        detail = self.store.content_idea(idea["id"])
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(len(detail["research_snapshots"]), 2)
        self.assertEqual(detail["latest_research"]["evidence"]["opportunity_explanation"], "Second")
        self.assertEqual(detail["research_snapshots"][1]["evidence"]["opportunity_explanation"], "First")

    def test_missing_research_is_honest(self):
        idea = self.create()
        summary = self.store.content_ideas()["ideas"][0]
        self.assertIsNone(idea["latest_research"])
        self.assertEqual(summary["personal_evidence_status"], "insufficient_evidence")
        self.assertIn("not been run", summary["opportunity_explanation"])

    def test_creator_content_change_marks_current_research_stale_but_preserves_snapshot(self):
        idea = self.create()
        self.store.save_content_idea_research(idea["id"], {"captured_at": "2026-08-20T00:00:00Z", "opportunity_explanation": "Old topic evidence"})
        changed = self.store.update_content_idea(idea["id"], {"topic": "A materially different topic"})
        self.assertTrue(changed["research_is_stale"])
        self.assertIsNone(changed["latest_research"])
        self.assertEqual(len(changed["research_snapshots"]), 1)
        self.assertEqual(changed["research_snapshots"][0]["evidence"]["opportunity_explanation"], "Old topic evidence")

    def test_package_and_owned_video_complete_traceable_lifecycle(self):
        idea = self.create(status="scripted")
        run_id = self.record_run()
        generated = self.store.attach_content_idea_analysis(idea["id"], run_id)
        self.assertEqual((generated["status"], generated["analysis_run_id"]), ("package_generated", run_id))
        link_id = self.store.link_published_video(
            analysis_run_id=run_id, youtube_video_id="AbCdEfGhI12",
            published_at="2026-08-23T00:00:00Z", ownership_state="verified",
            ownership_verified=True, verified_channel_id="owned-channel",
        )
        published = self.store.content_idea(idea["id"])
        self.assertEqual((published["status"], published["published_video_link_id"]), ("published", link_id))

    def test_creator_cannot_mark_unlinked_idea_published(self):
        idea = self.create()
        with self.assertRaisesRegex(ValueError, "Link the generated package"):
            self.store.update_content_idea(idea["id"], {"status": "published"})

    def test_deleting_generated_history_preserves_and_reopens_idea(self):
        idea = self.create(status="scripted")
        run_id = self.record_run()
        self.store.attach_content_idea_analysis(idea["id"], run_id)
        self.assertTrue(self.store.delete_analysis_run(run_id))
        restored = self.store.content_idea(idea["id"])
        self.assertEqual(restored["status"], "scripted")
        self.assertIsNone(restored["analysis_run_id"])


class StageG1IdeaEvidenceTests(unittest.TestCase):
    def test_evidence_uses_dated_observations_not_fake_demand(self):
        evidence = build_idea_evidence({
            "youtube_results": [{"title": "Public result", "published_at": "2026-08-20T00:00:00Z", "view_count": 50, "outlier_score": 3.2}],
            "research_queries": [{"type": "topic", "query": "rain road quote"}],
            "research_warnings": [],
        }, {"learning_allowed": False, "sample_size": 4, "confidence_label": "Collecting evidence", "snapshot_window": "24h"})
        self.assertEqual(evidence["signals"]["relevant_result_count"], 1)
        self.assertEqual(evidence["personal_evidence"]["status"], "insufficient_evidence")
        self.assertIn("not monthly search volume", evidence["opportunity_explanation"])
        self.assertNotIn("trend_percentage", evidence)

    def test_empty_research_does_not_fabricate_signals(self):
        evidence = build_idea_evidence({"youtube_results": [], "research_queries": []})
        self.assertEqual(evidence["signals"]["relevant_result_count"], 0)
        self.assertIn("unavailable", evidence["opportunity_explanation"])
        self.assertEqual(evidence["personal_evidence"]["status"], "insufficient_evidence")

    def test_research_snapshot_excludes_runtime_objects_and_tokens(self):
        evidence = build_idea_evidence({
            "history_store": object(), "youtube_runtime": {"refresh_token": "secret"},
            "youtube_results": [], "research_queries": [],
        })
        serialized = str(evidence)
        self.assertNotIn("history_store", evidence)
        self.assertNotIn("youtube_runtime", evidence)
        self.assertNotIn("secret", serialized)

    def test_saved_evidence_rehydrates_generator_defaults(self):
        research = evidence_to_research({"youtube_results": None, "cache_policy": None})
        self.assertEqual(research["youtube_results"], [])
        self.assertEqual(research["research_warnings"], [])
        self.assertEqual(research["research_decision"], {})
        self.assertEqual(research["cache_policy"], "idea-research-snapshot")

    def test_idea_script_uses_only_creator_fields_and_override(self):
        idea = {"topic": "Sunset quote", "notes": "Two people sitting", "evidence": {"invented": "ignore"}}
        self.assertIn("Notes: Two people sitting", idea_script(idea))
        self.assertNotIn("invented", idea_script(idea))
        self.assertEqual(idea_script(idea, "Exact creator script"), "Exact creator script")


class StageG1IdeaApiTests(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.path = handle.name
        handle.close()
        self.settings = Settings(database_path=self.path, youtube_api_key=None, gemini_api_key=None)
        self.settings_patch = patch.object(routes, "get_settings", return_value=self.settings)
        self.settings_patch.start()

    def tearDown(self):
        self.settings_patch.stop()
        try:
            os.remove(self.path)
        except OSError:
            pass

    def test_create_list_get_and_patch_api_contract(self):
        created = routes.create_idea(CreateIdeaRequest(topic="Private original idea", format="youtube_shorts"))
        idea_id = created["idea"]["id"]
        listing = routes.list_ideas(status="idea", limit=20, offset=0)
        detail = routes.get_idea(idea_id)
        updated = routes.update_idea(idea_id, UpdateIdeaRequest(notes="Script outline", status="scripted"))
        self.assertEqual((created["status"], listing["total"]), ("created", 1))
        self.assertEqual(detail["idea"]["topic"], "Private original idea")
        self.assertEqual(updated["idea"]["status"], "scripted")

    def test_research_api_saves_each_controlled_refresh(self):
        idea = routes.create_idea(CreateIdeaRequest(topic="Research this quote"))["idea"]
        fixture = {
            "youtube_results": [], "top_opportunities": [], "keyword_signals": [], "entity_signals": [],
            "upload_timing": {}, "thumbnail_intelligence": {}, "research_queries": [],
            "research_decision": {}, "research_warnings": ["API unavailable in fixture"], "cache_policy": "test",
        }
        with patch.object(routes.ResearchService, "gather", return_value=fixture):
            routes.research_idea(idea["id"])
            result = routes.research_idea(idea["id"])
        self.assertEqual(len(result["idea"]["research_snapshots"]), 2)
        self.assertIn("unavailable", result["snapshot"]["evidence"]["opportunity_explanation"])

    def test_generate_api_uses_existing_generator_and_links_history_run(self):
        idea = routes.create_idea(CreateIdeaRequest(topic="Generate this package"))["idea"]
        store = HistoryStore(self.path)
        store.save_content_idea_research(idea["id"], build_idea_evidence({"youtube_results": [], "research_queries": []}))

        def fake_generate(script, research, context):
            run_id = research["history_store"].record_analysis_run(script, "idea", "angle", "Title", 8, "low", "UNKNOWN", 0, {"title": "Title"})
            return {"history_run_id": run_id, "title": "Title"}

        with patch.object(routes, "generate_seo_suggestions", side_effect=fake_generate) as generator:
            result = routes.generate_idea_package(idea["id"], GenerateIdeaRequest())
        self.assertEqual(result["idea"]["status"], "package_generated")
        self.assertIsInstance(result["idea"]["analysis_run_id"], int)
        self.assertEqual(generator.call_count, 1)


if __name__ == "__main__":
    unittest.main()
