"""The YouTube OAuth flow returns the browser to the page that started it."""
from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from fastapi import FastAPI
from fastapi.testclient import TestClient

from win_engine.api import routes
from win_engine.core.config import Settings
from win_engine.integrations.youtube_channel import ChannelConnectError

GOOGLE_URL = "https://accounts.google.com/o/oauth2/auth?state=fixture"
COOKIE = "win_engine_oauth_return"


class OAuthReturnTests(unittest.TestCase):
    def setUp(self) -> None:
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = handle.name
        handle.close()
        # TestClient addresses the app as "testserver", so that is the redirect host here.
        self.settings = Settings(
            database_path=self.db_path,
            youtube_oauth_redirect_uri="http://testserver/oauth/youtube/callback",
        )
        app = FastAPI()
        app.include_router(routes.router)
        self.client = TestClient(app)
        self.patches = [
            patch.object(routes, "get_settings", return_value=self.settings),
            patch.object(routes.YouTubeChannelService, "authorization_url", return_value=GOOGLE_URL),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self) -> None:
        for item in self.patches:
            item.stop()
        for suffix in ("", "-wal", "-shm"):
            try:
                if os.path.exists(self.db_path + suffix):
                    os.remove(self.db_path + suffix)
            except OSError:
                pass

    def _connect(self, query: str = ""):
        return self.client.get(f"/youtube/channel/connect{query}", follow_redirects=False)

    def _callback(self, query: str, cookie: str | None = None):
        self.client.cookies.clear()
        if cookie is not None:
            self.client.cookies.set(COOKIE, cookie)
        return self.client.get(f"/oauth/youtube/callback{query}", follow_redirects=False)

    def test_connect_remembers_an_allowed_react_page(self):
        response = self._connect("?return_to=/next/settings")

        self.assertEqual(response.headers["location"], GOOGLE_URL)
        set_cookie = response.headers["set-cookie"]
        # Starlette quotes values containing "/"; the request parser unquotes them.
        self.assertIn(f'{COOKIE}="/next/settings"', set_cookie)
        self.assertIn("HttpOnly", set_cookie)
        self.assertIn("samesite=lax", set_cookie.lower())

    def test_the_cookie_set_on_connect_steers_the_callback(self):
        self.client.cookies.clear()
        self._connect("?return_to=/next/channel")  # the client keeps the cookie, as a browser would
        with patch.object(routes.YouTubeChannelService, "complete_authorization", return_value={}):
            response = self.client.get("/oauth/youtube/callback?code=abc&state=xyz", follow_redirects=False)

        self.assertEqual(response.headers["location"], "/next/channel?youtube=connected")

    def test_connect_without_a_valid_page_clears_any_earlier_choice(self):
        for query in ("", "?return_to=https://evil.example/", "?return_to=/next/history"):
            with self.subTest(query=query):
                set_cookie = self._connect(query).headers["set-cookie"]
                self.assertIn(f'{COOKIE}=""', set_cookie)
                self.assertIn("Max-Age=0", set_cookie)

    def test_denied_consent_returns_to_the_starting_page_with_the_reason(self):
        response = self._callback("?error=access_denied", cookie="/next/channel")

        self.assertEqual(response.headers["location"], "/next/channel?youtube=error&reason=access_denied")
        self.assertIn("Max-Age=0", response.headers["set-cookie"])

    def test_successful_connection_returns_to_settings(self):
        with patch.object(routes.YouTubeChannelService, "complete_authorization", return_value={}) as complete:
            response = self._callback("?code=abc&state=xyz", cookie="/next/settings")

        complete.assert_called_once_with(code="abc", state="xyz")
        self.assertEqual(response.headers["location"], "/next/settings?youtube=connected")

    def test_legacy_flow_without_a_cookie_keeps_the_root_redirect(self):
        with patch.object(routes.YouTubeChannelService, "complete_authorization", return_value={}):
            response = self._callback("?code=abc&state=xyz")

        self.assertEqual(response.headers["location"], "/?youtube=connected")

    def test_a_forged_cookie_cannot_redirect_off_site(self):
        with patch.object(
            routes.YouTubeChannelService,
            "complete_authorization",
            side_effect=ChannelConnectError("expired_state", "The connection request expired."),
        ):
            response = self._callback("?code=abc&state=xyz", cookie="https://evil.example/")

        self.assertEqual(response.headers["location"], "/?youtube=error&reason=expired_state")

    def test_an_unexpected_failure_is_logged_by_type_only(self):
        with (
            patch.object(
                routes.YouTubeChannelService,
                "complete_authorization",
                side_effect=RuntimeError("token response with secrets"),
            ),
            self.assertLogs("win_engine.api.routes", level="WARNING") as logs,
        ):
            response = self._callback("?code=abc&state=xyz", cookie="/next/settings")

        self.assertEqual(response.headers["location"], "/next/settings?youtube=error&reason=connect_failed")
        self.assertNotIn("secrets", "\n".join(logs.output))

    def test_connect_moves_to_the_redirect_host_first(self):
        # Browsing as localhost while Google returns to 127.0.0.1 would lose the return cookie.
        self.settings.youtube_oauth_redirect_uri = "http://127.0.0.1:8000/oauth/youtube/callback"
        response = self._connect("?return_to=/next/channel")

        target = urlsplit(response.headers["location"])
        self.assertEqual((target.scheme, target.netloc, target.path), ("http", "127.0.0.1:8000", "/youtube/channel/connect"))
        self.assertEqual(parse_qs(target.query), {"return_to": ["/next/channel"]})
        self.assertNotIn("set-cookie", response.headers)

    def test_connect_does_not_bounce_on_another_spelling_of_the_redirect_host(self):
        # Browsers lower-case the host and drop a default port; redirecting on
        # the raw text sent them back to the same address forever.
        for redirect_uri, host in (
            ("http://LocalHost:8000/oauth/youtube/callback", "localhost:8000"),
            ("http://127.0.0.1:80/oauth/youtube/callback", "127.0.0.1"),
            ("https://TestServer:443/oauth/youtube/callback", "testserver"),
            ("http://[::1]:8000/oauth/youtube/callback", "[::1]:8000"),
        ):
            with self.subTest(redirect_uri=redirect_uri):
                self.settings.youtube_oauth_redirect_uri = redirect_uri
                response = self.client.get("/youtube/channel/connect", headers={"Host": host}, follow_redirects=False)
                self.assertEqual(response.headers["location"], GOOGLE_URL)

    def test_connect_still_moves_for_another_port_or_a_malformed_host(self):
        self.settings.youtube_oauth_redirect_uri = "http://testserver:8000/oauth/youtube/callback"
        for host in ("testserver", "testserver:80", "testserver:abc"):
            with self.subTest(host=host):
                response = self.client.get("/youtube/channel/connect", headers={"Host": host}, follow_redirects=False)
                self.assertEqual(urlsplit(response.headers["location"]).netloc, "testserver:8000")

    def test_connect_without_oauth_setup_returns_to_the_page_with_a_reason(self):
        with patch.object(routes.YouTubeChannelService, "authorization_url", side_effect=ValueError("not configured")):
            response = self._connect("?return_to=/next/settings")

        self.assertEqual(response.headers["location"], "/next/settings?youtube=error&reason=not_configured")

    def test_free_text_in_the_error_parameter_is_not_echoed(self):
        response = self._callback("?error=call%20555-0100%20for%20help", cookie="/next/settings")

        self.assertEqual(response.headers["location"], "/next/settings?youtube=error&reason=unknown")


if __name__ == "__main__":
    unittest.main()
