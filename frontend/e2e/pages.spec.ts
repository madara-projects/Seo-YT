import { expect, test, type Page } from "@playwright/test";
import {
  HISTORY_RUNS,
  VIEWPORTS,
  blockWrites,
  collectErrors,
  expectNoHorizontalOverflow,
  mockHistoryRuns,
} from "./helpers";
import { AI_SHORTS_PLAN } from "../src/test/fixtures/aiShorts";

/**
 * Dashboard and History against the running backend. Requires
 * `docker compose up -d` at the repository root. No request that could change
 * saved data reaches the server: every write is answered by a test's own
 * route or aborted.
 */

test.beforeEach(async ({ page }) => {
  await blockWrites(page);
});

test.describe("Dashboard", () => {
  test("renders against live data with no console errors", async ({ page }) => {
    const errors = collectErrors(page);
    await page.goto("/dashboard");

    await expect(page.getByRole("heading", { name: "Dashboard", level: 1 })).toBeVisible();
    await expect(page.getByText("Avg opportunity score")).toBeVisible();
    await expect(page.getByText("Connected channel")).toBeVisible();

    expect(errors).toEqual([]);
  });

  test("labels unavailable channel metrics instead of showing zero", async ({ page }) => {
    // No channel and no linked videos: the channel-derived cards must read as
    // unavailable rather than as a fabricated 0.
    await page.route("**/api/history", (route) =>
      route.fulfill({
        json: {
          learning: {},
          scorecard: { total_runs: 3 },
          owned_performance: { channel: null, latest_sync: null, estimated_watch_minutes: null, linked_videos_count: 0 },
        },
      }),
    );
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: "Dashboard", level: 1 })).toBeVisible();
    await expect(page.getByText("Connect and refresh your channel in Settings.")).toBeVisible();

    for (const label of ["Views (28 days)", "Estimated watch time"]) {
      const card = page.locator(`[data-stat="${label}"]`);
      await expect(card).toContainText("Unavailable");
      await expect(card).not.toContainText(/^0$/);
    }
  });

  test("labels linked-video watch time as its own measure", async ({ page }) => {
    // Without a channel sync the backend adds up the linked videos that have
    // watch time; that is not a 28-day channel total and must not look like one.
    await page.route("**/api/history", (route) =>
      route.fulfill({
        json: {
          learning: {},
          scorecard: { total_runs: 41 },
          owned_performance: {
            channel: null,
            latest_sync: null,
            estimated_watch_minutes: 132,
            linked_videos_count: 19,
            linked_videos_with_watch_time: 4,
          },
        },
      }),
    );
    await page.goto("/dashboard");

    const card = page.locator('[data-stat="Estimated watch time"]');
    await expect(card).toContainText("2.2 hrs");
    await expect(card).toContainText("Linked videos");
    await expect(card).toContainText("Across 4 of your 19 linked videos");
    await expect(card).not.toContainText("Not connected");
  });

  test("draws the angle comparison without SVG errors", async ({ page }) => {
    // Regression: rows once had an `angle` field, which Recharts passes to
    // each label as its rotation, producing transform="rotate(Story, ...)".
    const errors = collectErrors(page);
    await page.route("**/api/history", (route) =>
      route.fulfill({
        json: {
          learning: {
            angle_effectiveness: [
              { content_angle: "Authority", run_count: 4, avg_title_score: 8.1 },
              { content_angle: "Story", run_count: 9, avg_title_score: 7.4 },
              { content_angle: "Mistake", run_count: 2, avg_title_score: 6.9 },
            ],
            recent_runs: [],
            winning_titles: [],
            retention_pattern: [],
          },
          scorecard: { total_runs: 15, avg_title_score: 7.5, avg_opportunity_score: 40 },
          owned_performance: {},
        },
      }),
    );

    await page.goto("/dashboard");
    const chart = page.locator(".recharts-wrapper");
    await expect(chart).toBeVisible();
    await expect(chart.getByText("8.1", { exact: true })).toBeVisible();
    await expect(chart.getByText("Mistake", { exact: true })).toBeVisible();

    expect(errors).toEqual([]);
  });

  test("hands a draft to Creator without analysing on the Dashboard", async ({ page }) => {
    let analyzeCalls = 0;
    await page.route("**/analyze", (route) => {
      analyzeCalls += 1;
      return route.abort();
    });

    await page.goto("/dashboard");
    await page.getByRole("button", { name: "Quote short" }).click();
    await page.getByRole("button", { name: "Open in Creator" }).click();

    await expect(page.getByRole("heading", { name: "Creator", level: 1 })).toBeVisible();
    await expect(page.getByLabel("Script")).toHaveValue(/biggest betrayal/);
    expect(analyzeCalls).toBe(0);
  });

  for (const [name, viewport] of Object.entries(VIEWPORTS)) {
    test(`lays out without horizontal overflow at ${name}`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await page.goto("/dashboard");
      await expect(page.getByRole("heading", { name: "Dashboard", level: 1 })).toBeVisible();

      // Wait for the loaded state rather than the skeletons, so the check (and
      // the screenshot) reflects the layout a user actually sees.
      await expect(page.locator('[data-stat="Avg opportunity score"]')).toBeVisible();

      await expectNoHorizontalOverflow(page);
      await page.screenshot({ path: `screenshots/dashboard-${name}.png` });
    });
  }
});

