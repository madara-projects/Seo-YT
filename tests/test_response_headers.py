"""Security and caching headers on responses served by the app."""
from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from win_engine.api.app import STATIC_DIR, create_app


class ResponseHeaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app())

    def test_thumbnails_are_the_only_new_image_origin(self):
        policy = self.client.get("/meta").headers["content-security-policy"]

        self.assertIn("img-src 'self' data: https://i.ytimg.com;", policy)
        self.assertIn("default-src 'self';", policy)
        self.assertIn("connect-src 'self';", policy)

    def test_scripts_run_only_from_the_apps_own_files(self):
        policy = self.client.get("/meta").headers["content-security-policy"]
        self.assertIn("script-src 'self';", policy)
        # With no 'unsafe-inline', an inline script or handler in either page would not run.
        pages = [STATIC_DIR / "index.html", STATIC_DIR / "app" / "index.html"]
        for page in (path for path in pages if path.exists()):
            html = page.read_text(encoding="utf-8")
            self.assertNotRegex(html, r"\son[a-z]+\s*=", page.name)
            self.assertNotRegex(html, r"<script(?![^>]*\bsrc=)[^>]*>", page.name)

    def test_only_hashed_build_files_are_cacheable(self):
        assets = sorted((STATIC_DIR / "app" / "assets").glob("*.js"))
        if not assets:
            self.skipTest("React build output is not present")

        asset = self.client.get(f"/app-assets/assets/{assets[0].name}")
        self.assertEqual(asset.status_code, 200)
        self.assertEqual(asset.headers["cache-control"], "public, max-age=31536000, immutable")

        missing = self.client.get("/app-assets/assets/does-not-exist.js")
        self.assertEqual(missing.headers["cache-control"], "no-store")
        self.assertEqual(self.client.get("/meta").headers["cache-control"], "no-store")


if __name__ == "__main__":
    unittest.main()
