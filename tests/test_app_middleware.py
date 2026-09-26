"""Host checking, error envelopes, headers, budgets and body limits on every response."""
from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from google.auth.exceptions import RefreshError
from starlette.requests import Request

from win_engine.api import routes
from win_engine.api.app import create_app, is_costly, request_host, route_template
from win_engine.core.config import Settings
from win_engine.integrations.youtube_channel import YouTubeUnavailable


def _request(method: str, path: str, host: str = "127.0.0.1:8000") -> Request:
    return Request({"type": "http", "method": method, "path": path, "headers": [(b"host", host.encode())]})


class PureHelperTests(unittest.TestCase):
    def test_host_names_drop_ports_and_brackets(self):
        self.assertEqual(request_host(_request("GET", "/", "127.0.0.1:8000")), "127.0.0.1")
        self.assertEqual(request_host(_request("GET", "/", "LocalHost")), "localhost")
        self.assertEqual(request_host(_request("GET", "/", "[::1]:8000")), "::1")

    def test_allowed_hosts_are_read_like_the_host_header(self):
        settings = Settings(allowed_hosts="MyHost:8000, [::1]:8000, 127.0.0.1, [fe80::1], ::1")
        self.assertEqual(settings.allowed_host_set, {"myhost", "::1", "127.0.0.1", "fe80::1"})
        for host in ("myhost:8000", "MYHOST", "[::1]:8000", "[fe80::1]:80"):
            self.assertIn(request_host(_request("GET", "/", host)), settings.allowed_host_set, host)

    def test_one_budget_per_route_not_per_record(self):
        self.assertEqual(route_template("/api/ideas/12/generate"), "/api/ideas/{id}/generate")
        self.assertEqual(
            route_template("/api/experiment-center/experiments/3/assignments/41"),
            "/api/experiment-center/experiments/{id}/assignments/{id}",
        )
        self.assertEqual(route_template("/ideas"), "/ideas")

    def test_every_spelling_the_id_parser_reads_as_a_number_is_one_record(self):
        # The request path arrives decoded, so "%201" is " 1" here.
        for path in ("/api/ideas/1.0/generate", "/api/ideas/+1/generate", "/api/ideas/ 1/generate",
                     "/api/ideas/1_0/generate", "/api/ideas/01/generate", "/api/ideas/-1/generate"):
            self.assertEqual(route_template(path), "/api/ideas/{id}/generate", path)
        # Static files keep one budget per file, including names that start with a digit.
        for path in ("/app-assets/theme-init.js", "/app-assets/assets/0123abc.js"):
            self.assertEqual(route_template(path), path)

    def test_quota_spending_writes_are_costly(self):
        for path in ("/analyze", "/diagnostics", "/api/ideas/4/generate", "/api/watchlist/videos/2/research",
                     "/api/history/runs/9/link-video", "/api/audits/5/refresh", "/api/watchlist/videos"):
            self.assertTrue(is_costly(_request("POST", path)), path)
        self.assertFalse(is_costly(_request("GET", "/api/watchlist/videos")))
        self.assertFalse(is_costly(_request("POST", "/api/watchlist/videos/2/analyze-outlier")))
        self.assertFalse(is_costly(_request("PATCH", "/api/ideas/4")))


