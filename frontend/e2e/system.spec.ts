import { expect, test, type Page } from "@playwright/test";
import {
  VIEWPORTS,
  blockWrites,
  collectErrors,
  expectNoHorizontalOverflow,
  minutesAgo,
  mockHistoryRuns,
  stubThumbnails,
} from "./helpers";

/**
 * Settings, Channel and the command palette against the running backend.
 * Channel data is mocked where a connected channel is needed, because this
 * environment has none; every mutating call is answered here or aborted, so
 * no test spends YouTube quota or changes saved data. Requires
 * `docker compose up -d`.
 */

/**
 * A sync as `/youtube/channel/status` returns it. Built when each test runs,
 * so "a minute ago" is a minute before that test, not before the file loaded.
 */
function sync() {
  return {
    channel: { id: "UCe2efixture0000000001", title: "E2E Fixture Channel", subscribers: 18432, video_count: 212, real_total_views: 4829331 },
    period: { start: "2026-08-27", end: "2026-09-23" },
    current_28_days: { views: 184233, estimatedMinutesWatched: 51230, averageViewDuration: 17, subscribersGained: 912, likes: 9120, comments: 812 },
    previous_28_days: { views: 151020, estimatedMinutesWatched: 48110, averageViewDuration: 19, subscribersGained: 1034, likes: 8800, comments: 640 },
    recent_videos: {
      rows: Array.from({ length: 10 }, (_, index) => ({
        video_id: `e2evideo${String(index).padStart(3, "0")}`,
        title: `Fixture upload ${index + 1}`,
        published_at: minutesAgo(60 * 24 * (index * 3 + 1)),
        views: [1200, 48210, 9000, 15550, 6620, 21980, 4410, 9760, 17340, 30112][index],
        likes: 100 + index * 10,
        comments: 10 + index,
      })),
    },
    video_learning: { sample_size: 0, confidence_label: "Collecting evidence", learning_allowed: false },
  };
}

function connected() {
  const data = sync();
  return {
    configured: true,
    connected: true,
    channel: { id: data.channel.id, title: data.channel.title, connected_at: minutesAgo(60 * 24 * 20) },
    latest_sync: { synced_at: minutesAgo(1), data },
    setup_message: null,
  };
}

const NOT_CONNECTED = { configured: true, connected: false, channel: null, latest_sync: null, setup_message: null };

async function mockChannelStatus(page: Page, status: object) {
  await page.route("**/youtube/channel/status", (route) => route.fulfill({ json: status }));
  await page.route("**/youtube/channel/refresh", (route) => route.fulfill({ json: sync() }));
  await stubThumbnails(page);
}

test.beforeEach(async ({ page }) => {
  await blockWrites(page);
});

test.describe("Settings", () => {
  test("renders every section with no console errors and no live check", async ({ page }) => {
    const errors = collectErrors(page);
    let diagnostics = 0;
    page.on("request", (request) => {
      if (new URL(request.url()).pathname === "/diagnostics") diagnostics += 1;
    });

    await page.goto("/settings");
    await expect(page.getByRole("heading", { name: "Settings", level: 1 })).toBeVisible();
    for (const name of ["YouTube channel", "Cloud sync", "AI & data providers", "Local database"]) {
      await expect(page.getByRole("heading", { name, level: 2 })).toBeVisible();
    }
    await expect(page.getByText("Schema · size")).toBeVisible();

    expect(diagnostics).toBe(0);
    expect(errors).toEqual([]);
  });

  test("points the connect button back at Settings", async ({ page }) => {
    await mockChannelStatus(page, NOT_CONNECTED);
    await page.goto("/settings");

    await expect(page.getByRole("link", { name: /Connect YouTube channel/ })).toHaveAttribute(
      "href",
      "/youtube/channel/connect?return_to=%2Fsettings",
    );
  });

  test("shows the OAuth result once and cleans the URL", async ({ page }) => {
    await mockChannelStatus(page, connected());
    await page.goto("/settings?youtube=connected");

    await expect(
      page.getByRole("status").filter({ hasText: "YouTube channel connected with read-only access." }),
    ).toBeVisible();
    await expect(page).toHaveURL(/\/settings$/);
  });

  test("does not announce a connection the server doesn't have", async ({ page }) => {
    // Anyone can put ?youtube=connected in a link; the page checks with the server.
    await mockChannelStatus(page, NOT_CONNECTED);
    await page.goto("/settings?youtube=connected");

    await expect(page.getByRole("alert").filter({ hasText: /no connected channel/ })).toBeVisible();
    await expect(page.getByText("YouTube channel connected with read-only access.")).toHaveCount(0);
  });

  for (const [name, viewport] of Object.entries(VIEWPORTS)) {
    test(`lays out without horizontal overflow at ${name}`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await page.goto("/settings");
      await expect(page.getByRole("heading", { name: "Settings", level: 1 })).toBeVisible();
      await expect(page.getByText("Schema · size")).toBeVisible();

      await expectNoHorizontalOverflow(page);
      await page.screenshot({ path: `screenshots/settings-${name}.png`, fullPage: true });
    });
  }
});

