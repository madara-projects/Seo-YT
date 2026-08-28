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
        executable_path = os.environ.get("SEO_YT_BROWSER_EXECUTABLE")
        launch_options = {"headless": True}
        if executable_path:
            launch_options["executable_path"] = executable_path
        cls.browser = cls.playwright.chromium.launch(**launch_options)

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

    def open_experiment_form(self):
        details = self.page.locator("#experimentForm details")
        if details.get_attribute("open") is None:
            details.locator("summary").click()
        self.assertIsNotNone(details.get_attribute("open"))

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
            ("#ideas", "nav-ideas", "view-ideas"),
            ("#demand", "nav-demand", "view-demand"),
            ("#watchlist", "nav-watchlist", "view-watchlist"),
            ("#audits", "nav-audits", "view-audits"),
            ("#experiments", "nav-experiments", "view-experiments"),
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

    def test_sidebar_collapses_persists_and_navigation_still_works(self):
        self.open("#dashboard")
        expanded_width = self.page.locator("#appSidebar").evaluate("el => el.getBoundingClientRect().width")
        self.assertGreater(expanded_width, 200)

        self.page.locator("#sidebarToggle").click()
        self.page.wait_for_timeout(300)
        collapsed_width = self.page.locator("#appSidebar").evaluate("el => el.getBoundingClientRect().width")
        self.assertLess(collapsed_width, 100)
        self.assertEqual(self.page.locator("#sidebarToggle").get_attribute("aria-expanded"), "false")
        toggle_center = self.page.locator("#sidebarToggle").evaluate(
            "el => { const r = el.getBoundingClientRect(); return r.left + r.width / 2; }"
        )
        icon_center = self.page.locator("#nav-dashboard svg").evaluate(
            "el => { const r = el.getBoundingClientRect(); return r.left + r.width / 2; }"
        )
        self.assertAlmostEqual(toggle_center, icon_center, delta=1)
        self.assertEqual(
            self.page.locator("#appSidebar").evaluate("el => getComputedStyle(el).scrollbarWidth"),
            "none",
        )
        self.assertEqual(
            self.page.locator("#sidebarToggle").evaluate("el => getComputedStyle(el).borderRadius"),
            self.page.locator("#nav-dashboard").evaluate("el => getComputedStyle(el).borderRadius"),
        )

        self.page.locator("#nav-settings").click()
        self.assertEqual(self.page.evaluate("window.location.hash"), "#settings")
        self.assertEqual(self.page.locator(".page-view.active").get_attribute("id"), "view-settings")

        self.page.reload(wait_until="domcontentloaded")
        self.page.wait_for_timeout(300)
        self.assertTrue(self.page.locator("body").evaluate("el => el.classList.contains('sidebar-collapsed')"))
        self.page.locator("#sidebarToggle").click()
        self.page.wait_for_timeout(300)
        self.assertGreater(self.page.locator("#appSidebar").evaluate("el => el.getBoundingClientRect().width"), 200)
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
        for hash_name in ("#dashboard", "#creator", "#ideas", "#demand", "#watchlist", "#audits", "#experiments", "#analytics", "#history", "#settings"):
            self.open(hash_name)
            text = self.page.locator("body").inner_text()
            for marker in ("Ã", "Â", "â", "ðŸ", "ï¸"):
                self.assertNotIn(marker, text, f"unexpected encoding artifact on {hash_name}: {marker}")
        self.assert_clean_browser()

    def test_watchlist_add_refresh_and_outlier_evidence(self):
        self.open("#watchlist")
        self.page.locator("#watchChannelId").fill("UC-fixture")
        self.page.locator("#watchChannelForm button[type='submit']").click()
        self.page.wait_for_selector("text=Fixture Public Channel")
        self.page.locator("#watchVideoId").fill("https://youtu.be/AbCdEfGhI12")
        self.page.locator("#watchVideoForm button[type='submit']").click()
        self.page.wait_for_selector("text=Fixture camera outlier")
        self.page.locator("#watchVideos [data-watch-id='1']").click()
        self.page.wait_for_selector("#watchDetail >> text=Outlier analysis")
        self.page.locator("#watchDetail [data-watch-action='research']").click()
        self.page.wait_for_selector("#watchDetail >> text=9,300 views")
        self.page.locator("#watchDetail [data-watch-action='outlier']").click()
        self.page.wait_for_selector("#watchDetail >> text=observational outlier signal")
        text = self.page.locator("#watchDetail").inner_text().lower()
        self.assertIn("possible_outlier", text)
        self.assertIn("not a viral prediction", text)
        self.assertEqual(self.router.count("POST", "/api/watchlist/channels"), 1)
        self.assertEqual(self.router.count("POST", "/api/watchlist/videos"), 1)
        self.assert_clean_browser()

    def test_published_audit_navigation_list_and_intent_actual_detail(self):
        self.replace_router(include_link=True)
        self.open("#audits")
        self.page.wait_for_selector("text=Published rainy highway title")
        self.assertEqual(self.page.locator("[data-audit-link='9']").count(), 1)
        self.page.locator("[data-audit-link='9']").click()
        self.page.wait_for_selector("#auditDetail >> text=Audit not run")
        self.page.locator("#auditDetail [data-audit-action='refresh']").click()
        self.page.wait_for_selector("#auditDetail >> text=PUBLISHED VIDEO AUDIT")
        text = self.page.locator("#auditDetail").inner_text()
        self.assertIn("Generated rainy highway title", text)
        self.assertIn("Selected rainy highway title", text)
        self.assertIn("Published rainy highway title", text)
        self.assertIn("NOT ESTABLISHED", text)
        self.assertIn("Enough observation time is available for comparison.", text)
        self.assertEqual(self.router.count("POST", "/api/audits/9/refresh"), 1)
        self.assert_clean_browser()

    def test_published_audit_empty_state_is_truthful(self):
        self.open("#audits")
        self.page.wait_for_selector("text=No linked published videos")
        self.assertIn("0 linked video", self.page.locator("#auditStatus").inner_text())
        self.assertIn("immutable", self.page.locator("#auditStatus").inner_text().lower())
        self.assert_clean_browser()

    def test_experiment_creation_duplicate_click_guard_and_detail(self):
        self.replace_router(include_link=True)
        self.open("#experiments")
        self.open_experiment_form()
        self.page.locator("#experimentName").fill("Curiosity title comparison")
        self.page.locator("#experimentHypothesis").fill("Specific curiosity may be associated with stronger observed retention.")
        self.page.locator("#experimentControl").fill("Descriptive title")
        self.page.locator("#experimentVariant").fill("Specific curiosity title")
        self.page.locator("#experimentCreateBtn").evaluate("b => { b.click(); b.click(); }")
        self.page.wait_for_selector("#experimentDetail >> text=Curiosity title comparison")
        text = self.page.locator("#experimentDetail").inner_text()
        self.assertIn("PLANNED EXPERIMENT", text)
        self.assertIn("NOT CAUSAL PROOF", text)
        self.assertEqual(self.router.count("POST", "/api/experiment-center/experiments"), 1)
        self.assert_clean_browser()

    def test_experiment_assignment_comparison_and_insufficient_evidence(self):
        self.replace_router(include_link=True)
        self.open("#experiments")
        self.open_experiment_form()
        self.page.locator("#experimentName").fill("Opening test")
        self.page.locator("#experimentHypothesis").fill("A direct opening may be associated with stronger average viewing.")
        self.page.locator("#experimentControl").fill("Normal opening")
        self.page.locator("#experimentVariant").fill("Direct opening")
        self.page.locator("#experimentCreateBtn").click()
        self.page.wait_for_selector("#experimentAssignVideo")
        self.page.locator("#experimentAssignVideo").select_option("9")
        self.page.locator("#experimentAssignRole").select_option("control")
        self.page.locator("[data-experiment-action='assign']").click()
        self.page.wait_for_selector("#experimentDetail >> text=Published rainy highway title")
        self.page.locator("[data-experiment-action='compare']").evaluate("b => { b.click(); b.click(); }")
        self.page.wait_for_selector("#experimentDetail >> text=INSUFFICIENT EVIDENCE")
        detail = self.page.locator("#experimentDetail").inner_text()
        self.assertIn("no direction is claimed", detail.lower())
        self.assertIn("No fake statistical significance", detail)
        self.assertEqual(self.router.count("POST", "/api/experiment-center/experiments/1/assignments"), 1)
        self.assertEqual(self.router.count("POST", "/api/experiment-center/experiments/1/compare"), 1)
        self.assert_clean_browser()

    def test_demand_research_provenance_limitations_and_duplicate_click_guard(self):
        self.open("#demand")
        self.assertIn("No demand", self.page.locator("#demandList").inner_text())
        self.page.locator("#demandTopic").fill("camera comparison")
        self.page.locator("#demandForm").evaluate("form => form.requestSubmit()")
        self.page.wait_for_selector("#demandDetail >> text=active_topic")
        text = self.page.locator("#demandDetail").inner_text().lower()
        self.assertIn("public_observation", text)
        self.assertIn("not monthly search volume", text)
        self.assertIn("no official monthly search-volume", text)
        self.page.locator("#demandDetail [data-demand-action='generate']").evaluate("b => { b.click(); b.click(); }")
        self.page.wait_for_selector("#demandActionStatus >> text=Package saved")
        self.assertEqual(self.router.count("POST", "/api/demand/research/1/generate"), 1)
        self.assert_clean_browser()

    def test_idea_demand_to_existing_generation_flow(self):
        self.open("#ideas")
        self.page.wait_for_selector("text=Rainy highway quote idea")
        self.page.locator("[data-idea-id='1']").click()
        self.page.wait_for_selector("#ideaDetail [data-idea-action='demand']")
        self.page.locator("#ideaDetail [data-idea-action='demand']").click()
        self.page.wait_for_selector("#ideaDetail >> text=emerging_signal")
        self.page.locator("#ideaDetail [data-idea-action='generate']").click()
        self.page.wait_for_selector("#ideaDetail [data-idea-action='history']")
        self.assertEqual(self.router.count("POST", "/api/ideas/1/demand-research"), 1)
        self.assertEqual(self.router.count("POST", "/api/ideas/1/generate"), 1)
        self.assert_clean_browser()

    def test_ideas_workspace_renders_honest_empty_evidence_and_dated_research(self):
        self.open("#ideas")
        self.page.wait_for_selector("text=Rainy highway quote idea")
        self.page.locator("[data-idea-id='1']").click()
        detail = self.page.locator("#ideaDetail")
        self.page.wait_for_selector("#ideaDetail >> text=Research unavailable")
        self.assertIn("Research unavailable", detail.inner_text())
        self.assertIn("No search volume", detail.inner_text())
        detail.locator("[data-idea-action='research']").click()
        self.page.wait_for_selector("text=Public rainy road observation")
        text = detail.inner_text()
        self.assertIn("not monthly search volume", text)
        self.assertIn("Not enough personal evidence", text)
        self.assertIn("Captured:", text)
        self.assertIn("Published:", text)
        self.assertEqual(self.router.count("POST", "/api/ideas/1/research"), 1)
        self.assert_clean_browser()

    def test_ideas_create_generate_and_status_filter_workflow(self):
        self.open("#ideas")
        self.page.locator("#ideaTopic").fill("Sunset couple quote idea")
        self.page.locator("#ideaNotes").fill("Two people beneath the same sky.")
        self.page.locator("#ideaCreateForm").evaluate("form => form.requestSubmit()")
        self.page.wait_for_selector("text=Idea saved permanently in SQLite")
        self.assertEqual(self.router.count("POST", "/api/ideas"), 1)
        self.page.locator("#ideaDetail [data-idea-action='generate']").click()
        self.page.wait_for_selector("#ideaDetail [data-idea-action='history']")
        self.assertIn("package generated", self.page.locator("#ideaDetail").inner_text().lower())
        self.assertEqual(self.router.count("POST", "/api/ideas/2/generate"), 1)
        self.page.locator("#ideasStatusFilter").select_option("package_generated")
        self.page.wait_for_timeout(100)
        self.assertIn("Sunset couple quote idea", self.page.locator("#ideasList").inner_text())
        self.assertNotIn("Rainy highway quote idea", self.page.locator("#ideasList").inner_text())
        self.assert_clean_browser()

    def test_creator_success_has_one_analyze_request(self):
        self.open("#creator")
        self.page.locator("#scriptInput").fill("A reflective quote over a rainy highway.")
        self.page.locator("#analyzeBtn").click()
        self.page.wait_for_selector("text=The Truth About Letting Go 💔 #shorts")
        self.assertEqual(self.router.count("POST", "/analyze"), 1)
        output_text = self.page.locator("#outputContent").inner_text()
        final_title = self.page.locator("#outputContent .creator-output-title").inner_text()
        self.assertIn("A reflective short", output_text)
        self.assertEqual(final_title.lower().count("#shorts"), 1)
        self.assertTrue(any(ord(char) >= 0x2600 for char in final_title))
        self.assertIn("upload timing guidance", output_text.lower())
        self.assertIn("6:00 PM - 8:00 PM Asia/Kolkata", output_text)
        self.assertIn("Personalized upload timing is not yet established", output_text)
        self.assertNotIn("viral shorts", output_text.lower())
        self.assertIn("Inferred", self.page.locator("#creatorBriefProvenance").inner_text())
        self.assert_clean_browser()

    def test_creator_research_stage_renders_existing_evidence_without_extra_requests(self):
        self.open("#creator")
        self.page.locator("#scriptInput").fill("A reflective quote over a rainy highway.")
        self.page.locator("#analyzeBtn").click()
        self.page.wait_for_selector("text=The Truth About Letting Go 💔 #shorts")
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
        self.page.wait_for_selector("text=The Truth About Letting Go 💔 #shorts")
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
        self.page.wait_for_selector("text=Second: The Truth About Letting Go 💔 #shorts", timeout=5000)
        self.assertEqual(self.router.count("POST", "/analyze"), 2)
        self.assertIn("Second: The Truth About Letting Go 💔 #shorts", self.page.locator("#outputContent").inner_text())
        self.assertNotIn("First: The Truth About Letting Go 💔 #shorts", self.page.locator("#outputContent").inner_text())
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
        self.page.wait_for_selector("text=The Truth About Letting Go 💔 #shorts")
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
        self.page.wait_for_selector("text=The Truth About Letting Go 💔 #shorts")
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
        self.page.wait_for_selector("text=First: The Truth About Letting Go 💔 #shorts")
        self.assertEqual(self.router.count("POST", "/analyze"), 1)
        self.assert_clean_browser()

    def test_package_comparison_selection_is_persisted_and_survives_navigation(self):
        self.open("#creator")
        self.page.locator("#scriptInput").fill("A reflective quote over a rainy highway.")
        self.page.locator("#analyzeBtn").click()
        self.page.wait_for_selector("text=The Truth About Letting Go 💔 #shorts")
        self.page.locator("[data-testid='creator-stage-compare']").click()
        self.assertGreaterEqual(self.page.locator("[data-testid='package-option-card']").count(), 3)
        self.page.locator("[data-testid='select-package-b']").click()
        self.page.wait_for_selector("text=Selection saved")
        self.assertEqual(self.page.locator("[data-testid='select-package-b']").get_attribute("aria-pressed"), "true")
        self.page.locator("[data-testid='creator-stage-decision']").click()
        self.assertIn("package b recorded in history", self.page.locator("#creatorDecisionPanel").inner_text().lower())
        self.page.locator("[data-testid='creator-stage-compare']").click()
        self.assertEqual(self.page.locator("[data-testid='select-package-b']").get_attribute("aria-pressed"), "true")
        self.assertEqual(self.router.count("POST", "/analyze"), 1)
        self.assertEqual(self.router.count("PUT", "/api/history/runs/1/selection"), 1)
        self.assert_clean_browser()

    def test_decision_stage_separates_evidence_heuristics_and_unknowns(self):
        self.open("#creator")
        self.page.locator("#scriptInput").fill("A reflective quote over a rainy highway.")
        self.page.locator("#analyzeBtn").click()
        self.page.wait_for_selector("text=The Truth About Letting Go 💔 #shorts")
        self.page.locator("[data-testid='creator-stage-decision']").click()
        text = self.page.locator("#creatorDecisionPanel").inner_text()
        self.assertIn("Public observation", text)
        self.assertIn("Local heuristic", text)
        self.assertIn("unavailable before publishing", text.lower())
        self.assertIn("do not predict actual ctr", text.lower())
        self.assertIn("never changes or publishes a YouTube video", text)
        self.assertEqual(self.router.count("POST", "/analyze"), 1)
        self.assert_clean_browser()

    def test_retention_assistant_is_real_traceable_creator_output(self):
        self.open("#creator")
        self.page.locator("#scriptInput").fill("A reflective quote over a rainy highway.")
        self.page.locator("#analyzeBtn").click()
        self.page.wait_for_selector("text=The Truth About Letting Go 💔 #shorts")
        self.page.locator("[data-testid='creator-stage-angle']").click()
        panel = self.page.locator("[data-testid='creator-retention-panel']")
        text = panel.inner_text()
        self.assertIn("hook, pacing and retention assistant", text.lower())
        self.assertIn("first_frame_text_dense", text.lower())
        self.assertIn("Reveal the exact text in readable steps", text)
        self.assertIn("HEURISTIC", text.upper())
        self.assertIn("insufficient_evidence", text)
        self.assertIn("does not predict or guarantee", text)
        self.assertEqual(self.router.count("POST", "/analyze"), 1)
        self.assert_clean_browser()

    def test_retention_package_alignment_updates_after_persisted_selection(self):
        self.open("#creator")
        self.page.locator("#scriptInput").fill("A reflective quote over a rainy highway.")
        self.page.locator("#analyzeBtn").click()
        self.page.wait_for_selector("text=The Truth About Letting Go 💔 #shorts")
        self.page.locator("[data-testid='creator-stage-compare']").click()
        self.page.locator("[data-testid='select-package-b']").click()
        self.page.wait_for_selector("text=Selection saved")
        self.page.locator("[data-testid='creator-stage-decision']").click()
        panel = self.page.locator("[data-testid='creator-retention-panel']")
        self.assertIn("Package B / package-b", panel.inner_text())
        self.assertIn("Status: aligned", panel.inner_text())
        self.assertEqual(self.router.count("PUT", "/api/history/runs/1/selection"), 1)
        self.assert_clean_browser()

    def test_checklist_is_local_persists_and_resets_after_selection_change(self):
        self.open("#creator")
        self.page.locator("#scriptInput").fill("A reflective quote over a rainy highway.")
        self.page.locator("#analyzeBtn").click()
        self.page.wait_for_selector("text=The Truth About Letting Go 💔 #shorts")
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
        self.page.wait_for_selector("text=The Truth About Letting Go 💔 #shorts")
        self.page.locator("[data-testid='creator-stage-decision']").click()
        self.page.get_by_role("button", name="Copy selected upload package").click()
        self.page.wait_for_function("window.__copiedPackage && window.__copiedPackage.includes('DESCRIPTION')")
        copied = self.page.evaluate("window.__copiedPackage")
        self.assertIn("The Truth About Letting Go 💔 #shorts", copied)
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
        self.page.wait_for_selector("text=The Truth About Letting Go 💔 #shorts")
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
        self.assertEqual(self.page.locator("#historyRunCount").inner_text(), "1 saved package")
        self.page.locator("#historySearch").fill("highway")
        self.page.wait_for_selector("text=1 of 1 packages match")
        scroll_before = self.page.locator("main.app-container").evaluate("el => el.scrollTop")
        self.page.get_by_role("button", name="View package").click()
        self.page.wait_for_selector("text=Didn't I Deserve the Bare Minimum?")
        self.page.wait_for_selector("text=Original video content / script")
        self.assertEqual(self.page.locator("main.app-container").evaluate("el => el.scrollTop"), scroll_before)
        self.assertEqual(self.router.count("GET", "/api/history/runs/1"), 1)
        self.assert_clean_browser()

    def test_history_linked_performance_explains_pending_retention(self):
        self.replace_router(include_link=True)
        self.open("#history")
        self.page.get_by_role("button", name="View package").click()
        self.page.wait_for_selector("#historyDetail >> text=Retention evidence")
        detail = self.page.locator("#historyDetail").inner_text()
        self.assertIn("0 of 5 comparable videos", detail)
        self.assertIn("Retention pending", detail)
        self.assertIn("Live counts", detail)
        self.assertIn("1,152", detail)
        self.assertIn("Save local labels", detail)
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
