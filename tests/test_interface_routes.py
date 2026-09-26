"""The interface is served at the root; old addresses redirect to a known page."""

import unittest

from fastapi.testclient import TestClient

from win_engine.api import routes
from win_engine.api.app import STATIC_DIR, create_app


@unittest.skipUnless((STATIC_DIR / "app" / "index.html").is_file(), "React build output is not present")
class InterfaceRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app(), raise_server_exceptions=False)

    def test_the_root_and_every_page_serve_the_interface(self):
        for path in ("/", *(f"/{page}" for page in routes._APP_PAGES)):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn('<div id="root"></div>', response.text)

    def test_old_addresses_redirect_to_the_same_page(self):
        cases = {
            "/next": "/",
            "/next/creator": "/creator",
            # A sign-in that started before the move still reports its result.
            "/next/settings?youtube=connected": "/settings?youtube=connected",
            "/next/history/12": "/history",
            "/app": "/",
            "/dashboard_view": "/",
        }
        for old, new in cases.items():
            with self.subTest(old=old):
                response = self.client.get(old, follow_redirects=False)
                self.assertEqual(response.status_code, 308)
                self.assertEqual(response.headers["location"], new)

    def test_a_crafted_old_address_cannot_leave_the_site(self):
        for old in ("/next//evil.example", "/next/%2F%2Fevil.example", "/next/\\evil.example", "/next/unknown-page"):
            with self.subTest(old=old):
                response = self.client.get(old, follow_redirects=False)
                self.assertEqual(response.headers["location"], "/")

    def test_unknown_paths_stay_json_404s(self):
        # Pages are listed one by one, so a missing API path is never answered with a web page.
        response = self.client.get("/no-such-page")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "http_error")
        self.assertEqual(self.client.get("/api/no-such-endpoint").status_code, 404)


if __name__ == "__main__":
    unittest.main()