/**
 * Waits for the list to settle before counting: the rows arrive asynchronously,
 * so counting immediately after navigation always reports zero.
 */
async function savedRowCount(page: Page): Promise<number> {
  const rows = page.getByTestId("history-row");
  await expect(page.getByTestId("history-result-summary")).not.toHaveText(
    /Loading saved packages/,
  );
  return rows.count();
}

/** A package the AI Shorts page saved, listed above the History fixtures. */
const SHORT_RUN = {
  id: 903,
  created_at: "2026-09-28T09:12:44Z",
  title: AI_SHORTS_PLAN.package!.title!,
  query: AI_SHORTS_PLAN.quote,
  content_angle: "Story",
  opportunity_score: null,
  opportunity_label: "UNMEASURED",
  title_score: 8.5,
  selected_package_id: null,
  linked_youtube_video_id: null,
  source_page: "ai_shorts",
  ai_shorts: { plan_id: AI_SHORTS_PLAN.id, parts: 2, total_seconds: 16, language: "english", generation_source: "gemini" },
};

/** The History fixtures plus `SHORT_RUN`, its detail and its plan. Reads only. */
async function mockShortsHistory(page: Page) {
  await mockHistoryRuns(page);
  // Registered later, so it answers first and hands everything else back.
  await page.route("**/api/history/runs**", (route) => {
    const request = route.request();
    if (request.method() !== "GET") return route.fallback();
    const path = new URL(request.url()).pathname;
    if (path === "/api/history/runs") {
      return route.fulfill({
        json: { runs: [SHORT_RUN, ...HISTORY_RUNS], total: HISTORY_RUNS.length + 1, limit: 100, offset: 0 },
      });
    }
    if (path === `/api/history/runs/${SHORT_RUN.id}`) {
      return route.fulfill({
        json: {
          ...SHORT_RUN,
          package: { ...AI_SHORTS_PLAN.package, source_page: "ai_shorts", ai_shorts: SHORT_RUN.ai_shorts },
          selected_package: null,
          linked_video_report: { linked: false },
        },
      });
    }
    return route.fallback();
  });
  await page.route(`**/api/ai-shorts/plans/${AI_SHORTS_PLAN.id}`, (route) =>
    route.request().method() === "GET"
      ? route.fulfill({ json: { ...AI_SHORTS_PLAN, analysis_run_id: SHORT_RUN.id } })
      : route.fallback(),
  );
}

