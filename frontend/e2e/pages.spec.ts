import { expect, test, type ConsoleMessage, type Page } from "@playwright/test";

/**
 * Dashboard and History against the running backend with its real data.
 * Requires `docker compose up -d` at the repository root.
 */

const VIEWPORTS = {
  desktop: { width: 1440, height: 900 },
  tablet: { width: 834, height: 1112 },
  mobile: { width: 390, height: 844 },
} as const;

function collectErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (message: ConsoleMessage) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(String(error)));
  return errors;
}

test.describe("Dashboard", () => {
  test("renders against live data with no console errors", async ({ page }) => {
    const errors = collectErrors(page);
    await page.goto("/next/dashboard");

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
          owned_performance: { channel: null, latest_sync: null, estimated_watch_minutes: 0, linked_videos_count: 0 },
        },
      }),
    );
    await page.goto("/next/dashboard");
    await expect(page.getByRole("heading", { name: "Dashboard", level: 1 })).toBeVisible();
    await expect(page.getByText("Connect and refresh your channel in Settings.")).toBeVisible();

    for (const label of ["Views (28 days)", "Estimated watch time"]) {
      const card = page.locator(`[data-stat="${label}"]`);
      await expect(card).toContainText("Unavailable");
      await expect(card).not.toContainText(/^0$/);
    }
  });

  test("labels linked-video watch time as its own measure", async ({ page }) => {
    // Without a channel sync the backend falls back to linked videos' latest
    // snapshots; that is not a 28-day channel total and must not look like one.
    await page.route("**/api/history", (route) =>
      route.fulfill({
        json: {
          learning: {},
          scorecard: { total_runs: 41 },
          owned_performance: { channel: null, latest_sync: null, estimated_watch_minutes: 132, linked_videos_count: 19 },
        },
      }),
    );
    await page.goto("/next/dashboard");

    const card = page.locator('[data-stat="Estimated watch time"]');
    await expect(card).toContainText("2.2 hrs");
    await expect(card).toContainText("Linked videos");
    await expect(card).toContainText("Across your 19 linked videos");
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

    await page.goto("/next/dashboard");
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

    await page.goto("/next/dashboard");
    await page.getByRole("button", { name: "Quote short" }).click();
    await page.getByRole("button", { name: "Open in Creator" }).click();

    await expect(page.getByRole("heading", { name: "Creator", level: 1 })).toBeVisible();
    await expect(page.getByLabel("Script")).toHaveValue(/biggest betrayal/);
    expect(analyzeCalls).toBe(0);
  });

  for (const [name, viewport] of Object.entries(VIEWPORTS)) {
    test(`lays out without horizontal overflow at ${name}`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await page.goto("/next/dashboard");
      await expect(page.getByRole("heading", { name: "Dashboard", level: 1 })).toBeVisible();

      // Wait for the loaded state rather than the skeletons, so the check (and
      // the screenshot) reflects the layout a user actually sees.
      await expect(page.locator('[data-stat="Avg opportunity score"]')).toBeVisible();

      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow).toBeLessThanOrEqual(1);
      await page.screenshot({ path: `screenshots/dashboard-${name}.png` });
    });
  }
});

/**
 * Waits for the list to settle before counting: the rows arrive asynchronously,
 * so counting immediately after navigation always reports zero and would skip
 * every test that needs data.
 */
async function savedRowCount(page: Page): Promise<number> {
  const rows = page.getByTestId("history-row");
  await expect(page.getByTestId("history-result-summary")).not.toHaveText(
    /Loading saved packages/,
  );
  return rows.count();
}

test.describe("History", () => {
  test("lists saved packages with no console errors", async ({ page }) => {
    const errors = collectErrors(page);
    await page.goto("/next/history");

    await expect(page.getByRole("heading", { name: "Package library", level: 1 })).toBeVisible();
    await expect(page.getByLabel("Search saved packages")).toBeVisible();

    expect(errors).toEqual([]);
  });

  test("opens a saved package and offers the whole bundle for reuse", async ({ page }) => {
    await page.goto("/next/history");
    await expect(page.getByRole("heading", { name: "Package library", level: 1 })).toBeVisible();

    const rows = page.getByTestId("history-row");
    test.skip((await savedRowCount(page)) === 0, "no saved packages in this environment");

    await rows.first().getByRole("button", { name: "View package" }).click();
    const detail = page.getByTestId("history-detail");
    await expect(detail).toBeVisible();
    await expect(detail.getByRole("button", { name: "Copy upload package" })).toBeVisible();
    await page.screenshot({ path: "screenshots/history-detail.png" });
  });

  test("asks for confirmation before deleting and does not delete on cancel", async ({ page }) => {
    let deleteCalls = 0;
    await page.route("**/api/history/runs**", (route) => {
      if (route.request().method() === "DELETE") deleteCalls += 1;
      return route.continue();
    });

    await page.goto("/next/history");
    const rows = page.getByTestId("history-row");
    test.skip((await savedRowCount(page)) === 0, "no saved packages in this environment");

    await rows.first().getByRole("button", { name: /^Delete/ }).click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText("marked deleted");

    await dialog.getByRole("button", { name: "Cancel" }).click();
    await expect(dialog).toBeHidden();
    expect(deleteCalls).toBe(0);
  });

  test("filters the list from the search box", async ({ page }) => {
    await page.goto("/next/history");
    const rows = page.getByTestId("history-row");
    test.skip((await savedRowCount(page)) === 0, "no saved packages in this environment");

    const before = await savedRowCount(page);
    await page.getByLabel("Search saved packages").fill("zzzz-no-match-zzzz");

    await expect(page.getByText("No saved packages match your search.")).toBeVisible();
    expect(before).toBeGreaterThan(0);
  });

  for (const [name, viewport] of Object.entries(VIEWPORTS)) {
    test(`lays out without horizontal overflow at ${name}`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await page.goto("/next/history");
      await expect(page.getByRole("heading", { name: "Package library", level: 1 })).toBeVisible();
      await savedRowCount(page);

      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow).toBeLessThanOrEqual(1);
      await page.screenshot({ path: `screenshots/history-${name}.png` });
    });
  }
});
