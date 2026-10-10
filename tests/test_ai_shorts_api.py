"""AI Shorts: a quote becomes Google Flow prompts and a lean package, saved to History, with no YouTube call.

The Flow planner (``flow_prompts.plan_flow_shots``) and Gemini are mocked, and
the YouTube client fails the test if anything on this path tries to use it.
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from starlette.requests import Request

from win_engine.api import routes
from win_engine.api.app import STATIC_DIR, create_app, is_costly
from win_engine.core.config import Settings
from win_engine.core.schemas import AiShortsGenerateRequest
from win_engine.feedback import migrations
from win_engine.feedback.ai_shorts_store import AiShortsStore
from win_engine.feedback.history_store import HistoryStore, comparable_format
from win_engine.feedback.studio_tests import run_is_short
from win_engine.generation import ai_shorts
from win_engine.generation.flow_prompts import cautions, flow_steps
from win_engine.ingestion.research_service import ResearchService
from win_engine.ingestion.youtube_client import YouTubeClient
from win_engine.llm import gemini_client

QUOTE = "Stop explaining yourself to people who already decided to misunderstand you."
VISUAL = "a person walking alone down a rain-soaked street at night, neon reflections on the wet asphalt"
GEMINI_ENV = {"WIN_ENGINE_GEMINI_API_KEY": "test", "WIN_ENGINE_GEMINI_MODEL": "test"}
PLANNER_KEYS = {
    "quote", "language", "parts", "total_seconds", "mood", "shots", "negative_prompt", "audio",
    "text_overlay_plan", "flow_steps", "cautions", "checks", "generation_source", "provider",
}
LIST_KEYS = {"id", "analysis_run_id", "quote", "language", "parts", "total_seconds", "generation_source",
             "package_title", "created_at"}


def _plan(quote: str = QUOTE, parts: int = 2, language: str = "english", generation_source: str = "fallback") -> dict:
    """What flow_prompts.plan_flow_shots returns, in its documented shape."""
    words = quote.split()
    step = max(1, -(-len(words) // parts))
    shots, overlay = [], []
    for part in range(1, parts + 1):
        shots.append({
            "part": part, "seconds": 8,
            "title": "The walk begins" if part == 1 else f"Part {part}: the street keeps going",
            "prompt": f"Cinematic vertical 9:16 shot, part {part}: {VISUAL}; slow dolly forward, soft rain, no text.",
            "flow_mode": "text_to_video" if part == 1 else "extend",
            "continuity": "" if part == 1 else "Same street and light; the camera keeps drifting forward.",
        })
        overlay.append({"part": part, "seconds": 8, "lines": [" ".join(words[(part - 1) * step: part * step])]})
    return {
        "quote": quote, "language": language, "parts": parts, "total_seconds": 8 * parts,
        "mood": {"feeling": "quiet resolve", "keywords": ["rain", "night", "alone", "walking"],
                 "visual_metaphor": VISUAL, "palette": "deep blue with amber neon", "pace": "slow"},
        "shots": shots,
        "negative_prompt": "on-screen text, captions, watermark, extra people, fast cuts",
        "audio": {"style": "ambient", "description": "soft rain on pavement and a distant traffic hum"},
        "text_overlay_plan": overlay,
        "flow_steps": ["Open Google Flow and start a new project.", "Part 1: Text to Video with the part 1 prompt.",
                       "Each later part: Extend the previous clip with its prompt."][: 2 + (parts > 1)],
        "cautions": ["Veo renders on-screen text unreliably; add the quote in your editor."],
        "checks": {"passed": True, "issues": [], "warnings": []},
        "generation_source": generation_source,
        "provider": {"status": "gemini_unavailable" if generation_source == "fallback" else "gemini_success"},
    }


def _request(method: str, path: str) -> Request:
    return Request({"type": "http", "method": method, "path": path, "headers": [(b"host", b"127.0.0.1:8000")]})


def _gemini_reply(text: str = '{"title": "t"}') -> MagicMock:
    response = MagicMock(status_code=200, headers={})
    response.json.return_value = {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}]}
    return response


def _greedy_planner(statuses: list[str]):
    """A planner that wants four Gemini calls; its statuses show which were allowed."""
    def plan(quote, *, language, parts, mood_hint):
        for _ in range(4):
            _, trace = gemini_client.generate_with_diagnostics("plan the shots")
            statuses.append(str(trace["status"]))
        return _plan(quote, parts, language, generation_source="gemini")
    return plan


def _greedy_writer(statuses: list[str]):
    """A package stage that wants four Gemini calls, then records its run as the real one does."""
    def generate(script, research, context=None):
        for _ in range(4):
            _, trace = gemini_client.generate_with_diagnostics("write the package")
            statuses.append(str(trace["status"]))
        run_id = research["history_store"].record_analysis_run(
            query=script, intent="emotional", content_angle="quote", title="A title #shorts", title_score=80.0,
            retention_risk="low", opportunity_label="UNMEASURED", opportunity_score=None,
            payload={"title": "A title #shorts"},
        )
        return {"title": "A title #shorts", "history_run_id": run_id, "research_warnings": []}
    return generate


class AiShortsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.path = str(Path(self.dir.name) / "ai-shorts.db")
        # The generate route shares the stricter budget for quota-spending requests
        # (eight per window by default); these tests send more than that.
        self.settings = Settings(database_path=self.path, allowed_hosts="testserver", app_environment="development",
                                 analyze_rate_limit_max_requests=50)
        self.planner = MagicMock(side_effect=lambda quote, **kw: _plan(quote, kw["parts"], kw["language"]))
        # Gemini is off unless a test turns it on; the writer then falls back locally with no call.
        self.gemini_off = patch.object(gemini_client, "is_available", return_value=False)
        self.patches = [
            patch.object(routes, "get_settings", return_value=self.settings),
            patch("win_engine.core.config.get_settings", return_value=self.settings),
            # Zero YouTube Data API calls: building the client or running research fails the test.
            patch.object(YouTubeClient, "__init__", side_effect=AssertionError("the AI Shorts path must not build a YouTube client")),
            patch.object(ResearchService, "gather", side_effect=AssertionError("the AI Shorts path must not run research")),
            patch.object(ai_shorts, "_plan_flow_shots", self.planner),
            self.gemini_off,
        ]
        for item in self.patches:
            item.start()
        self.client = TestClient(create_app(), raise_server_exceptions=False)
        self.store = HistoryStore(self.path)

    def tearDown(self) -> None:
        for item in self.patches:
            item.stop()
        self.dir.cleanup()

    def generate(self, **body) -> dict:
        response = self.client.post("/api/ai-shorts/generate", json={"quote": QUOTE, **body})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def table_count(self, table: str) -> int:
        with self.store._connect() as connection:
            return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


class GenerateTests(AiShortsTestCase):
    def test_a_quote_becomes_a_plan_and_a_history_run(self):
        body = self.generate()
        plan = _plan()

        self.planner.assert_called_once_with(QUOTE, language="english", parts=2, mood_hint="")
        self.assertIsInstance(body["id"], int)
        self.assertIsInstance(body["analysis_run_id"], int)
        datetime.fromisoformat(body["created_at"])
        for key in PLANNER_KEYS:
            with self.subTest(key=key):
                self.assertEqual(body[key], plan[key])

        package = body["package"]
        for key in ("title", "title_variants", "description", "tags", "hashtags", "title_thumbnail_packages",
                    "generation_quality", "generation_source", "creator_brief"):
            with self.subTest(key=key):
                self.assertIn(key, package)
        self.assertTrue(package["title"])
        self.assertTrue(package["title"].endswith("#shorts"))
        self.assertTrue(all(title.endswith("#shorts") for title in package["title_variants"]))
        self.assertTrue(package["title_thumbnail_packages"])
        self.assertIn(package["generation_quality"]["verdict"], {"GREEN", "YELLOW", "RED"})
        self.assertEqual(package["generation_source"], "fallback")
        # The Shorts path: #shorts first, the quote preserved, no YouTube evidence pretended.
        self.assertEqual(package["hashtags"][0], "#shorts")
        self.assertIn("#shorts", package["description"])
        self.assertEqual(package["youtube_results"], [])
        self.assertEqual(package["opportunity_gap_analysis"]["opportunity_score"]["label"], "UNMEASURED")
        self.assertIsNone(package["opportunity_gap_analysis"]["opportunity_score"]["score"])
        self.assertIn(ai_shorts.RESEARCH_SKIPPED_WARNING, package["research_warnings"])
        self.assertFalse([w for w in package["research_warnings"] if w.startswith("Keyword signals are unavailable")])
        self.assertEqual(package["source_page"], "ai_shorts")
        self.assertEqual(package["ai_shorts"]["plan_id"], body["id"])
        self.assertEqual(package["ai_shorts"]["parts"], 2)

        run = self.store.history_run(body["analysis_run_id"])
        self.assertEqual(run["query"], QUOTE)
        self.assertEqual(run["package"]["source_page"], "ai_shorts")
        self.assertEqual(run["package"]["ai_shorts"], package["ai_shorts"])
        self.assertEqual((run["opportunity_label"], run["opportunity_score"]), ("UNMEASURED", None))
        brief = run["package"]["creator_brief"]
        self.assertEqual(brief["exact_quote"], QUOTE)
        self.assertEqual(brief["on_screen_text"], QUOTE)
        self.assertEqual(brief["visual_requirements"], VISUAL)
        self.assertEqual(brief["duration_seconds"], 16)
        self.assertEqual(comparable_format(brief["video_format"]), "youtube_shorts")
        self.assertTrue(run_is_short(run))
        self.assertEqual(run["package"]["chapters"], [])

        listed = self.client.get("/api/history/runs").json()["runs"]
        self.assertIn(body["analysis_run_id"], [item["id"] for item in listed])

    def test_the_package_warnings_leave_out_the_briefs_unknown_fields(self):
        # "who the video is for is unknown", "proof ... is unknown" and "Voice Over is
        # unknown" are noise for a quote Short made with Flow; the brief still records them.
        package = self.generate()["package"]
        self.assertTrue(package["creator_brief"]["warnings"])
        self.assertFalse([item for item in package["research_warnings"] if item.endswith("is unknown.")])
        self.assertEqual(package["research_warnings"][0], ai_shorts.RESEARCH_SKIPPED_WARNING)
        self.assertEqual(len(package["research_warnings"]), len(set(package["research_warnings"])))

    def test_honest_warnings_drop_only_the_briefs_own_lines(self):
        fallback = "Gemini timed out, so this run used the content-specific local fallback."
        kept = ai_shorts._honest_research_warnings(
            ["Voice Over is unknown.", fallback, "who the video is for is unknown.", "Keyword signals are unavailable: x"],
            brief_warnings=["Voice Over is unknown.", "who the video is for is unknown."],
        )
        self.assertEqual(kept, [ai_shorts.RESEARCH_SKIPPED_WARNING, fallback])

    def test_the_plan_row_keeps_the_request_and_the_planner_verdict(self):
        body = self.generate(parts=3, language="Tamil", mood_hint="  rain at night  ", region="India")
        self.planner.assert_called_once_with(QUOTE, language="tamil", parts=3, mood_hint="rain at night")
        with self.store._connect() as connection:
            row = connection.execute(
                "SELECT analysis_run_id, quote, language, parts, generation_source FROM ai_short_plans WHERE id = ?",
                (body["id"],),
            ).fetchone()
        self.assertEqual(tuple(row), (body["analysis_run_id"], QUOTE, "tamil", 3, "fallback"))
        self.assertEqual(body["total_seconds"], 24)
        self.assertEqual(body["package"]["creator_brief"]["region"], "india")
        self.assertEqual(body["package"]["creator_brief"]["language"], "tamil")

    def test_the_request_model_trims_and_normalizes(self):
        request = AiShortsGenerateRequest(quote=f"  {QUOTE}  ", language=" English ", region="IN")
        self.assertEqual((request.quote, request.language, request.region, request.parts), (QUOTE, "english", "india", 2))

    def test_invalid_requests_are_refused_before_the_planner_runs(self):
        cases = {
            "short quote": {"quote": "short"},
            "blank quote": {"quote": "        "},
            "no words": {"quote": "🔥🔥🔥 !!! 🔥🔥🔥"},
            "long quote": {"quote": "x" * 401},
            "no quote": {},
            "zero parts": {"quote": QUOTE, "parts": 0},
            "four parts": {"quote": QUOTE, "parts": 4},
            # Lax ints read JSON true as 1 part and "2" as 2.
            "parts true": {"quote": QUOTE, "parts": True},
            "parts as text": {"quote": QUOTE, "parts": "2"},
            "long mood hint": {"quote": QUOTE, "mood_hint": "m" * 201},
            "unknown field": {"quote": QUOTE, "style": "cinematic"},
        }
        for name, body in cases.items():
            with self.subTest(case=name):
                response = self.client.post("/api/ai-shorts/generate", json=body)
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(response.json()["error"]["code"], "validation_error")
        self.planner.assert_not_called()
        self.assertEqual(self.store.history_run_count(), 0)
        self.assertEqual(self.table_count("ai_short_plans"), 0)

    def test_a_quote_the_planner_refuses_is_a_422_and_saves_nothing(self):
        # Eight characters to the request model, five once the planner tidies the spaces.
        response = self.client.post("/api/ai-shorts/generate", json={"quote": "ab    cd"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["message"], "quote must have at least 6 characters")
        self.planner.assert_not_called()
        self.assertEqual(self.store.history_run_count(), 0)

    def test_a_part_count_the_planner_refuses_is_a_refused_quote(self):
        with self.assertRaisesRegex(ai_shorts.QuoteRefused, "parts must be a whole number from 1 to 3"):
            ai_shorts.generate_ai_short(self.store, quote=QUOTE, parts=4)
        self.planner.assert_not_called()
        self.assertEqual(self.store.history_run_count(), 0)

    def test_a_value_error_inside_the_planner_is_a_server_error_not_a_refused_quote(self):
        # The inputs passed; a ValueError later in the planner (json.loads raised one
        # for a reply with a 5000-digit number) is the server's failure, not a verdict.
        self.planner.side_effect = ValueError("Exceeds the limit (4300 digits) for integer string conversion")
        response = self.client.post("/api/ai-shorts/generate", json={"quote": QUOTE})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"]["code"], "internal_server_error")
        self.assertNotIn("4300 digits", response.text)
        self.assertEqual(self.store.history_run_count(), 0)

    def test_a_value_error_after_the_planner_is_a_server_error_not_a_refused_quote(self):
        # Only the planner judges the quote; any ValueError used to become a 422
        # that showed the creator an internal message about their quote.
        with patch.object(ai_shorts, "generate_seo_suggestions", side_effect=ValueError("internal detail")):
            response = self.client.post("/api/ai-shorts/generate", json={"quote": QUOTE})
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("internal detail", response.text)
        self.assertEqual(self.store.history_run_count(), 0)

    def test_a_plan_that_cannot_be_saved_leaves_no_orphan_run(self):
        with patch.object(AiShortsStore, "save_plan", side_effect=sqlite3.OperationalError("disk I/O error")):
            response = self.client.post("/api/ai-shorts/generate", json={"quote": QUOTE})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"]["code"], "internal_server_error")
        self.assertEqual(self.store.history_run_count(), 0)
        self.assertEqual(self.table_count("ai_short_plans"), 0)

    def test_a_package_stage_that_fails_after_recording_its_run_leaves_no_orphan_run(self):
        def records_then(outcome):
            def generate(script, research, context=None):
                run_id = research["history_store"].record_analysis_run(
                    query=script, intent="emotional", content_angle="quote", title="A title #shorts", title_score=80.0,
                    retention_risk="low", opportunity_label="UNMEASURED", opportunity_score=None,
                    payload={"title": "A title #shorts"},
                )
                if outcome == "raises":
                    raise RuntimeError("the final quality gate failed")
                return {"title": "A title #shorts", "history_run_id": str(run_id), "research_warnings": []}
            return generate

        # Another package saved meanwhile is not this request's to delete.
        self.store.record_analysis_run("other", "browse", "quote", "Other", 7.0, "LOW", "UNMEASURED", None, {"title": "Other"})
        for outcome in ("raises", "returns no run id"):
            with self.subTest(outcome=outcome), \
                    patch.object(ai_shorts, "generate_seo_suggestions", side_effect=records_then(outcome)):
                response = self.client.post("/api/ai-shorts/generate", json={"quote": QUOTE})
                self.assertEqual(response.status_code, 500)
                self.assertEqual([run["title"] for run in self.store.history_runs()], ["Other"])
                self.assertEqual(self.table_count("ai_short_plans"), 0)


class ReadAndDeleteTests(AiShortsTestCase):
    def test_plans_are_listed_newest_first_with_their_package_title(self):
        first = self.generate()
        second = self.generate(quote="The quietest people usually have the loudest minds.")

        listed = self.client.get("/api/ai-shorts/plans?limit=20").json()["plans"]
        self.assertEqual([item["id"] for item in listed], [second["id"], first["id"]])
        self.assertEqual(set(listed[0]), LIST_KEYS)
        self.assertEqual(listed[0]["quote"], "The quietest people usually have the loudest minds.")
        self.assertEqual(listed[0]["package_title"], self.store.history_run(second["analysis_run_id"])["title"])
        self.assertEqual((listed[0]["parts"], listed[0]["total_seconds"], listed[0]["generation_source"]), (2, 16, "fallback"))
        self.assertEqual(len(self.client.get("/api/ai-shorts/plans?limit=1").json()["plans"]), 1)
        self.assertEqual(len(self.client.get("/api/ai-shorts/plans").json()["plans"]), 2)
        for limit in (0, 101, "many"):
            with self.subTest(limit=limit):
                self.assertEqual(self.client.get(f"/api/ai-shorts/plans?limit={limit}").status_code, 422)

    def test_a_saved_plan_reads_back_as_the_generate_response(self):
        body = self.generate()
        response = self.client.get(f"/api/ai-shorts/plans/{body['id']}")
        self.assertEqual(response.status_code, 200)
        # All of it, except that the Flow guide is always today's (the fake
        # planner here writes its own placeholder guide).
        self.assertEqual(response.json(), {**body, "flow_steps": flow_steps(body["parts"]), "cautions": cautions(body["parts"])})

        missing = self.client.get(f"/api/ai-shorts/plans/{body['id'] + 1}")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()["error"]["code"], "http_error")

    def test_a_saved_plan_shows_todays_flow_guide_not_the_one_it_was_saved_with(self):
        # Plans saved before the guide was corrected still hold its old wording.
        body = self.generate()
        with self.store._connect() as connection:
            stored = json.loads(connection.execute(
                "SELECT plan_json FROM ai_short_plans WHERE id = ?", (body["id"],)).fetchone()[0])
            stored["flow_steps"] = ["1. 1080p upscaling needs the Ultra plan."]
            stored["cautions"] = ["Tick \"Altered or synthetic content\" in YouTube Studio."]
            connection.execute("UPDATE ai_short_plans SET plan_json = ? WHERE id = ?", (json.dumps(stored), body["id"]))

        plan = self.client.get(f"/api/ai-shorts/plans/{body['id']}").json()
        self.assertEqual(plan["flow_steps"], flow_steps(body["parts"]))
        self.assertEqual(plan["cautions"], cautions(body["parts"]))
        self.assertEqual(plan["shots"], body["shots"])

    def test_deleting_a_plan_deletes_its_run_and_queues_the_cloud_tombstone(self):
        body = self.generate()
        run_id = body["analysis_run_id"]
        now = datetime.now(timezone.utc).isoformat()
        with self.store._connect() as connection:
            # As cloud sync records a package it has pushed.
            connection.execute(
                """INSERT INTO cloud_sync_packages
                       (sync_uuid, analysis_run_id, origin_device_id, revision, content_hash, created_at, updated_at)
                   VALUES ('uuid-plan', ?, 'device-a', 1, 'hash', ?, ?)""", (run_id, now, now),
            )

        response = self.client.delete(f"/api/ai-shorts/plans/{body['id']}")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertEqual(self.client.get(f"/api/ai-shorts/plans/{body['id']}").status_code, 404)
        self.assertIsNone(self.store.history_run(run_id))
        self.assertEqual(self.table_count("ai_short_plans"), 0)
        with self.store._connect() as connection:
            tombstone = connection.execute(
                "SELECT revision, pending FROM cloud_sync_tombstones WHERE sync_uuid = 'uuid-plan'"
            ).fetchone()
        self.assertEqual(tuple(tombstone), (2, 1))
        self.assertEqual(self.client.delete(f"/api/ai-shorts/plans/{body['id']}").status_code, 404)

    def test_deleting_a_plan_asks_cloud_sync_to_push_the_deletion_soon(self):
        body = self.generate()
        cloud = MagicMock()
        cloud.request_run.return_value = {"state": "waiting", "run_requested": True}
        self.client.app.state.cloud_sync = cloud

        self.assertEqual(self.client.delete(f"/api/ai-shorts/plans/{body['id']}").status_code, 204)
        cloud.request_run.assert_called_once_with()
        # Nothing deleted, nothing to push.
        self.assertEqual(self.client.delete(f"/api/ai-shorts/plans/{body['id']}").status_code, 404)
        cloud.request_run.assert_called_once_with()

    def test_deleting_the_history_run_removes_the_plan_with_it(self):
        body = self.generate()
        self.assertEqual(self.client.delete(f"/api/history/runs/{body['analysis_run_id']}").status_code, 200)
        self.assertEqual(self.client.get(f"/api/ai-shorts/plans/{body['id']}").status_code, 404)
        self.assertEqual(self.table_count("ai_short_plans"), 0)
        self.assertEqual(self.client.get("/api/ai-shorts/plans").json(), {"plans": []})


class GeminiBudgetTests(AiShortsTestCase):
    @patch("win_engine.llm.gemini_client.time.sleep")
    @patch("win_engine.llm.gemini_client.httpx.post")
    def test_planner_gets_three_writer_three_and_request_at_most_six(self, post, _sleep):
        post.return_value = _gemini_reply()
        self.gemini_off.stop()
        planner_statuses: list[str] = []
        writer_statuses: list[str] = []
        self.planner.side_effect = _greedy_planner(planner_statuses)
        with patch.dict(os.environ, GEMINI_ENV), \
                patch.object(ai_shorts, "generate_seo_suggestions", side_effect=_greedy_writer(writer_statuses)):
            body = self.generate()

        self.assertEqual(post.call_count, ai_shorts.MAX_GEMINI_CALLS)
        self.assertEqual(planner_statuses, ["gemini_success", "gemini_success", "gemini_success", "gemini_budget_exhausted"])
        self.assertEqual(writer_statuses, ["gemini_success"] * 3 + ["gemini_budget_exhausted"])
        self.assertEqual(body["generation_source"], "gemini")
        self.assertEqual(body["package"]["source_page"], "ai_shorts")
        self.assertEqual(self.store.history_run(body["analysis_run_id"])["package"]["ai_shorts"]["plan_id"], body["id"])

    @patch("win_engine.llm.gemini_client.time.sleep")
    @patch("win_engine.llm.gemini_client.httpx.post")
    def test_one_deadline_covers_both_stages(self, post, _sleep):
        post.return_value = _gemini_reply()
        self.gemini_off.stop()
        planner_statuses: list[str] = []
        writer_statuses: list[str] = []
        self.planner.side_effect = _greedy_planner(planner_statuses)
        with patch.dict(os.environ, GEMINI_ENV), \
                patch.object(ai_shorts, "generate_seo_suggestions", side_effect=_greedy_writer(writer_statuses)):
            ai_shorts.generate_ai_short(self.store, quote=QUOTE, deadline_seconds=0.0)

        post.assert_not_called()
        self.assertEqual(set(planner_statuses) | set(writer_statuses), {"gemini_budget_exhausted"})


class RouteContractTests(AiShortsTestCase):
    def test_generating_is_a_costly_request_and_reading_is_not(self):
        self.assertTrue(is_costly(_request("POST", "/api/ai-shorts/generate")))
        self.assertFalse(is_costly(_request("GET", "/api/ai-shorts/plans")))
        self.assertFalse(is_costly(_request("GET", "/api/ai-shorts/plans/3")))
        self.assertFalse(is_costly(_request("DELETE", "/api/ai-shorts/plans/3")))

    def test_the_generate_route_runs_on_the_stricter_budget(self):
        self.settings.analyze_rate_limit_max_requests = 2
        client = TestClient(create_app(), raise_server_exceptions=False)
        # Refused requests count too: the budget is spent on the attempt, not the outcome.
        for _ in range(2):
            self.assertEqual(client.post("/api/ai-shorts/generate", json={"quote": "short"}).status_code, 422)
        throttled = client.post("/api/ai-shorts/generate", json={"quote": QUOTE})
        self.assertEqual(throttled.status_code, 429)
        self.assertEqual(throttled.json()["error"]["code"], "rate_limit_exceeded")
        self.planner.assert_not_called()
        # Reading plans is on the general budget and is still answered.
        self.assertEqual(client.get("/api/ai-shorts/plans").status_code, 200)

    def test_values_json_cannot_echo_back_are_refused_not_server_errors(self):
        # The refusal echoes the input; Infinity, NaN or a lone surrogate in it was a 500.
        quote = QUOTE.encode()
        for body in (
            b'{"quote": "' + quote + b'", "parts": 1e400}',
            b'{"quote": "' + quote + b'", "parts": NaN}',
            b'{"quote": "' + quote + b'", "\\ud800": "unknown field"}',
            b'{"quote": "\\ud800 ' + quote + b'"}',
        ):
            with self.subTest(body=body):
                response = self.client.post(
                    "/api/ai-shorts/generate", content=body, headers={"Content-Type": "application/json"},
                )
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(response.json()["error"]["code"], "validation_error")
        self.planner.assert_not_called()
        self.assertEqual(self.store.history_run_count(), 0)

    def test_the_page_is_one_of_the_interface_pages(self):
        self.assertIn("ai-shorts", routes._APP_PAGES)
        if (STATIC_DIR / "app" / "index.html").is_file():
            response = self.client.get("/ai-shorts")
            self.assertEqual(response.status_code, 200)
            self.assertIn('<div id="root"></div>', response.text)


class SchemaTests(unittest.TestCase):
    def test_a_version_11_database_gains_the_same_plan_table_as_a_new_one(self):
        def plan_schema(path: Path) -> tuple[list, int, list]:
            connection = sqlite3.connect(path)
            try:
                ddl = connection.execute(
                    "SELECT type, name, sql FROM sqlite_master WHERE tbl_name = 'ai_short_plans' ORDER BY type, name"
                ).fetchall()
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                recorded = connection.execute(
                    "SELECT version, description FROM schema_migrations WHERE version = 12"
                ).fetchall()
                return ddl, version, recorded
            finally:
                connection.close()

        with tempfile.TemporaryDirectory() as folder:
            new_path = Path(folder) / "new.db"
            migrations.prepare_database(str(new_path))
            migrated_path = Path(folder) / "v11.db"
            migrations.prepare_database(str(migrated_path))
            connection = sqlite3.connect(migrated_path)
            connection.execute("DROP TABLE ai_short_plans")
            connection.execute("DELETE FROM schema_migrations WHERE version = 12")
            connection.execute("PRAGMA user_version = 11")
            connection.commit()
            connection.close()

            result = migrations.prepare_database(str(migrated_path))
            self.assertEqual((result.old_version, result.new_version), (11, 12))
            self.assertEqual(migrations.CURRENT_SCHEMA_VERSION, 12)
            ddl, version, recorded = plan_schema(new_path)
            self.assertEqual([(kind, name) for kind, name, _ in ddl], [("index", "idx_ai_short_plans_run"), ("table", "ai_short_plans")])
            self.assertEqual((version, recorded), (12, [(12, migrations._V12_DESCRIPTION)]))
            self.assertEqual(plan_schema(migrated_path), (ddl, version, recorded))


if __name__ == "__main__":
    unittest.main()
