from __future__ import annotations

import os
import unittest
from urllib.parse import urlparse

try:
    from playwright.sync_api import Page, sync_playwright
except ImportError:  # pragma: no cover - optional development dependency
    Page = object
    sync_playwright = None

from .fixtures import FixtureRouter


@unittest.skipUnless(sync_playwright, "Install requirements-browser.txt and Chromium to run browser tests")
class CriticalDashboardBrowserTests(unittest.TestCase):
    """Quota-free Phase 3B browser checks against deterministic intercepted fixtures."""

    @classmethod
    def setUpClass(cls):
        cls.base_url = os.environ.get("SEO_YT_BROWSER_BASE_URL", "http://127.0.0.1:8000")
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.page: Page = self.browser.new_page()
        self.router = FixtureRouter(self.page)
        self.page_errors: list[str] = []
        self.console_errors: list[str] = []
        self.page.on("pageerror", lambda error: self.page_errors.append(str(error)))
        self.page.on("console", lambda message: self.console_errors.append(message.text) if message.type == "error" else None)

    def tearDown(self):
        self.page.close()

    def open(self, hash_name: str):
        self.page.goto(self.base_url + "/" + hash_name, wait_until="domcontentloaded")
        self.page.wait_for_timeout(250)

    def replace_router(self, **options):
        self.page.close()
        self.page = self.browser.new_page()
        self.router = FixtureRouter(self.page, **options)
        self.page_errors = []
        self.console_errors = []
        self.page.on("pageerror", lambda error: self.page_errors.append(str(error)))
        self.page.on("console", lambda message: self.console_errors.append(message.text) if message.type == "error" else None)

    def assert_clean_browser(self, *, allow_console_errors: tuple[str, ...] = ()):
        self.assertFalse(self.page_errors, "uncaught page errors: " + repr(self.page_errors))
        unexpected = [error for error in self.console_errors if not any(expected in error for expected in allow_console_errors)]
        self.assertFalse(unexpected, "console errors: " + repr(unexpected))
        allowed_intercepted_hosts = {"fonts.googleapis.com", "fonts.gstatic.com"}
        unexpected_external = [
            url for url in self.router.external_requests
            if urlparse(url).hostname not in allowed_intercepted_hosts
        ]
        self.assertFalse(unexpected_external, "unexpected external requests: " + repr(unexpected_external))

    def test_navigation_direct_routes_and_sidebar(self):
        for hash_name, nav_id, view_id in (
            ("#dashboard", "nav-dashboard", "view-dashboard"),
            ("#creator", "nav-creator", "view-creator"),
            ("#analytics", "nav-analytics", "view-analytics"),
            ("#history", "nav-history", "view-history"),
            ("#settings", "nav-settings", "view-settings"),
        ):
            self.open(hash_name)
            self.assertEqual(self.page.locator(".page-view.active").get_attribute("id"), view_id)
            self.assertTrue(self.page.locator("#" + nav_id).evaluate("el => el.classList.contains('active')"))
        self.open("#dashboard")
        self.page.locator("#nav-creator").click()
        self.assertEqual(self.page.evaluate("window.location.hash"), "#creator")
        self.assertEqual(self.page.locator(".page-view.active").get_attribute("id"), "view-creator")
        self.assert_clean_browser()

    def test_extracted_assets_and_legacy_rollback_route(self):
        self.open("#dashboard")
        self.assertEqual(self.page.locator("link[href='/static/css/app.css']").count(), 1)
        self.assertEqual(self.page.locator("script[type='module'][src='/static/js/app.js']").count(), 1)
        self.assertEqual(self.page.evaluate("fetch('/static/js/api.js').then(r => r.status)"), 200)
        self.page.goto(self.base_url + "/dashboard_legacy", wait_until="domcontentloaded")
        self.page.wait_for_selector("#view-dashboard")
        self.assertTrue(self.page.locator("#view-dashboard").count())
        self.assert_clean_browser()

    def test_active_frontend_has_no_mojibake_markers(self):
        for hash_name in ("#dashboard", "#creator", "#analytics", "#history", "#settings"):
            self.open(hash_name)
            text = self.page.locator("body").inner_text()
            for marker in ("Ã", "Â", "â", "ðŸ", "ï¸"):
                self.assertNotIn(marker, text, f"unexpected encoding artifact on {hash_name}: {marker}")
        self.assert_clean_browser()

    def test_creator_success_has_one_analyze_request(self):
        self.open("#creator")
        self.page.locator("#scriptInput").fill("A reflective quote over a rainy highway.")
        self.page.locator("#analyzeBtn").click()
        self.page.wait_for_selector("text=The Truth About Letting Go #Shorts")
        self.assertEqual(self.router.count("POST", "/analyze"), 1)
        self.assertIn("A reflective short", self.page.locator("#outputContent").inner_text())
        self.assertIn("Inferred", self.page.locator("#creatorBriefProvenance").inner_text())
        self.assert_clean_browser()

    def test_creator_research_stage_renders_existing_evidence_without_extra_requests(self):
        self.open("#creator")
        self.page.locator("#scriptInput").fill("A reflective quote over a rainy highway.")
        self.page.locator("#analyzeBtn").click()
        self.page.wait_for_selector("text=The Truth About Letting Go #Shorts")
        self.page.locator("[data-testid='creator-stage-research']").click()
        panel = self.page.locator("#creatorResearchPanel")
        self.assertTrue(panel.is_visible())
        panel_text = panel.inner_text()
        self.assertIn("available", panel_text.lower())
        self.assertIn("rainy highway quote", panel_text.lower())
        self.assertIn("Public observation", panel_text)
        self.assertIn("Local heuristic", panel_text)
        self.assertIn("When Letting Go Finally Feels Quiet", panel_text)
        self.assertEqual(self.router.count("POST", "/analyze"), 1)
        self.assert_clean_browser()

    def test_creator_research_missing_data_is_explicitly_unavailable(self):
        self.page.close()
        self.page = self.browser.new_page()
        self.router = FixtureRouter(self.page, creator_research="empty")
        self.page_errors = []
        self.console_errors = []
        self.page.on("pageerror", lambda error: self.page_errors.append(str(error)))
        self.page.on("console", lambda message: self.console_errors.append(message.text) if message.type == "error" else None)
        self.open("#creator")
        self.page.locator("#scriptInput").fill("A research-empty fixture.")
        self.page.locator("#analyzeBtn").click()
        self.page.wait_for_selector("text=The Truth About Letting Go #Shorts")
        self.page.locator("[data-testid='creator-stage-research']").click()
        panel_text = self.page.locator("#creatorResearchPanel").inner_text()
        self.assertIn("unavailable", panel_text.lower())
        self.assertIn("no research evidence was returned", panel_text.lower())
        self.assertNotIn("winning", panel_text.lower())
        self.assertEqual(self.router.count("POST", "/analyze"), 1)
        self.assert_clean_browser()

    def test_creator_stale_response_cannot_overwrite_newer_analysis(self):
        self.page.add_init_script("window.__SEO_YT_TEST__ = true;")
        self.page.close()
        self.page = self.browser.new_page()
        self.page.add_init_script("window.__SEO_YT_TEST__ = true;")
        self.router = FixtureRouter(self.page, analyze_delay_ms=300)
        self.page_errors = []
        self.console_errors = []
        self.page.on("pageerror", lambda error: self.page_errors.append(str(error)))
        self.page.on("console", lambda message: self.console_errors.append(message.text) if message.type == "error" else None)
        self.open("#creator")
        self.page.locator("#scriptInput").fill("first analysis")
        self.page.evaluate("void window.__seoYtCreatorTestHooks.submitAnalyze();")
        self.page.locator("#scriptInput").fill("second analysis")
        self.page.evaluate("void window.__seoYtCreatorTestHooks.submitAnalyze();")
        self.page.wait_for_selector("text=Second: The Truth About Letting Go #Shorts", timeout=5000)
        self.assertEqual(self.router.count("POST", "/analyze"), 2)
        self.assertIn("Second: The Truth About Letting Go #Shorts", self.page.locator("#outputContent").inner_text())
        self.assertNotIn("First: The Truth About Letting Go #Shorts", self.page.locator("#outputContent").inner_text())
        self.assert_clean_browser()

    def test_creator_workflow_stages_preserve_form_across_navigation(self):
        self.open("#creator")
        self.page.locator("#scriptInput").fill("A quote over a sunset highway.")
        self.page.locator("details.accordion").locator("summary").click()
        self.page.locator("#target_audience").fill("People healing from loss")
        self.page.locator("[data-testid='creator-stage-brief']").click()
        self.assertEqual(self.page.locator("#creatorWorkflow").get_attribute("data-stage"), "brief")
        self.assertTrue(self.page.locator("[data-testid='creator-stage-brief']").evaluate("el => el.classList.contains('active')"))
        self.page.locator("#nav-dashboard").click()
        self.page.locator("#nav-creator").click()
        self.assertEqual(self.page.locator("#scriptInput").input_value(), "A quote over a sunset highway.")
        self.assertEqual(self.page.locator("#target_audience").input_value(), "People healing from loss")
        self.assertEqual(self.router.count("POST", "/analyze"), 0)
        self.assert_clean_browser()

    def test_creator_advanced_values_survive_collapse_and_submit_once(self):
        self.open("#creator")
        self.page.locator("#scriptInput").fill("A reflective quote over a rainy highway.")
        details = self.page.locator("details.accordion")
        details.locator("summary").click()
        self.page.locator("#target_audience").fill("People healing from one-sided relationships")
        self.page.locator("#viewer_promise").fill("Feel understood in under a minute")
        self.page.locator("#unique_angle").fill("Rainy highway visual with a first-person quote")
        self.page.locator("#proof").fill("Original on-screen quote")
        self.page.locator("#video_format").select_option("story")
        self.page.locator("#title_style").select_option("curiosity")
        self.page.locator("#thumbnail_idea").fill("Rainy road, high-contrast quote text")
        details.locator("summary").click()
        self.assertIsNone(details.get_attribute("open"))
        self.page.locator("#analyzeBtn").click()
        self.page.wait_for_selector("text=The Truth About Letting Go #Shorts")
        self.assertEqual(self.router.count("POST", "/analyze"), 1)
        payload = self.router.bodies("POST", "/analyze")[0]
        self.assertEqual(payload["target_audience"], "People healing from one-sided relationships")
        self.assertEqual(payload["viewer_promise"], "Feel understood in under a minute")
        self.assertEqual(payload["unique_angle"], "Rainy highway visual with a first-person quote")
        self.assertEqual(payload["proof"], "Original on-screen quote")
        self.assertEqual(payload["video_format"], "story")
        self.assertEqual(payload["title_style"], "curiosity")
        self.assertEqual(payload["thumbnail_idea"], "Rainy road, high-contrast quote text")
        self.assertIn("Creator-entered", self.page.locator("#creatorBriefProvenance").inner_text())
        self.assert_clean_browser()

    def test_creator_complete_happy_path_through_all_stages(self):
        self.open("#creator")
        self.page.locator("#scriptInput").fill("A reflective quote over a rainy highway.")
        for stage in ("brief", "research", "angle"):
            self.page.locator(f"[data-creator-stage='{stage}']").click()
            self.assertEqual(self.page.locator("#creatorWorkflow").get_attribute("data-stage"), stage)
        self.page.locator("[data-creator-stage='idea']").click()
        self.page.locator("#analyzeBtn").click()
        self.page.wait_for_selector("text=The Truth About Letting Go #Shorts")
        self.assertEqual(self.page.locator("#creatorWorkflow").get_attribute("data-stage"), "packaging")
        for stage, panel_id in (
            ("research", "creatorResearchPanel"),
            ("angle", "creatorAnglePanel"),
            ("packaging", "resultsPanel"),
            ("compare", "creatorComparePanel"),
            ("decision", "creatorDecisionPanel"),
            ("checklist", "creatorChecklistPanel"),
        ):
            self.page.locator(f"[data-creator-stage='{stage}']").click()
            self.assertTrue(self.page.locator("#" + panel_id).is_visible())
        self.assertEqual(self.router.count("POST", "/analyze"), 1)
        self.assert_clean_browser()

    def test_creator_loading_and_duplicate_click_protection(self):
        self.replace_router(analyze_delay_ms=350)
        self.open("#creator")
        self.page.locator("#scriptInput").fill("first delayed analysis")
        loading_state = self.page.evaluate("""() => {
            const button = document.getElementById('analyzeBtn');
            button.click();
            button.click();
            return {disabled: button.disabled, text: button.innerText};
        }""")
        self.assertTrue(loading_state["disabled"])
        self.assertIn("Analyzing and packaging", loading_state["text"])
        self.page.wait_for_selector("text=First: The Truth About Letting Go #Shorts")
        self.assertEqual(self.router.count("POST", "/analyze"), 1)
        self.assert_clean_browser()

    def test_package_comparison_selection_is_local_and_survives_navigation(self):
        self.open("#creator")
        self.page.locator("#scriptInput").fill("A reflective quote over a rainy highway.")
        self.page.locator("#analyzeBtn").click()
        self.page.wait_for_selector("text=The Truth About Letting Go #Shorts")
        self.page.locator("[data-testid='creator-stage-compare']").click()
        self.assertGreaterEqual(self.page.locator("[data-testid='package-option-card']").count(), 3)
        self.page.locator("[data-testid='select-package-b']").click()
        self.assertEqual(self.page.locator("[data-testid='select-package-b']").get_attribute("aria-pressed"), "true")
        self.page.locator("[data-testid='creator-stage-decision']").click()
        self.assertIn("package b selected locally", self.page.locator("#creatorDecisionPanel").inner_text().lower())
        self.page.locator("[data-testid='creator-stage-compare']").click()
        self.assertEqual(self.page.locator("[data-testid='select-package-b']").get_attribute("aria-pressed"), "true")
        self.assertEqual(self.router.count("POST", "/analyze"), 1)
        self.assert_clean_browser()

    def test_decision_stage_separates_evidence_heuristics_and_unknowns(self):
        self.open("#creator")
        self.page.locator("#scriptInput").fill("A reflective quote over a rainy highway.")
        self.page.locator("#analyzeBtn").click()
        self.page.wait_for_selector("text=The Truth About Letting Go #Shorts")
        self.page.locator("[data-testid='creator-stage-decision']").click()
        text = self.page.locator("#creatorDecisionPanel").inner_text()
        self.assertIn("Public observation", text)
        self.assertIn("Local heuristic", text)
        self.assertIn("unavailable before publishing", text.lower())
        self.assertIn("do not predict actual ctr", text.lower())
        self.assertIn("does not change the saved History record", text)
        self.assertEqual(self.router.count("POST", "/analyze"), 1)
        self.assert_clean_browser()

    def test_checklist_is_local_persists_and_resets_after_selection_change(self):
        self.open("#creator")
        self.page.locator("#scriptInput").fill("A reflective quote over a rainy highway.")
        self.page.locator("#analyzeBtn").click()
        self.page.wait_for_selector("text=The Truth About Letting Go #Shorts")
        self.page.locator("[data-testid='creator-stage-checklist']").click()
        self.page.locator("[data-checklist-key='title']").check()
        self.page.locator("[data-checklist-key='description']").check()
        self.page.locator("[data-testid='creator-stage-decision']").click()
        self.page.locator("[data-testid='creator-stage-checklist']").click()
        self.assertTrue(self.page.locator("[data-checklist-key='title']").is_checked())
        self.assertTrue(self.page.locator("[data-checklist-key='description']").is_checked())
        self.page.locator("[data-testid='creator-stage-compare']").click()
        self.page.locator("[data-testid='select-package-b']").click()
        self.page.locator("[data-testid='creator-stage-checklist']").click()
        self.assertFalse(self.page.locator("[data-checklist-key='title']").is_checked())
        self.assertFalse(self.page.locator("[data-checklist-key='description']").is_checked())
        self.assertEqual(self.router.count("POST", "/analyze"), 1)
        self.assert_clean_browser()

    def test_safe_copy_and_export_have_no_network_side_effects(self):
        self.page.add_init_script("Object.defineProperty(navigator, 'clipboard', {value: {writeText: async value => { window.__copiedPackage = value; }}, configurable: true});")
        self.open("#creator")
        self.page.locator("#scriptInput").fill("A reflective quote over a rainy highway.")
        self.page.locator("#analyzeBtn").click()
        self.page.wait_for_selector("text=The Truth About Letting Go #Shorts")
        self.page.locator("[data-testid='creator-stage-decision']").click()
        self.page.get_by_role("button", name="Copy selected upload package").click()
        self.page.wait_for_function("window.__copiedPackage && window.__copiedPackage.includes('DESCRIPTION')")
        copied = self.page.evaluate("window.__copiedPackage")
        self.assertIn("The Truth About Letting Go #Shorts", copied)
        with self.page.expect_download() as download_info:
            self.page.get_by_role("button", name="Export full analysis and local decision").click()
        self.assertTrue(download_info.value.suggested_filename.startswith("seo-analysis-"))
        self.assertEqual(self.router.count("POST", "/analyze"), 1)
        self.assert_clean_browser()

    def test_creator_remount_navigation_does_not_duplicate_listeners(self):
        self.open("#creator")
        for _ in range(3):
            self.page.locator("#nav-dashboard").click()
            self.page.locator("#nav-creator").click()
        self.page.locator("#scriptInput").fill("A reflective quote over a rainy highway.")
        self.page.locator("#analyzeBtn").click()
        self.page.wait_for_selector("text=The Truth About Letting Go #Shorts")
        self.assertEqual(self.router.count("POST", "/analyze"), 1)
        self.assert_clean_browser()

    def test_creator_error_uses_standard_envelope(self):
        self.page.close()
        self.page = self.browser.new_page()
        self.router = FixtureRouter(self.page, analyze_error=True)
        self.page_errors = []
        self.console_errors = []
        self.page.on("pageerror", lambda error: self.page_errors.append(str(error)))
        self.page.on("console", lambda message: self.console_errors.append(message.text) if message.type == "error" else None)
        self.open("#creator")
        self.page.locator("#scriptInput").fill("A deterministic failure fixture.")
        self.page.locator("#analyzeBtn").click()
        self.page.locator("#creatorStatusPanel").get_by_text("Fixture analysis failed.", exact=False).wait_for()
        self.assertEqual(self.router.count("POST", "/analyze"), 1)
        self.assertIn("Request ID: browser-fixture-1", self.page.locator("body").inner_text())
        self.page.locator("[data-testid='creator-stage-research']").click()
        self.assertIn("API error", self.page.locator("#creatorResearchPanel").inner_text())
        self.assert_clean_browser(allow_console_errors=("503 (Service Unavailable)",))

    def test_dashboard_uses_neutral_initial_metrics_and_truthful_labels(self):
        self.open("#dashboard")
        self.page.wait_for_selector("text=Saved records")
        self.assertEqual(self.page.locator("#dashMetricOpp").inner_text(), "Not available / 100")
        body_text = self.page.locator("body").inner_text()
        for misleading in ("8.8", "61.4", "High CTR", "Viral Hashtags", "Winning Patterns Engine", "Live Sync"):
            self.assertNotIn(misleading, body_text)
        body_lower = body_text.lower()
        self.assertIn("public research trends", body_lower)
        self.assertIn("not enough mature evidence", body_lower)
        self.assert_clean_browser()

    def test_analytics_distinguishes_current_data_from_mature_evidence(self):
        self.open("#analytics")
        self.page.wait_for_selector("text=Current data")
        body_text = self.page.locator("body").inner_text()
        self.assertIn("not mature 24h/7d/28d learning evidence", body_text)
        self.assertIn("no mature evidence yet.", body_text.lower())
        self.assert_clean_browser()

    def test_history_detail_and_initial_request_counts(self):
        self.open("#history")
        self.page.wait_for_selector("text=Rainy Highway Reflection")
        self.assertEqual(self.router.count("GET", "/api/history/runs"), 1)
        self.page.get_by_role("button", name="Open").click()
        self.page.wait_for_selector("text=Didn't I Deserve the Bare Minimum?")
        self.assertEqual(self.router.count("GET", "/api/history/runs/1"), 1)
        self.assert_clean_browser()

    def test_analytics_fixture_has_no_automatic_refresh_when_disconnected(self):
        self.open("#analytics")
        self.page.locator("#anaChannelName").wait_for(state="visible")
        self.assertEqual(self.router.count("POST", "/youtube/channel/refresh"), 0)
        self.assertEqual(self.router.count("GET", "/api/history"), 1)
        self.assertEqual(self.router.count("GET", "/api/published-videos"), 1)
        self.assertEqual(self.router.count("GET", "/api/learning/cohorts"), 1)
        self.assert_clean_browser()

    def test_settings_renders_disconnected_and_collector_status(self):
        self.open("#settings")
        self.page.wait_for_selector("text=Fixture OAuth is disconnected.")
        self.page.wait_for_selector("text=Status: disabled")
        self.assertEqual(self.router.count("GET", "/youtube/channel/status"), 1)
        self.assertEqual(self.router.count("GET", "/api/snapshot-collector/status"), 1)
        self.assert_clean_browser()

    def test_settings_connected_oauth_state_is_truthful_and_non_mutating(self):
        self.replace_router(oauth_state="connected")
        self.open("#settings")
        self.page.wait_for_selector("text=Connected to Fixture Creator Channel")
        self.assertFalse(self.page.locator("#settRefreshBtn").is_hidden())
        self.assertFalse(self.page.locator("#settDisconnectBtn").is_hidden())
        self.assertTrue(self.page.locator("#settConnectBtn").is_hidden())
        self.assertEqual(self.router.count("POST", "/youtube/channel/refresh"), 0)
        self.assertEqual(self.router.count("POST", "/youtube/channel/disconnect"), 0)
        self.assert_clean_browser()

    def test_collector_dry_run_is_explicitly_non_mutating(self):
        self.page.close()
        self.page = self.browser.new_page()
        self.router = FixtureRouter(self.page, collector_state="dry-run")
        self.page_errors = []
        self.console_errors = []
        self.page.on("pageerror", lambda error: self.page_errors.append(str(error)))
        self.page.on("console", lambda message: self.console_errors.append(message.text) if message.type == "error" else None)
        self.open("#settings")
        self.page.wait_for_selector("text=Status: dry-run")
        self.assertIn("no YouTube/Gemini calls or database writes", self.page.locator("#settCollectorDetails").inner_text())
        self.assert_clean_browser()

    def test_collector_error_shows_normalized_message_and_request_id(self):
        self.page.close()
        self.page = self.browser.new_page()
        self.router = FixtureRouter(self.page, collector_error=True)
        self.page_errors = []
        self.console_errors = []
        self.page.on("pageerror", lambda error: self.page_errors.append(str(error)))
        self.page.on("console", lambda message: self.console_errors.append(message.text) if message.type == "error" else None)
        self.open("#settings")
        self.page.wait_for_selector("text=Collector status unavailable in fixture.")
        self.assertIn("Request ID: collector-fixture-1", self.page.locator("#settCollectorDetails").inner_text())
        self.assert_clean_browser(allow_console_errors=("503 (Service Unavailable)",))

    def test_collector_reported_error_is_not_presented_as_healthy(self):
        self.page.close()
        self.page = self.browser.new_page()
        self.router = FixtureRouter(self.page, collector_state="error")
        self.page_errors = []
        self.console_errors = []
        self.page.on("pageerror", lambda error: self.page_errors.append(str(error)))
        self.page.on("console", lambda message: self.console_errors.append(message.text) if message.type == "error" else None)
        self.open("#settings")
        self.page.wait_for_selector("text=Status: error")
        self.assertIn("Collector error: Fixture collector failure.", self.page.locator("#settCollectorDetails").inner_text())
        self.assert_clean_browser()

    def test_linked_video_refresh_has_one_request_per_click(self):
        self.page.close()
        self.page = self.browser.new_page()
        self.router = FixtureRouter(self.page, include_link=True)
        self.page_errors = []
        self.console_errors = []
        self.page.on("pageerror", lambda error: self.page_errors.append(str(error)))
        self.page.on("console", lambda message: self.console_errors.append(message.text) if message.type == "error" else None)
        self.open("#analytics")
        self.page.get_by_role("button", name="Refresh snapshot").click()
        self.page.wait_for_timeout(150)
        self.assertEqual(self.router.count("POST", "/api/published-videos/9/refresh"), 1)
        self.assert_clean_browser()


if __name__ == "__main__":
    unittest.main()
