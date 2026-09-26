import { expect, type ConsoleMessage, type Page } from "@playwright/test";

/** Shared by every spec. */

export const VIEWPORTS = {
  desktop: { width: 1440, height: 900 },
  tablet: { width: 834, height: 1112 },
  mobile: { width: 390, height: 844 },
} as const;

// A 1x1 transparent PNG stands in for YouTube thumbnails.
const PIXEL = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
  "base64",
);

export async function stubThumbnails(page: Page) {
  await page.route("https://i.ytimg.com/**", (route) =>
    route.fulfill({ status: 200, contentType: "image/png", body: PIXEL }),
  );
}

/**
 * Aborts every request that could change saved data or spend quota (anything
 * but a read) unless a test's own route answers it. Register it before the
 * test's routes: Playwright runs the most recently registered match first,
 * and a route that only watches requests passes them on with `fallback()`.
 */
export async function blockWrites(page: Page) {
  await page.route("**/*", (route) => {
    const method = route.request().method();
    return method === "GET" || method === "HEAD" ? route.fallback() : route.abort("blockedbyclient");
  });
}

export function collectErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (message: ConsoleMessage) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(String(error)));
  return errors;
}

export async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
}

/** An ISO timestamp this many minutes before now, computed when called. */
export const minutesAgo = (minutes: number) => new Date(Date.now() - minutes * 60_000).toISOString();

/** The channel as the app sees it; mocked because this environment has none connected. */
export async function mockChannel(page: Page, connected: boolean, id = "UCe2efixture0000000001") {
  await page.route("**/youtube/channel/status", (route) =>
    route.fulfill({
      json: {
        configured: true,
        connected,
        channel: connected ? { id, title: "E2E Fixture Channel" } : null,
        latest_sync: null,
      },
    }),
  );
}

/** Saved packages for the History specs, so they never depend on the live library. */
export const HISTORY_RUNS = [
  {
    id: 901,
    created_at: "2026-09-22T17:53:19Z",
    title: "Three Morning Habits",
    query: "waking at the same time daily",
    content_angle: "Story",
    opportunity_score: 38.6,
    title_score: 7.5,
    selected_package_id: "package-a",
    linked_youtube_video_id: null,
  },
  {
    id: 902,
    created_at: "2026-09-21T10:00:00Z",
    title: "Top AI Tools",
    query: "productivity tools review",
    content_angle: "Review",
    opportunity_score: null,
    opportunity_label: "UNMEASURED",
    title_score: 8.1,
    selected_package_id: null,
    linked_youtube_video_id: "abc12345678",
  },
];

/** Serves `HISTORY_RUNS` for the list and each package's detail. Reads only. */
export async function mockHistoryRuns(page: Page) {
  await page.route("**/api/history/runs**", (route) => {
    const request = route.request();
    if (request.method() !== "GET") return route.fallback();
    const detail = new URL(request.url()).pathname.match(/\/api\/history\/runs\/(\d+)$/);
    if (detail) {
      const run = HISTORY_RUNS.find((item) => item.id === Number(detail[1]));
      return route.fulfill(
        run
          ? {
              json: {
                ...run,
                package: {
                  title: run.title,
                  description: "A saved description.",
                  tags: ["fixture tag"],
                  hashtags: ["#fixture"],
                  chapters: [],
                },
                selected_package: null,
                linked_video_report: { linked: false },
              },
            }
          : { status: 404, json: { error: { code: "http_error", message: "Saved package not found." } } },
      );
    }
    return route.fulfill({ json: { runs: HISTORY_RUNS, total: HISTORY_RUNS.length, limit: 100, offset: 0 } });
  });
}

/** Picks an option from one of the app's labelled selects. */
export async function choose(page: Page, label: string, option: string) {
  await page.getByRole("combobox", { name: label }).click();
  await page.getByRole("option", { name: option, exact: true }).click();
}