test.describe("History", () => {
  test("lists saved packages with no console errors", async ({ page }) => {
    const errors = collectErrors(page);
    await page.goto("/history");

    await expect(page.getByRole("heading", { name: "Package library", level: 1 })).toBeVisible();
    await expect(page.getByLabel("Search saved packages")).toBeVisible();

    expect(errors).toEqual([]);
  });

  test("opens a saved package and offers the whole bundle for reuse", async ({ page }) => {
    await mockHistoryRuns(page);
    await page.goto("/history");
    await expect(page.getByRole("heading", { name: "Package library", level: 1 })).toBeVisible();
    expect(await savedRowCount(page)).toBe(2);

    await page.getByTestId("history-row").first().getByRole("button", { name: "View package" }).click();
    const detail = page.getByTestId("history-detail");
    await expect(detail).toBeVisible();
    await expect(detail.getByRole("button", { name: "Copy upload package" })).toBeVisible();
    await page.screenshot({ path: "screenshots/history-detail.png" });
  });

  test("asks for confirmation before deleting and does not delete on cancel", async ({ page }) => {
    await mockHistoryRuns(page);
    let deleteCalls = 0;
    // Counted and answered here, so even a regression that confirmed would never delete anything.
    await page.route("**/api/history/runs**", (route) => {
      if (route.request().method() !== "DELETE") return route.fallback();
      deleteCalls += 1;
      return route.fulfill({ json: { status: "deleted", run_id: 0, cloud_sync: { state: "disabled" } } });
    });

    await page.goto("/history");
    expect(await savedRowCount(page)).toBe(2);

    await page.getByTestId("history-row").first().getByRole("button", { name: /^Delete/ }).click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText("marked deleted");
    // Focus starts on Cancel, so Enter straight away never confirms.
    await expect(dialog.getByRole("button", { name: "Cancel" })).toBeFocused();

    await dialog.getByRole("button", { name: "Cancel" }).click();
    await expect(dialog).toBeHidden();
    expect(deleteCalls).toBe(0);
  });

  test("filters the list from the search box", async ({ page }) => {
    await mockHistoryRuns(page);
    await page.goto("/history");
    expect(await savedRowCount(page)).toBe(2);

    await page.getByLabel("Search saved packages").fill("zzzz-no-match-zzzz");

    await expect(page.getByText("No saved packages match your search.")).toBeVisible();
  });

  test("shows an unmeasured opportunity as unavailable, never as 0", async ({ page }) => {
    await mockHistoryRuns(page);
    await page.goto("/history");

    const row = page.getByTestId("history-row").filter({ hasText: "Top AI Tools" });
    await expect(row.getByRole("group", { name: "Package scores" })).toContainText("Unavailable");
    await expect(row.getByRole("group", { name: "Package scores" })).not.toContainText("0/100");
  });

  test("opens an AI Short on its Flow prompts from View package", async ({ page }) => {
    const errors = collectErrors(page);
    await page.setViewportSize(VIEWPORTS.desktop);
    await mockShortsHistory(page);
    await page.goto("/history");
    expect(await savedRowCount(page)).toBe(3);

    const row = page.getByTestId("history-row").filter({ hasText: SHORT_RUN.title });
    await row.getByRole("button", { name: "View package" }).click();
    const detail = page.getByTestId("history-detail");
    await expect(detail.getByTestId("shot-prompt")).toHaveCount(2);
    await expect(detail.getByRole("button", { name: "Copy prompt for Part 1" })).toBeVisible();
    await expect(detail.getByRole("link", { name: "Open in AI Shorts" })).toHaveAttribute(
      "href",
      `/ai-shorts?plan=${AI_SHORTS_PLAN.id}`,
    );
    // Test & Compare is for long videos only.
    await expect(detail.getByTestId("studio-test-panel")).toHaveCount(0);
    // 64rem on a desktop (the root is 80% there), so a prompt reads as a paragraph.
    const rem = await page.evaluate(() => parseFloat(getComputedStyle(document.documentElement).fontSize));
    expect((await detail.boundingBox())!.width).toBeGreaterThanOrEqual(64 * rem - 1);
    await page.screenshot({ path: "screenshots/history-ai-short-desktop.png" });

    expect(errors).toEqual([]);
  });

  test("fits an AI Short's detail on a phone without sideways scrolling", async ({ page }) => {
    await page.setViewportSize(VIEWPORTS.mobile);
    await mockShortsHistory(page);
    await page.goto(`/history?run=${SHORT_RUN.id}`);

    const detail = page.getByTestId("history-detail");
    await expect(detail.getByTestId("shot-prompt")).toHaveCount(2);
    expect((await detail.boundingBox())!.width).toBeLessThanOrEqual(VIEWPORTS.mobile.width);
    // The sheet is fixed, so the page's own overflow check can't see inside it.
    for (const scroller of [detail, detail.getByTestId("history-detail-body")]) {
      expect(await scroller.evaluate((node) => node.scrollWidth - node.clientWidth)).toBeLessThanOrEqual(1);
    }
    await expectNoHorizontalOverflow(page);
    await page.screenshot({ path: "screenshots/history-ai-short-mobile.png" });
  });

  for (const [name, viewport] of Object.entries(VIEWPORTS)) {
    test(`lays out without horizontal overflow at ${name}`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await page.goto("/history");
      await expect(page.getByRole("heading", { name: "Package library", level: 1 })).toBeVisible();
      await savedRowCount(page);

      await expectNoHorizontalOverflow(page);
      await page.screenshot({ path: `screenshots/history-${name}.png` });
    });
  }
});
