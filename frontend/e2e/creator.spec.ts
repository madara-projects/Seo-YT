import { expect, test, type Page } from "@playwright/test";
import { VIEWPORTS, blockWrites, collectErrors, expectNoHorizontalOverflow } from "./helpers";

/**
 * The Creator's two screens against the running backend. `/analyze` is
 * answered here, so no test spends YouTube quota or calls Gemini, and the
 * selection save is answered too, so nothing is written to History.
 * Requires `docker compose up -d`.
 */

const RESULT = {
  title: "Why silence hurts more than words",
  description: "A short reflection on the things we never say.",
  tags: ["silence hurts", "unsaid words", "shorts"],
  hashtags: ["#shorts", "#silence"],
  generation_source: "gemini",
  history_run_id: 9001,
  research_warnings: ["Only 2 public results matched the topic; research was limited."],
  title_variants: ["The words I never said"],
  title_thumbnail_packages: [
    { package_id: "package-a", title: "Why silence hurts more than words", quality_status: "approved", misleading_risk: "low" },
    { package_id: "package-b", title: "Silence says everything", quality_status: "approved", misleading_risk: "low" },
  ],
};

async function mockAnalyze(page: Page, bodies: unknown[]) {
  await page.route("**/analyze", (route) => {
    bodies.push(route.request().postDataJSON());
    return route.fulfill({ json: RESULT });
  });
  await page.route("**/api/history/runs/9001", (route) => route.fulfill({ json: { id: 9001, selected_package: null } }));
  await page.route("**/api/history/runs/9001/selection", (route) => route.fulfill({ json: { status: "selected" } }));
}

/** Nothing a test does may change saved data: writes are answered by its own routes or aborted. */
test.beforeEach(async ({ page }) => {
  await blockWrites(page);
});

test.describe("Creator", () => {
  test("generates a long tutorial and opens the results on the Package tab", async ({ page }) => {
    const errors = collectErrors(page);
    const bodies: unknown[] = [];
    await mockAnalyze(page, bodies);
    await page.goto("/creator");

    // The radios are visually hidden inside their cards; the card (label) takes the click.
    await page.getByRole("radio", { name: /Long video/ }).check({ force: true });
    await page.getByRole("radio", { name: "Tutorial" }).check({ force: true });
    await page.getByLabel("Script").fill("How I edit a vlog in one hour.");
    await expect(page.getByTestId("setup-summary")).toHaveText("Long video · Tutorial · English · Global");
    await page.getByRole("button", { name: "Generate package" }).click();

    await expect(page.getByRole("tab", { name: "Package" })).toHaveAttribute("aria-selected", "true");
    expect(bodies).toEqual([expect.objectContaining({ video_format: "tutorial" })]);
    await expect(page.getByTestId("package-card")).toContainText("Why silence hurts more than words");
    await page.screenshot({ path: "screenshots/creator-results.png" });

    await page.getByRole("tab", { name: "Compare options" }).click();
    await expect(page).toHaveURL(/[?&]tab=compare(&|$)/);

    await page.getByRole("button", { name: /Edit and regenerate/ }).click();
    await expect(page.getByLabel("Script")).toHaveValue("How I edit a vlog in one hour.");
    await page.getByRole("button", { name: /Back to results/ }).click();
    await expect(page.getByRole("tab", { name: "Compare options" })).toHaveAttribute("aria-selected", "true");

    expect(errors).toEqual([]);
  });

  test("keeps the package panel and Generate beside the form on wide screens", async ({ page }) => {
    await page.setViewportSize(VIEWPORTS.desktop);
    await page.goto("/creator");

    const panel = page.getByRole("complementary", { name: "Your package" });
    await expect(panel.getByRole("button", { name: "Generate package" })).toBeVisible();
    await expect(panel.getByRole("combobox", { name: "Output language" })).toBeVisible();
    await expect(page.getByTestId("setup-bar")).toHaveCount(0);
    // Side by side, never overlapping, and the setup fits one screen with the details closed.
    const form = await page.getByRole("group", { name: "What are you making?" }).boundingBox();
    const side = await panel.boundingBox();
    expect(form && side && side.x >= form.x + form.width).toBe(true);
    const details = await page.getByRole("button", { name: /More details \(optional\)/ }).boundingBox();
    expect(details && details.y + details.height <= 900).toBe(true);
  });

  test("keeps Generate in a bottom bar on phones", async ({ page }) => {
    await page.setViewportSize(VIEWPORTS.mobile);
    await page.goto("/creator");

    await expect(page.getByTestId("setup-bar").getByRole("button", { name: "Generate package" })).toBeVisible();
    await expect(page.getByRole("complementary", { name: "Your package" })).toHaveCount(0);
  });

  test("opens an old ?stage= link on the matching tab", async ({ page }) => {
    await mockAnalyze(page, []);
    await page.goto("/creator");
    await page.getByLabel("Script").fill("Silence says everything.");
    await page.getByRole("button", { name: "Generate package" }).click();
    await expect(page.getByRole("tab", { name: "Package" })).toBeVisible();

    // An in-app link to an old stage, as History or a bookmark might hold.
    await page.evaluate(() => {
      window.history.pushState({}, "", "/creator?stage=checklist");
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    await expect(page.getByRole("tab", { name: "Before you publish" })).toHaveAttribute("aria-selected", "true");
  });

  for (const [name, viewport] of Object.entries(VIEWPORTS)) {
    test(`lays out the results without horizontal overflow at ${name}`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await mockAnalyze(page, []);
      await page.goto("/creator");
      await page.getByLabel("Script").fill("Silence says everything.");
      await page.getByRole("button", { name: "Generate package" }).click();
      await expect(page.getByRole("tab", { name: "Package" })).toBeVisible();

      await expectNoHorizontalOverflow(page);
      await page.screenshot({ path: `screenshots/creator-results-${name}.png`, fullPage: true });
    });
  }
});
