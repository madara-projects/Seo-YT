import { expect, test, type Page } from "@playwright/test";
import {
  VIEWPORTS,
  blockWrites,
  choose,
  collectErrors,
  expectNoHorizontalOverflow,
  mockChannel,
  stubThumbnails,
} from "./helpers";
import { AUDIT_FIXTURE } from "../src/test/fixtures/audit";

/**
 * Published-video audits against the running backend. The list and audits are
 * mocked for stable data, and refreshing is intercepted: it reads the video
 * from a connected channel and saves a new audit version. Requires
 * `docker compose up -d`.
 */

const AUDITED = {
  id: 5,
  analysis_run_id: 42,
  youtube_video_id: "e2eaudit001",
  published_at: "2026-09-07T11:50:35Z",
  youtube_metadata: { title: "Silence says everything #shorts" },
  latest_performance: { views: 3105, snapshot_window: "current", captured_at: "2026-09-24T09:00:00+00:00" },
  ownership_verified: true,
  verified_channel_id: "UCe2efixture0000000001",
  audit_id: 9,
  audit_state: "mature_observation",
  evidence_state: "observed",
};
const NOT_RUN = {
  ...AUDITED,
  id: 6,
  analysis_run_id: 43,
  youtube_video_id: "e2eaudit002",
  published_at: "2026-09-02T11:00:00Z",
  youtube_metadata: { title: "A very long published title that has to wrap neatly in the list on a phone #shorts" },
  latest_performance: null,
  ownership_verified: false,
  audit_id: null,
  audit_state: "not_run",
  evidence_state: "unavailable",
};

async function mockAudits(page: Page, calls: { refreshed: number }) {
  let audited = false;
  await page.route("**/api/audits**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const refresh = url.pathname.match(/^\/api\/audits\/(\d+)\/refresh$/);
    if (refresh && request.method() === "POST") {
      calls.refreshed += 1;
      audited = true;
      return route.fulfill({
        status: 201,
        json: {
          status: "audited",
          audit: { ...AUDIT_FIXTURE, id: 10 },
          versions: [{ id: 10, captured_at: AUDIT_FIXTURE.captured_at, summary_state: "mature_observation" }],
          video_refresh: { captured: [{ snapshot_window: "7d" }] },
        },
      });
    }
    const detail = url.pathname.match(/^\/api\/audits\/(\d+)$/);
    if (detail) {
      const id = Number(detail[1]);
      const hasAudit = id === 5 || (id === 6 && audited);
      return route.fulfill({
        json: hasAudit
          ? { audit: AUDIT_FIXTURE, versions: [{ id: 9, captured_at: AUDIT_FIXTURE.captured_at, summary_state: "mature_observation" }], status: "available" }
          : { audit: null, versions: [], status: "not_run" },
      });
    }
    const state = url.searchParams.get("audit_state");
    const rows = [AUDITED, NOT_RUN].filter((item) => !state || item.audit_state === state);
    return route.fulfill({ json: { candidates: rows, total: rows.length } });
  });
  await stubThumbnails(page);
}

/** Nothing a test does may change saved data: writes are answered by its own routes or aborted. */
test.beforeEach(async ({ page }) => {
  await blockWrites(page);
});

test.describe("Audits", () => {
  test("runs a first audit and shows the field-by-field check", async ({ page }) => {
    const errors = collectErrors(page);
    const calls = { refreshed: 0 };
    await mockChannel(page, true);
    await mockAudits(page, calls);

    await page.goto("/next/audits?link=6");
    const detail = page.getByTestId("audit-detail");
    await expect(detail.getByText("What an audit does")).toBeVisible();

    await detail.getByRole("button", { name: "Run audit" }).click();
    await expect(detail.getByText("Differences found")).toBeVisible();
    await expect(detail.getByTestId("audit-field")).toHaveCount(4);
    expect(calls.refreshed).toBe(1);

    expect(errors).toEqual([]);
  });

  test("keeps the open video's facts when a filter hides it", async ({ page }) => {
    await mockChannel(page, true);
    await mockAudits(page, { refreshed: 0 });
    await page.goto("/next/audits?link=6");
    const detail = page.getByTestId("audit-detail");
    await expect(detail.getByRole("link", { name: "Run #43" })).toBeVisible();

    await choose(page, "Filter by audit state", "Mature observation");
    await expect(page.getByTestId("audit-candidate")).toHaveCount(1);
    await expect(detail.getByRole("link", { name: "Run #43" })).toBeVisible();
    await expect(detail).not.toContainText("Unknown");
  });

  test("points to connecting the channel instead of offering an audit that can't run", async ({ page }) => {
    await mockChannel(page, false);
    await mockAudits(page, { refreshed: 0 });
    await page.goto("/next/audits?link=6");

    const detail = page.getByTestId("audit-detail");
    await expect(detail.getByRole("link", { name: /Connect your channel/ })).toHaveAttribute("href", "/next/channel");
    await expect(detail.getByRole("button", { name: "Run audit" })).toHaveCount(0);
  });

  for (const [name, viewport] of Object.entries(VIEWPORTS)) {
    test(`lays out without horizontal overflow at ${name}`, async ({ page }) => {
      await mockChannel(page, true);
      await mockAudits(page, { refreshed: 0 });
      await page.setViewportSize(viewport);
      await page.goto("/next/audits?link=5");
      await expect(page.getByTestId("audit-detail").getByText("Differences found")).toBeVisible();

      await expectNoHorizontalOverflow(page);
      await page.screenshot({ path: `screenshots/audits-${name}.png`, fullPage: true });
    });
  }
});
