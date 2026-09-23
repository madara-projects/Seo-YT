import { expect, test, type ConsoleMessage, type Page } from "@playwright/test";

/**
 * Renders the real app from the running backend and checks the things a unit
 * test cannot: that the bundle executes without console errors, that the
 * layout holds at three widths, and that both themes paint.
 *
 * Requires the stack to be up: `docker compose up -d` at the repository root.
 */

const VIEWPORTS = {
  desktop: { width: 1440, height: 900 },
  tablet: { width: 834, height: 1112 },
  mobile: { width: 390, height: 844 },
} as const;

function collectErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (message: ConsoleMessage) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(String(error)));
  return errors;
}

test.describe("React shell", () => {
  test("mounts the Creator page with no console errors", async ({ page }) => {
    const errors = collectErrors(page);

    await page.goto("/next/creator");

    await expect(page.getByRole("heading", { name: "Creator", level: 1 })).toBeVisible();
    await expect(page.getByLabel("Script")).toBeVisible();
    await expect(page.getByRole("button", { name: /Generate SEO package/i })).toBeVisible();

    expect(errors).toEqual([]);
  });

  test("serves a deep link directly without a client redirect", async ({ page }) => {
    const response = await page.goto("/next/history");
    expect(response?.status()).toBe(200);
    await expect(page.getByRole("heading", { name: "Package library", level: 1 })).toBeVisible();
  });

  test("keeps the legacy dashboard reachable and untouched", async ({ page }) => {
    const response = await page.goto("/app");
    expect(response?.status()).toBe(200);
    // The legacy shell, not the React app.
    await expect(page.locator("#view-creator")).toHaveCount(1);
  });

  for (const [name, viewport] of Object.entries(VIEWPORTS)) {
    test(`lays out without horizontal overflow at ${name}`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await page.goto("/next/creator");
      await expect(page.getByRole("heading", { name: "Creator", level: 1 })).toBeVisible();

      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow).toBeLessThanOrEqual(1);

      await page.screenshot({ path: `screenshots/creator-${name}.png`, fullPage: false });
    });
  }

  test("hides the sidebar on mobile and opens it as a drawer", async ({ page }) => {
    await page.setViewportSize(VIEWPORTS.mobile);
    await page.goto("/next/creator");

    const openButton = page.getByRole("button", { name: "Open navigation" });
    await expect(openButton).toBeVisible();

    await openButton.click();
    const drawer = page.getByRole("dialog", { name: "Navigation" });
    await expect(drawer).toBeVisible();
    await page.screenshot({ path: "screenshots/nav-mobile-drawer.png" });

    await page.keyboard.press("Escape");
    await expect(drawer).toBeHidden();
  });

  test("shows the desktop sidebar at full width", async ({ page }) => {
    await page.setViewportSize(VIEWPORTS.desktop);
    await page.goto("/next/creator");

    await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Open navigation" })).toBeHidden();
  });

  test("toggles between dark and light themes", async ({ page }) => {
    await page.setViewportSize(VIEWPORTS.desktop);
    await page.goto("/next/creator");

    const toggle = page.getByRole("button", { name: /Switch to (light|dark) theme/ });
    const startedDark = await page.evaluate(() =>
      document.documentElement.classList.contains("dark"),
    );

    await toggle.click();
    await expect
      .poll(() => page.evaluate(() => document.documentElement.classList.contains("dark")))
      .toBe(!startedDark);

    await page.screenshot({ path: "screenshots/creator-theme-toggled.png" });

    // The preference must survive a reload.
    await page.reload();
    await expect
      .poll(() => page.evaluate(() => document.documentElement.classList.contains("dark")))
      .toBe(!startedDark);
  });

  test("expands the collapsible creator brief", async ({ page }) => {
    await page.goto("/next/creator");

    const trigger = page.getByRole("button", { name: /Creator brief \(optional\)/ });
    await expect(trigger).toHaveAttribute("aria-expanded", "false");

    await trigger.click();
    await expect(trigger).toHaveAttribute("aria-expanded", "true");
    await expect(page.getByLabel("Target audience")).toBeVisible();
  });

  test("blocks an empty submission in the field, not at the API", async ({ page }) => {
    await page.goto("/next/creator");

    await page.getByRole("button", { name: /Generate SEO package/i }).click();
    await expect(page.getByText("Enter a script or video idea first.")).toBeVisible();
  });

  test("reaches the primary action by keyboard alone", async ({ page }) => {
    await page.goto("/next/creator");

    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
  });
});
