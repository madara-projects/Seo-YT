import { expect, type ConsoleMessage, type Page } from "@playwright/test";

/** Shared by the research-page specs. */

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

/** Picks an option from one of the app's labelled selects. */
export async function choose(page: Page, label: string, option: string) {
  await page.getByRole("combobox", { name: label }).click();
  await page.getByRole("option", { name: option, exact: true }).click();
}
