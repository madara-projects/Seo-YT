import { expect, test, type Page } from "@playwright/test";
import { VIEWPORTS, blockWrites, collectErrors, expectNoHorizontalOverflow } from "./helpers";
import { AI_SHORTS_PLAN, AI_SHORTS_PLAN_SUMMARIES } from "../src/test/fixtures/aiShorts";

/**
 * AI Shorts against the running backend. Every `/api/ai-shorts` call is
 * answered here: generating spends Gemini calls and writes to History, and
 * deleting would remove a saved plan. Requires `docker compose up -d`.
 */

const QUOTE = AI_SHORTS_PLAN.quote;

/** Answers the plan list, one plan's detail, generation and deletion. Counts the writes. */
async function mockAiShorts(page: Page, calls: { generated: unknown[]; deleted: number[] }) {
  await page.route("**/api/ai-shorts/**", (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === "POST" && path === "/api/ai-shorts/generate") {
      calls.generated.push(request.postDataJSON());
      return route.fulfill({ json: AI_SHORTS_PLAN });
    }
    const detail = path.match(/^\/api\/ai-shorts\/plans\/(\d+)$/);
    if (detail && request.method() === "DELETE") {
      calls.deleted.push(Number(detail[1]));
      return route.fulfill({ status: 204, body: "" });
    }
    if (detail) {
      return Number(detail[1]) === AI_SHORTS_PLAN.id
        ? route.fulfill({ json: AI_SHORTS_PLAN })
        : route.fulfill({ status: 404, json: { error: { code: "not_found", message: "AI Short not found." } } });
    }
    if (request.method() === "GET") return route.fulfill({ json: { plans: AI_SHORTS_PLAN_SUMMARIES } });
    return route.fallback();
  });
}

/** Nothing a test does may change saved data: writes are answered by its own routes or aborted. */
test.beforeEach(async ({ page }) => {
  await blockWrites(page);
});

test.describe("AI Shorts", () => {
  test("writes two Flow prompts and the package from a quote, with no console errors", async ({ page }) => {
    const errors = collectErrors(page);
    const calls = { generated: [] as unknown[], deleted: [] as number[] };
    await mockAiShorts(page, calls);

    await page.goto("/ai-shorts");
    await expect(page.getByRole("heading", { name: "AI Shorts", level: 1 })).toBeVisible();
    await expect(page.getByText("Quote in, Short out")).toBeVisible();

    const write = page.getByRole("button", { name: "Write Flow prompts" });
    await expect(write).toBeDisabled();
    await expect(page.getByText("Type the quote first.")).toBeVisible();

    await page.getByLabel("Quote").fill(QUOTE);
    await expect(write).toBeEnabled();
    await expect(page.getByText("Uses 2–4 Gemini calls. No YouTube quota.")).toBeVisible();
    await write.click();

    const header = page.getByRole("region", { name: "This AI Short" });
    await expect(header).toContainText(QUOTE);
    await expect(header).toContainText("Written with Gemini");
    await expect(page).toHaveURL(/\/ai-shorts\?plan=31$/);
    expect(calls.generated).toEqual([
      { quote: QUOTE, language: "english", parts: 2, mood_hint: "", region: "global" },
    ]);

    const prompts = page.getByTestId("shot-prompt");
    await expect(prompts).toHaveCount(2);
    await expect(prompts.nth(0)).toContainText("A dim kitchen at night");
    await expect(prompts.nth(1)).toContainText("The phone screen lights up face-down");
    await expect(page.getByRole("heading", { name: "Part 2 · 8 s · Extend from Part 1" })).toBeVisible();
    await expect(page.getByTestId("flow-guide")).toContainText("Open Google Flow and start a new project.");
    await expect(page.getByTestId("text-overlay")).toContainText("from the very first frame");
    await expect(page.getByTestId("shorts-package")).toContainText(AI_SHORTS_PLAN.package!.title!);
    await expect(page.getByRole("button", { name: "Copy upload package" })).toBeEnabled();
    await page.screenshot({ path: "screenshots/ai-shorts-results.png", fullPage: true });

    expect(errors).toEqual([]);
  });

  test("opens a recent plan and asks before deleting, deleting nothing on cancel", async ({ page }) => {
    const calls = { generated: [] as unknown[], deleted: [] as number[] };
    await mockAiShorts(page, calls);

    await page.goto("/ai-shorts");
    const rows = page.getByTestId("ai-shorts-plan");
    await expect(rows).toHaveCount(2);
    await expect(rows.nth(1).getByRole("link", { name: /Open in History/ })).toHaveAttribute("href", "/history?run=4199");

    // The row itself; its Delete button is named after the quote too.
    await rows.first().getByRole("button", { name: /^“The biggest betrayal/ }).click();
    await expect(page).toHaveURL(/\/ai-shorts\?plan=31$/);
    const header = page.getByRole("region", { name: "This AI Short" });
    await expect(header).toContainText(QUOTE);
    // The recent-plan rows carry "Open in History" links too, so the check stays inside the header.
    await expect(header.getByRole("link", { name: "Open in History" })).toHaveAttribute("href", "/history?run=4201");

    await rows.first().getByRole("button", { name: /^Delete:/ }).click();
    const dialog = page.getByRole("dialog", { name: "Delete this AI Short?" });
    await expect(dialog).toBeVisible();
    // Focus starts on Cancel, so Enter straight away never deletes.
    await expect(dialog.getByRole("button", { name: "Cancel" })).toBeFocused();
    await dialog.getByRole("button", { name: "Cancel" }).click();
    await expect(dialog).toBeHidden();
    expect(calls.deleted).toEqual([]);
    expect(calls.generated).toEqual([]);
  });

  for (const [name, viewport] of Object.entries(VIEWPORTS)) {
    test(`lays out the results without horizontal overflow at ${name}`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await mockAiShorts(page, { generated: [], deleted: [] });

      await page.goto("/ai-shorts?plan=31");
      await expect(page.getByRole("region", { name: "This AI Short" })).toBeVisible();
      await expect(page.getByTestId("shot-prompt")).toHaveCount(2);

      await expectNoHorizontalOverflow(page);
      await page.screenshot({ path: `screenshots/ai-shorts-${name}.png`, fullPage: true });
    });
  }

  test("lays out without horizontal overflow on a 360px phone", async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 780 });
    await mockAiShorts(page, { generated: [], deleted: [] });

    await page.goto("/ai-shorts?plan=31");
    await expect(page.getByTestId("shot-prompt")).toHaveCount(2);

    await expectNoHorizontalOverflow(page);
  });
});
