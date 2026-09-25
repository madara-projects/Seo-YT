"""Requests that change data are refused when another website sends them."""
from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from win_engine.api import routes
from win_engine.api.app import create_app, is_cross_site_write
from win_engine.core.config import Settings


def _request(method: str, headers: dict[str, str]) -> Request:
    raw = [(key.lower().encode(), value.encode()) for key, value in headers.items()]
    return Request({"type": "http", "method": method, "path": "/", "headers": raw})


class CrossSiteCheckTests(unittest.TestCase):
    def test_reads_are_never_refused(self):
        for method in ("GET", "HEAD", "OPTIONS"):
            self.assertFalse(is_cross_site_write(_request(method, {"sec-fetch-site": "cross-site"})))

    def test_browser_marking_decides_for_writes(self):
        self.assertTrue(is_cross_site_write(_request("POST", {"sec-fetch-site": "cross-site"})))
        self.assertTrue(is_cross_site_write(_request("DELETE", {"sec-fetch-site": "same-site"})))
        self.assertFalse(is_cross_site_write(_request("POST", {"sec-fetch-site": "same-origin"})))
        self.assertFalse(is_cross_site_write(_request("POST", {"sec-fetch-site": "none"})))

    def test_without_marking_the_origin_must_match_the_host(self):
        host = {"host": "127.0.0.1:8000"}
        self.assertFalse(is_cross_site_write(_request("POST", host)))
        self.assertFalse(is_cross_site_write(_request("POST", {**host, "origin": "http://127.0.0.1:8000"})))
        self.assertTrue(is_cross_site_write(_request("POST", {**host, "origin": "https://evil.example"})))
        self.assertTrue(is_cross_site_write(_request("POST", {**host, "origin": "null"})))


class CrossSiteMiddlewareTests(unittest.TestCase):
    def setUp(self) -> None:
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = handle.name
        handle.close()
        self.patches = [
            patch.object(routes, "get_settings", return_value=Settings(database_path=self.db_path)),
            patch.object(routes.YouTubeChannelService, "disconnect"),
        ]
        for item in self.patches:
            item.start()
        self.disconnect = routes.YouTubeChannelService.disconnect
        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        for item in self.patches:
            item.stop()
        for suffix in ("", "-wal", "-shm"):
            try:
                if os.path.exists(self.db_path + suffix):
                    os.remove(self.db_path + suffix)
            except OSError:
                pass

    def test_another_site_cannot_disconnect_the_channel(self):
        response = self.client.post("/youtube/channel/disconnect", headers={"Sec-Fetch-Site": "cross-site"})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "cross_site_request")
        self.disconnect.assert_not_called()

    def test_a_foreign_origin_is_refused_even_without_browser_marking(self):
        response = self.client.post("/youtube/channel/disconnect", headers={"Origin": "https://evil.example"})

        self.assertEqual(response.status_code, 403)
        self.disconnect.assert_not_called()

    def test_the_apps_own_pages_still_work(self):
        response = self.client.post("/youtube/channel/disconnect", headers={"Sec-Fetch-Site": "same-origin"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"disconnected": True})
        self.disconnect.assert_called_once()

    def test_deletes_are_covered_too(self):
        response = self.client.delete("/api/history/runs/1", headers={"Sec-Fetch-Site": "cross-site"})

        self.assertEqual(response.status_code, 403)

    def test_cross_site_reads_are_untouched(self):
        response = self.client.get("/meta", headers={"Sec-Fetch-Site": "cross-site"})

        self.assertEqual(response.status_code, 200)


class AdminTokenTests(unittest.TestCase):
    def _check(self, provided: str | None, expected: str = "correct-token") -> None:
        headers = {"X-Admin-Token": provided} if provided is not None else {}
        settings = Settings(app_environment="production", admin_api_token=expected)
        routes._require_admin(_request("POST", headers), settings)

    def test_only_the_configured_token_passes(self):
        self._check("correct-token")
        for wrong in ("", "correct-token-2", "correct-toke", None):
            with self.subTest(wrong=wrong), self.assertRaises(HTTPException) as caught:
                self._check(wrong)
            self.assertEqual(caught.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
