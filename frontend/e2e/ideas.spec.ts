import { expect, test, type Page } from "@playwright/test";
import { VIEWPORTS, choose, collectErrors, expectNoHorizontalOverflow, stubThumbnails } from "./helpers";

/**
 * The idea backlog against the running backend. Every idea call is
 * intercepted: research and generation spend YouTube quota and Gemini calls,
 * and saving would write to the real backlog. Requires `docker compose up -d`.
 */

const EVIDENCE = {
  captured_at: "2026-09-24T09:10:00+00:00",
  opportunity_explanation:
    "Observed 2 relevant public YouTube API result(s) across 3 approved research query angle(s); 1 carried a possible-outlier signal. Most recent observed publication: 2026-09-19T14:03:11Z. These are dated public observations, not monthly search volume or predicted demand.",
  signals: { relevant_result_count: 2, research_query_count: 3, possible_outlier_count: 1 },
  personal_evidence: { learning_allowed: false, sample_size: 0, confidence_label: "Collecting evidence", snapshot_window: "24h", message: "Not enough personal evidence." },
  youtube_results: [
    { video_id: "e2eidea0001", title: "A very long public video title that has to wrap neatly inside the evidence list on a phone", channel_title: "Fixture Channel", published_at: "2026-09-19T14:03:11Z", view_count: "184233" },
  ],
};

function idea(id: number, overrides: Record<string, unknown> = {}) {
  return {
    id,
    topic: "Why silence hurts more than words",
    status: "scripted",
    notes: "Open on an empty chat window.",
    format: "youtube_shorts",
    language: "tamil",
    region: "in",
    visual_or_background: "Rain on a window",
    on_screen_text: "Silence says everything",
    target_duration_seconds: 28,
    emotion_or_intent: "Quiet heartbreak",
    search_angle: "silence quotes tamil",
    browse_angle: "",
    audience_angle: "",
    analysis_run_id: null,
    published_video_link_id: null,
    created_at: "2026-09-20T10:00:00+00:00",
    updated_at: "2026-09-24T09:10:00+00:00",
    last_researched_at: EVIDENCE.captured_at,
    research_snapshots: [{ id: 3, captured_at: EVIDENCE.captured_at, evidence: EVIDENCE }],
    latest_research: { id: 3, captured_at: EVIDENCE.captured_at, evidence: EVIDENCE },
    research_is_stale: false,
    latest_demand_research: { id: 12, classification: "active_topic", captured_at: EVIDENCE.captured_at, stale: false },
    ...overrides,
  };
}

async function mockIdeas(page: Page, calls: { created: unknown[]; generated: number }) {
  let ideas = [idea(7)];
  await page.route("**/api/ideas**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === "POST" && path === "/api/ideas") {
      const body = request.postDataJSON();
      calls.created.push(body);
      const created = idea(8, { ...body, research_snapshots: [], latest_research: null, latest_demand_research: null, last_researched_at: null });
      ideas = [created, ...ideas];
      return route.fulfill({ status: 201, json: { status: "created", idea: created } });
    }
    const detail = path.match(/^\/api\/ideas\/(\d+)(\/[a-z-]+)?$/);
    if (detail) {
      const found = ideas.find((item) => item.id === Number(detail[1]));
      if (!found) return route.fulfill({ status: 404, json: { detail: "Idea not found." } });
      if (detail[2] === "/generate") {
        calls.generated += 1;
        Object.assign(found, { status: "package_generated", analysis_run_id: 42 });
        return route.fulfill({ json: { status: "package_generated", idea: found, analysis: { history_run_id: 42 } } });
      }
      return route.fulfill({ json: { idea: found } });
    }
    return route.fulfill({ json: { ideas, total: ideas.length, limit: 20, offset: 0 } });
  });
  await stubThumbnails(page);
}

test.describe("Ideas", () => {
  test("saves an idea with its language and region, then generates a package", async ({ page }) => {
    const errors = collectErrors(page);
    const calls = { created: [] as unknown[], generated: 0 };
    await mockIdeas(page, calls);

    await page.goto("/next/ideas");
    await expect(page.getByRole("heading", { name: "Ideas", level: 1 })).toBeVisible();
    await expect(page.getByTestId("idea-item")).toHaveCount(1);

    await page.getByRole("button", { name: "New idea" }).click();
    const form = page.getByTestId("idea-form");
    await form.getByLabel("Topic").fill("Letters I never sent");
    await choose(page, "Language", "Tamil");
    await choose(page, "Region", "Tamil Nadu");
    await form.getByLabel(/Target duration/).fill("45");
    await form.getByRole("button", { name: "Save idea" }).click();

    await expect(page).toHaveURL(/\/next\/ideas\?idea=8$/);
    await expect(form).toBeHidden();
    expect(calls.created).toEqual([
      expect.objectContaining({
        topic: "Letters I never sent",
        format: "youtube_shorts",
        language: "tamil",
        region: "tamil nadu",
        target_duration_seconds: 45,
        status: "idea",
      }),
    ]);
    const detail = page.getByTestId("idea-detail");
    await expect(detail.getByRole("heading", { name: "Letters I never sent" })).toBeVisible();
    await expect(detail).toContainText("Tamil Nadu");

    await detail.getByRole("button", { name: "Generate package" }).click();
    await expect(detail.getByText("Package saved to History as run #42.")).toBeVisible();
    await expect(detail.getByRole("link", { name: "Open in History" })).toHaveAttribute("href", "/next/history?run=42");
    expect(calls.generated).toBe(1);

    expect(errors).toEqual([]);
  });

  test("shows the research explanation with readable dates", async ({ page }) => {
    await mockIdeas(page, { created: [], generated: 0 });
    await page.goto("/next/ideas?idea=7");

    const detail = page.getByTestId("idea-detail");
    await expect(detail).toContainText("Most recent observed publication: 19 Sept 2026");
    await expect(detail).not.toContainText("2026-09-19T14:03:11Z");
    await expect(detail.getByRole("link", { name: /Open in Demand/ })).toHaveAttribute("href", "/next/demand?snapshot=12");
  });

  for (const [name, viewport] of Object.entries(VIEWPORTS)) {
    test(`lays out without horizontal overflow at ${name}`, async ({ page }) => {
      await mockIdeas(page, { created: [], generated: 0 });
      await page.setViewportSize(viewport);
      await page.goto("/next/ideas?idea=7");
      await expect(page.getByTestId("idea-detail")).toBeVisible();

      await expectNoHorizontalOverflow(page);
      await page.screenshot({ path: `screenshots/ideas-${name}.png`, fullPage: true });
    });
  }
});
