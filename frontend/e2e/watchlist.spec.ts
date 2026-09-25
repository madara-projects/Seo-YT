import { expect, test, type Page } from "@playwright/test";
import { VIEWPORTS, collectErrors, expectNoHorizontalOverflow, stubThumbnails } from "./helpers";

/**
 * The watchlist against the running backend. Every watchlist call is
 * intercepted: adding and refreshing look items up on YouTube, which spends
 * quota. Requires `docker compose up -d`.
 */

const CHANNEL = {
  id: 3,
  channel_id: "UCe2efixture0000000001",
  title: "E2E Fixture Channel",
  subscriber_count: 48200,
  video_count: 312,
  notes: "",
  state: "active",
  last_researched_at: "2026-09-24T09:00:00+00:00",
  created_at: "2026-09-20T09:00:00+00:00",
  snapshots: [{ id: 11, captured_at: "2026-09-24T09:00:00+00:00", subscriber_count: 48200, video_count: 312, view_count: 9120000 }],
};

function video(id: number, videoId: string, title: string, views: number | null) {
  const snapshot =
    views === null ? null : { id: id * 10, captured_at: "2026-09-24T09:00:00+00:00", view_count: views, like_count: 900, comment_count: 12 };
  return {
    id,
    video_id: videoId,
    watchlist_channel_id: 3,
    channel_id: CHANNEL.channel_id,
    channel_title: CHANNEL.title,
    title,
    published_at: "2026-09-19T14:03:11Z",
    duration_seconds: 21,
    language: "ta",
    format: "youtube_shorts",
    notes: "",
    state: "active",
    last_researched_at: snapshot ? snapshot.captured_at : null,
    created_at: "2026-09-24T09:00:00+00:00",
    snapshots: snapshot ? [snapshot] : [],
    latest_snapshot: snapshot,
    outlier: null as Record<string, unknown> | null,
  };
}

async function mockWatchlist(page: Page, calls: { added: unknown[]; analyzed: number; searches: string[] }) {
  let videos = [video(21, "e2ewatch001", "A very long public video title that has to wrap neatly inside the list on a phone", 184233)];
  await page.route("**/api/watchlist/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (request.method() === "POST" && path === "/api/watchlist/videos") {
      const body = request.postDataJSON();
      calls.added.push(body);
      const created = video(22, body.video_id, "Letters I never sent", null);
      videos = [created, ...videos];
      return route.fulfill({ status: 201, json: { status: "created", video: created } });
    }
    const outlier = path.match(/^\/api\/watchlist\/videos\/(\d+)\/analyze-outlier$/);
    if (outlier) {
      calls.analyzed += 1;
      const found = videos.find((item) => item.id === Number(outlier[1]))!;
      found.outlier = {
        status: "insufficient_evidence",
        sample_size: 0,
        explanation: "Only 0 comparable recent peer video(s) have public view observations; at least 5 with a positive median are required.",
        analyzed_at: "2026-09-24T09:05:00+00:00",
      };
      return route.fulfill({ json: { status: "analyzed", analysis: found.outlier, video: found } });
    }
    const item = path.match(/^\/api\/watchlist\/(videos|channels)\/(\d+)$/);
    if (item) {
      if (item[1] === "channels") return route.fulfill({ json: { channel: CHANNEL } });
      return route.fulfill({ json: { video: videos.find((entry) => entry.id === Number(item[2])) } });
    }
    if (path === "/api/watchlist/channels") return route.fulfill({ json: { channels: [CHANNEL], total: 1 } });
    const q = url.searchParams.get("q") ?? "";
    if (q) calls.searches.push(q);
    const rows = videos.filter((entry) => !q || entry.title.toLowerCase().includes(q.toLowerCase()));
    return route.fulfill({ json: { videos: rows, total: rows.length } });
  });
  await stubThumbnails(page);
}

test.describe("Watchlist", () => {
  test("adds a video from a link and runs the free outlier check", async ({ page }) => {
    const errors = collectErrors(page);
    const calls = { added: [] as unknown[], analyzed: 0, searches: [] as string[] };
    await mockWatchlist(page, calls);

    await page.goto("/next/watchlist");
    await expect(page.getByRole("heading", { name: "Watchlist", level: 1 })).toBeVisible();

    await page.getByLabel("Video ID or link").fill("https://www.youtube.com/shorts/e2ewatch002");
    await page.getByRole("button", { name: "Add video" }).click();

    await expect(page).toHaveURL(/\/next\/watchlist\?video=22$/);
    expect(calls.added).toEqual([{ video_id: "e2ewatch002", notes: "" }]);
    const detail = page.getByTestId("watch-detail");
    await expect(detail.getByRole("heading", { name: "Letters I never sent" })).toBeVisible();
    await expect(detail).toContainText("No snapshot yet");

    await detail.getByRole("button", { name: "Run outlier check" }).click();
    await expect(detail.getByText("Not enough peers")).toBeVisible();
    expect(calls.analyzed).toBe(1);

    expect(errors).toEqual([]);
  });

  test("searches videos after a pause and switches to channels", async ({ page }) => {
    const calls = { added: [] as unknown[], analyzed: 0, searches: [] as string[] };
    await mockWatchlist(page, calls);
    await page.goto("/next/watchlist");

    await page.getByLabel("Search watched videos").pressSequentially("wrap", { delay: 30 });
    await expect(page.getByTestId("watch-video")).toHaveCount(1);
    await expect.poll(() => calls.searches).toEqual(["wrap"]);

    await page.getByRole("tab", { name: /Channels/ }).click();
    await page.getByTestId("watch-channel").click();
    await expect(page).toHaveURL(/\/next\/watchlist\?channel=3$/);
    await expect(page.getByTestId("watch-detail")).toContainText("Watched uploads (1)");
  });

  for (const [name, viewport] of Object.entries(VIEWPORTS)) {
    test(`lays out without horizontal overflow at ${name}`, async ({ page }) => {
      await mockWatchlist(page, { added: [], analyzed: 0, searches: [] });
      await page.setViewportSize(viewport);
      await page.goto("/next/watchlist?video=21");
      await expect(page.getByTestId("watch-detail")).toBeVisible();

      await expectNoHorizontalOverflow(page);
      await page.screenshot({ path: `screenshots/watchlist-${name}.png`, fullPage: true });
    });
  }
});
