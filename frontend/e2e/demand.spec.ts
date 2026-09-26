import { expect, test, type Page } from "@playwright/test";
import { VIEWPORTS, blockWrites, collectErrors, expectNoHorizontalOverflow, stubThumbnails } from "./helpers";

/**
 * The Demand explorer against the running backend. Research and generation
 * are intercepted: they would spend YouTube quota and Gemini calls and write
 * to History. Requires `docker compose up -d`.
 */

test.beforeEach(async ({ page }) => {
  await blockWrites(page);
});

const SNAPSHOT = {
  id: 7,
  idea_id: null,
  topic: "painful love quotes",
  language: "english",
  format: "youtube_shorts",
  region: "india",
  audience_context: "",
  classification: "emerging_signal",
  captured_at: "2026-09-24T13:25:13+00:00",
  evidence: {
    classification: "emerging_signal",
    reasons: [
      "5 relevant public results were observed in the sampled API result set.",
      "Coverage was observed across 5 independent channels.",
    ],
    signals: [
      { name: "sampled_relevant_results", observed: 5, source: "public_observation", limitation: "Sampled API results, not monthly search volume." },
      { name: "recent_publications_90d", observed: 0, source: "public_observation", limitation: "Publication activity does not prove audience demand." },
      { name: "independent_channels", observed: 5, source: "public_observation", limitation: "Channel coverage is observational." },
      { name: "median_captured_views", observed: 20419, source: "public_observation", limitation: "Views at capture time are not search volume or causal evidence." },
      { name: "watchlist_possible_outliers", observed: 0, source: "heuristic", limitation: "Outlier association does not establish causation." },
    ],
    public_results: [
      { video_id: "e2edemand01", title: "A very long public video title that has to wrap neatly inside the evidence list on a phone", channel_title: "Fixture Channel", published_at: "2025-11-02T10:36:52Z", view_count: "180809850" },
      { video_id: "e2edemand02", title: "Second sampled result", channel_title: "Another Channel", published_at: "2024-07-17T22:24:38Z", view_count: "20419" },
    ],
    watchlist_evidence: [],
    personal_evidence: { status: "insufficient_evidence", learning_allowed: false, sample_size: 0, confidence_label: "Collecting evidence", source: "unavailable" },
    limitations: ["No official monthly search-volume data is available."],
  },
};

async function mockDemand(page: Page, calls: { research: unknown[]; generate: number }) {
  let snapshots = [SNAPSHOT];
  await page.route("**/api/demand/research**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === "POST" && path === "/api/demand/research") {
      const body = request.postDataJSON();
      calls.research.push(body);
      const created = {
        ...SNAPSHOT,
        id: 8,
        topic: body.topic,
        language: body.language,
        format: body.format,
        region: body.region,
      };
      snapshots = [created, ...snapshots];
      return route.fulfill({ status: 201, json: { status: "researched", research: created } });
    }
    if (request.method() === "POST" && path.endsWith("/generate")) {
      calls.generate += 1;
      return route.fulfill({
        json: { status: "package_generated", analysis: { history_run_id: 42 }, demand_research_id: 7 },
      });
    }
    const detail = path.match(/\/api\/demand\/research\/(\d+)$/);
    if (detail) {
      const found = snapshots.find((item) => item.id === Number(detail[1]));
      return route.fulfill(found ? { json: { research: found } } : { status: 404, json: { detail: "Not found" } });
    }
    return route.fulfill({ json: { research: snapshots, total: snapshots.length } });
  });
  await stubThumbnails(page);
}

test.describe("Demand", () => {
  test("researches a topic and inspects the evidence with no console errors", async ({ page }) => {
    const errors = collectErrors(page);
    const calls = { research: [] as unknown[], generate: 0 };
    await mockDemand(page, calls);

    await page.goto("/next/demand");
    await expect(page.getByRole("heading", { name: "Demand", level: 1 })).toBeVisible();
    await expect(page.getByTestId("demand-snapshot")).toHaveCount(1);

    await page.getByLabel("Topic or phrase").fill("heartbreak quotes");
    await page.getByRole("combobox", { name: "Language" }).click();
    await page.getByRole("option", { name: "Tamil", exact: true }).click();
    await page.getByRole("combobox", { name: "Region" }).click();
    await page.getByRole("option", { name: "Tamil Nadu" }).click();
    await page.getByRole("button", { name: "Research demand" }).click();

    await expect(page).toHaveURL(/\/next\/demand\?snapshot=8$/);
    const detail = page.getByTestId("demand-detail");
    await expect(detail.getByRole("heading", { name: "heartbreak quotes" })).toBeVisible();
    await expect(detail).toContainText("Emerging signal");
    await expect(detail).toContainText("Tamil Nadu");
    await expect(detail).toContainText("Median views at capture");
    expect(calls.research).toEqual([
      { topic: "heartbreak quotes", language: "tamil", format: "", region: "tamil nadu", audience_context: "" },
    ]);

    await detail.getByRole("button", { name: "Generate package" }).click();
    await expect(detail.getByRole("link", { name: /Open in History/ })).toHaveAttribute("href", "/next/history?run=42");
    expect(calls.generate).toBe(1);

    expect(errors).toEqual([]);
  });

  test("keeps the sidebar entry current, without the legacy tag", async ({ page }) => {
    await page.setViewportSize(VIEWPORTS.desktop);
    await page.goto("/next/demand");
    const link = page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Demand" });
    await expect(link).toHaveAttribute("aria-current", "page");
    await expect(link).not.toContainText("Legacy");
  });

  for (const [name, viewport] of Object.entries(VIEWPORTS)) {
    test(`lays out without horizontal overflow at ${name}`, async ({ page }) => {
      await mockDemand(page, { research: [], generate: 0 });
      await page.setViewportSize(viewport);
      await page.goto("/next/demand?snapshot=7");
      await expect(page.getByTestId("demand-detail")).toBeVisible();

      await expectNoHorizontalOverflow(page);
      await page.screenshot({ path: `screenshots/demand-${name}.png`, fullPage: true });
    });
  }
});
