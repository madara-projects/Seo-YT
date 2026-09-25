import { expect, test, type Page } from "@playwright/test";
import {
  VIEWPORTS,
  choose,
  collectErrors,
  expectNoHorizontalOverflow,
  mockChannel,
  stubThumbnails,
} from "./helpers";
import { EXPERIMENT_RESULT_FIXTURE } from "../src/test/fixtures/experiment";

/**
 * Structured experiments against the running backend. Every experiment call is
 * intercepted so no test writes to the real experiment tables, and a connected
 * channel with verified videos is mocked. Requires `docker compose up -d`.
 */

const CHANNEL_ID = "UCe2efixture0000000001";

const CANDIDATES = [
  { id: 5, analysis_run_id: 9, youtube_video_id: "e2eexpv0001", published_at: "2026-09-07T11:50:35Z", ownership_verified: true, verified_channel_id: CHANNEL_ID, audit_state: "not_run", evidence_state: "mature", youtube_metadata: { title: "Does silence hurt more than words?" } },
  { id: 6, analysis_run_id: 10, youtube_video_id: "e2eexpv0002", published_at: "2026-09-08T11:50:35Z", ownership_verified: false, verified_channel_id: null, audit_state: "not_run", evidence_state: "unavailable", youtube_metadata: { title: "Unverified upload" } },
];

type Assignment = { id: number; published_video_link_id: number; role: string; youtube_video_id: string; published_at: string; title: string };

function experiment(overrides: Record<string, unknown> = {}) {
  return {
    id: 3,
    name: "Question titles vs statements",
    hypothesis: "Question titles may be associated with a higher average view percentage.",
    mode: "controlled",
    status: "draft",
    variable: "title_mechanism",
    control_definition: "A plain statement title",
    variant_definition: "The same idea asked as a question",
    success_metric: "average_view_percentage",
    secondary_metrics: [],
    minimum_sample_size: 5,
    observation_window: "24h",
    created_at: "2026-09-24T09:00:00+00:00",
    assignments: [] as Assignment[],
    latest_result: null as unknown,
    assignment_counts: { control: 0, variant: 0, observational_reference: 0 },
    ...overrides,
  };
}

async function mockExperiments(page: Page, calls: { created: unknown[]; assigned: unknown[]; statuses: string[] }, seed = [experiment()]) {
  let experiments = seed;
  await page.route("**/api/audits**", (route) => route.fulfill({ json: { candidates: CANDIDATES, total: CANDIDATES.length } }));
  await page.route("**/api/experiment-center/experiments**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === "POST" && path === "/api/experiment-center/experiments") {
      const body = request.postDataJSON();
      calls.created.push(body);
      const created = experiment({ ...body, id: 4 });
      experiments = [created, ...experiments];
      return route.fulfill({ status: 201, json: { status: "created", experiment: created } });
    }
    const match = path.match(/^\/api\/experiment-center\/experiments\/(\d+)(\/[a-z]+)?$/);
    if (match) {
      const found = experiments.find((item) => item.id === Number(match[1]))!;
      if (match[2] === "/assignments" && request.method() === "POST") {
        const body = request.postDataJSON();
        calls.assigned.push(body);
        const video = CANDIDATES.find((item) => item.id === body.published_video_link_id)!;
        found.assignments = [
          ...found.assignments,
          { id: 100, published_video_link_id: video.id, role: body.role, youtube_video_id: video.youtube_video_id, published_at: video.published_at, title: video.youtube_metadata.title },
        ];
        return route.fulfill({ status: 201, json: { status: "assigned", experiment: found } });
      }
      if (request.method() === "PATCH") {
        const body = request.postDataJSON();
        calls.statuses.push(body.status);
        found.status = body.status;
        return route.fulfill({ json: { status: "updated", experiment: found } });
      }
      return route.fulfill({ json: { experiment: found, result_versions: found.latest_result ? [{ id: 21 }] : [] } });
    }
    return route.fulfill({ json: { experiments, total: experiments.length } });
  });
  await stubThumbnails(page);
}

test.describe("Experiments", () => {
  test("creates a comparison, assigns a verified video and runs it to completion", async ({ page }) => {
    const errors = collectErrors(page);
    const calls = { created: [] as unknown[], assigned: [] as unknown[], statuses: [] as string[] };
    await mockChannel(page, true, CHANNEL_ID);
    await mockExperiments(page, calls);

    await page.goto("/next/experiments");
    await page.getByRole("button", { name: "New experiment" }).click();
    const form = page.getByTestId("experiment-form");
    await form.getByLabel("Name").fill("Hook in the first second");
    await form.getByLabel("Hypothesis").fill("Text on the first frame may keep viewers longer.");
    await choose(page, "What changes", "First-frame text");
    await form.getByLabel("Control").fill("Open on the visual");
    await form.getByLabel("Variant").fill("Open on text over black");
    await choose(page, "Comparable window", "7 days");
    await form.getByRole("button", { name: "Create comparison" }).click();

    await expect(page).toHaveURL(/\/next\/experiments\?experiment=4$/);
    expect(calls.created).toEqual([
      {
        name: "Hook in the first second",
        hypothesis: "Text on the first frame may keep viewers longer.",
        mode: "controlled",
        variable: "first_frame_text",
        control_definition: "Open on the visual",
        variant_definition: "Open on text over black",
        success_metric: "average_view_percentage",
        observation_window: "7d",
        status: "draft",
      },
    ]);

    const detail = page.getByTestId("experiment-detail");
    // Only the verified video from the connected channel is offered.
    await detail.getByRole("combobox", { name: "Verified video" }).click();
    await expect(page.getByRole("option", { name: "Unverified upload" })).toHaveCount(0);
    await page.getByRole("option", { name: "Does silence hurt more than words?" }).click();
    await choose(page, "Side", "Variant");
    await detail.getByRole("button", { name: "Add video" }).click();
    await expect(detail.getByTestId("group-variant")).toContainText("Does silence hurt more than words?");
    expect(calls.assigned).toEqual([{ published_video_link_id: 5, role: "variant", notes: "" }]);

    await detail.getByRole("button", { name: "Mark planned" }).click();
    await detail.getByRole("button", { name: "Start" }).click();
    await detail.getByRole("button", { name: "Mark completed" }).click();
    const dialog = page.getByRole("dialog", { name: "Mark completed?" });
    await dialog.getByRole("button", { name: "Mark completed" }).click();
    await expect(detail.getByText("This comparison is closed, so it takes no new videos.")).toBeVisible();
    expect(calls.statuses).toEqual(["planned", "active", "completed"]);

    expect(errors).toEqual([]);
  });

  for (const [name, viewport] of Object.entries(VIEWPORTS)) {
    test(`lays out without horizontal overflow at ${name}`, async ({ page }) => {
      await mockChannel(page, true, CHANNEL_ID);
      await mockExperiments(page, { created: [], assigned: [], statuses: [] }, [
        experiment({
          status: "active",
          latest_result: EXPERIMENT_RESULT_FIXTURE,
          assignments: [
            { id: 101, published_video_link_id: 5, role: "control", youtube_video_id: "e2eexpv0001", published_at: "2026-09-07T11:50:35Z", title: "A very long assigned video title that has to wrap neatly on a phone" },
          ],
        }),
      ]);
      await page.setViewportSize(viewport);
      await page.goto("/next/experiments?experiment=3");
      await expect(page.getByTestId("experiment-result")).toBeVisible();

      await expectNoHorizontalOverflow(page);
      await page.screenshot({ path: `screenshots/experiments-${name}.png`, fullPage: true });
    });
  }
});