class MiddlewareTests(unittest.TestCase):
    def setUp(self) -> None:
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = handle.name
        handle.close()
        self.settings = Settings(
            database_path=self.db_path,
            allowed_hosts="127.0.0.1,localhost,::1,testserver",
            analyze_rate_limit_max_requests=1,
            max_request_bytes=2048,
        )
        self.patches = [
            patch.object(routes, "get_settings", return_value=self.settings),
            patch("win_engine.core.config.get_settings", return_value=self.settings),
        ]
        for item in self.patches:
            item.start()
        self.client = TestClient(create_app(), raise_server_exceptions=False)

    def tearDown(self) -> None:
        for item in self.patches:
            item.stop()
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(self.db_path + suffix)
            except OSError:
                pass

    def assert_envelope(self, response, status: int, code: str) -> dict:
        self.assertEqual(response.status_code, status)
        error = response.json()["error"]
        self.assertEqual(error["code"], code)
        # Every response, refusals and failures included, is traceable and hardened.
        self.assertEqual(error["request_id"], response.headers["x-request-id"])
        self.assertIn("default-src 'self'", response.headers["content-security-policy"])
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        return error

    def test_a_rebound_domain_is_refused(self):
        response = self.client.get("/health", headers={"Host": "attacker.example:8000"})
        self.assert_envelope(response, 400, "invalid_host")
        self.assertEqual(self.client.get("/health", headers={"Host": "localhost:8000"}).status_code, 200)

    def test_validation_errors_say_what_is_wrong(self):
        error = self.assert_envelope(self.client.patch("/api/ideas/1", json={}), 422, "validation_error")
        self.assertEqual(error["message"], "Provide at least one idea field to update.")
        self.assertIsInstance(error["details"], list)

        error = self.assert_envelope(self.client.post("/api/demand/research", json={"topic": ""}), 422, "validation_error")
        self.assertTrue(error["message"].startswith("topic: "))

    def test_unknown_routes_and_methods_use_the_same_envelope(self):
        self.assert_envelope(self.client.get("/no-such-route"), 404, "http_error")
        response = self.client.delete("/health")
        self.assert_envelope(response, 405, "http_error")
        self.assertIn("GET", response.headers["allow"])

    def test_refusals_carry_the_request_id_and_headers(self):
        self.assert_envelope(
            self.client.post("/youtube/channel/disconnect", headers={"Sec-Fetch-Site": "cross-site"}),
            403,
            "cross_site_request",
        )

    def test_costly_routes_share_one_budget_across_records(self):
        first = self.client.post("/api/ideas/1/generate", json={})
        self.assertEqual(first.status_code, 404)  # no such idea, but the attempt counts
        self.assert_envelope(self.client.post("/api/ideas/2/generate", json={}), 429, "rate_limit_exceeded")
        # Other routes keep their own budget.
        self.assertEqual(self.client.get("/api/ideas").status_code, 200)

    def test_every_spelling_of_a_record_id_shares_the_route_budget(self):
        # The id parser reads each of these as 1 (or 10), so none may open a fresh budget.
        self.assertEqual(self.client.post("/api/ideas/1/generate", json={}).status_code, 404)
        for spelling in ("1.0", "1.00", "+1", "%201", "1_0", "01"):
            with self.subTest(spelling=spelling):
                self.assert_envelope(
                    self.client.post(f"/api/ideas/{spelling}/generate", json={}), 429, "rate_limit_exceeded"
                )

    def test_an_allowed_host_listed_with_a_port_is_accepted(self):
        settings = Settings(database_path=self.db_path, allowed_hosts="myhost:8000,[::1]:8000")
        with patch("win_engine.core.config.get_settings", return_value=settings):
            client = TestClient(create_app(), raise_server_exceptions=False)
        for host in ("myhost:8000", "myhost", "[::1]:8000"):
            self.assertEqual(client.get("/meta", headers={"Host": host}).status_code, 200, host)
        self.assert_envelope(client.get("/meta", headers={"Host": "otherhost:8000"}), 400, "invalid_host")

    def test_unhandled_errors_are_enveloped_and_logged_once(self):
        with patch.object(routes.HistoryStore, "history_runs", side_effect=RuntimeError("boom")):
            with self.assertLogs("win_engine.api.app", level="ERROR") as logs:
                response = self.client.get("/api/history/runs")
        error = self.assert_envelope(response, 500, "internal_server_error")
        self.assertEqual(error["message"], "An unexpected error occurred.")
        self.assertEqual(len(logs.records), 1)
        self.assertNotIn("boom", response.text)

    def test_only_well_formed_request_ids_are_echoed(self):
        self.assertEqual(self.client.get("/meta", headers={"X-Request-Id": "abc-123"}).headers["x-request-id"], "abc-123")
        replaced = self.client.get("/meta", headers={"X-Request-Id": "<script>alert(1)</script>"})
        self.assertRegex(replaced.headers["x-request-id"], r"^[0-9a-f]{32}$")

    def test_oversized_bodies_are_refused_before_parsing(self):
        response = self.client.post("/analyze", content=b"{" + b"x" * 4096 + b"}", headers={"Content-Type": "application/json"})
        self.assert_envelope(response, 413, "payload_too_large")

    def test_interactive_docs_are_off_but_the_schema_stays(self):
        self.assertEqual(self.client.get("/docs").status_code, 404)
        self.assertEqual(self.client.get("/openapi.json").status_code, 200)

    def test_youtube_outages_and_revoked_grants_have_their_own_statuses(self):
        quota = YouTubeUnavailable("YouTube's API quota or rate limit was reached. Try again later.", status_code=429)
        with patch.object(routes.YouTubeChannelService, "refresh", side_effect=quota):
            error = self.assert_envelope(self.client.post("/youtube/channel/refresh"), 429, "youtube_unavailable")
        self.assertIn("quota", error["message"])

        fresh_budget = TestClient(create_app(), raise_server_exceptions=False)
        with patch.object(routes.YouTubeChannelService, "refresh", side_effect=RefreshError("invalid_grant")):
            error = self.assert_envelope(fresh_budget.post("/youtube/channel/refresh"), 401, "youtube_reconnect_required")
        self.assertNotIn("invalid_grant", error["message"])


if __name__ == "__main__":
    unittest.main()