test.describe("Channel", () => {
  test("invites a connection when no channel is connected", async ({ page }) => {
    const errors = collectErrors(page);
    await mockChannelStatus(page, NOT_CONNECTED);
    await page.goto("/channel");

    await expect(page.getByRole("heading", { name: "Channel", level: 1 })).toBeVisible();
    await expect(page.getByRole("link", { name: /Connect YouTube channel/ })).toHaveAttribute(
      "href",
      "/youtube/channel/connect?return_to=%2Fchannel",
    );
    expect(errors).toEqual([]);
  });

  test("renders a connected channel's analytics with no console errors", async ({ page }) => {
    const errors = collectErrors(page);
    let refreshes = 0;
    page.on("request", (request) => {
      if (new URL(request.url()).pathname === "/youtube/channel/refresh") refreshes += 1;
    });
    await mockChannelStatus(page, connected());
    await page.goto("/channel");

    await expect(page.getByRole("heading", { name: "E2E Fixture Channel" })).toBeVisible();
    const views = page.locator('[data-stat="Views (28 days)"]');
    await expect(views).toContainText("+22.0%");
    await expect(page.locator('[data-stat="Avg view duration (28 days)"]')).toContainText("0:17");

    const firstRow = page.getByRole("table").getByRole("row").nth(1);
    await expect(firstRow).toContainText("Fixture upload 1");
    await page.getByRole("tab", { name: "Most viewed" }).click();
    await expect(firstRow).toContainText("Fixture upload 2");
    // The sort is kept in the URL.
    await expect(page).toHaveURL(/sort=views/);

    // The sync is a minute old, so nothing is refreshed behind the user's back.
    expect(refreshes).toBe(0);
    expect(errors).toEqual([]);
  });

  for (const [name, viewport] of Object.entries(VIEWPORTS)) {
    test(`lays out without horizontal overflow at ${name}`, async ({ page }) => {
      await mockChannelStatus(page, connected());
      await page.setViewportSize(viewport);
      await page.goto("/channel");
      await expect(page.getByRole("heading", { name: "E2E Fixture Channel" })).toBeVisible();

      await expectNoHorizontalOverflow(page);
      await page.screenshot({ path: `screenshots/channel-${name}.png`, fullPage: true });
    });
  }
});

test.describe("Navigation", () => {
  test("jumps to a page from the command palette", async ({ page }) => {
    await mockChannelStatus(page, NOT_CONNECTED);
    await page.goto("/creator");
    await expect(page.getByRole("heading", { name: "Creator", level: 1 })).toBeVisible();

    await page.keyboard.press("Control+k");
    const search = page.getByRole("combobox", { name: "Search pages and actions" });
    await expect(search).toBeFocused();
    await search.fill("channel");
    await page.keyboard.press("Enter");

    await expect(page).toHaveURL(/\/channel$/);
    await expect(page.getByRole("heading", { name: "Channel", level: 1 })).toBeVisible();
    await expect(page).toHaveTitle(/^Channel · Win-Engine$/);
    await page.screenshot({ path: "screenshots/palette-navigated.png" });
  });

  test("opens a saved package from a shareable link", async ({ page }) => {
    await mockHistoryRuns(page);
    await page.goto("/history");
    const rows = page.getByTestId("history-row");
    await expect(page.getByTestId("history-result-summary")).not.toHaveText(/Loading saved packages/);
    await expect(rows).toHaveCount(2);

    await rows.first().getByRole("button", { name: "View package" }).click();
    await expect(page).toHaveURL(/\/history\?run=\d+$/);
    const link = page.url();

    await page.goto(link);
    await expect(page.getByTestId("history-detail")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("history-detail")).toBeHidden();
    await expect(page).toHaveURL(/\/history$/);
  });
});
