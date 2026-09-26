import { expect, test } from "@playwright/test";
import { VIEWPORTS, blockWrites, collectErrors, expectNoHorizontalOverflow } from "./helpers";

/**
 * Renders the real app from the running backend and checks the things a unit
 * test cannot: that the bundle executes without console errors, that the
 * layout holds at three widths, and that both themes paint.
 *
 * Requires the stack to be up: `docker compose up -d` at the repository root.
 */

test.beforeEach(async ({ page }) => {
  await blockWrites(page);
});

test.describe("React shell", () => {
  test("mounts the Creator page with no console errors", async ({ page }) => {
    const errors = collectErrors(page);

    await page.goto("/next/creator");

    await expect(page.getByRole("heading", { name: "Creator", level: 1 })).toBeVisible();
    await expect(page.getByRole("group", { name: "What are you making?" })).toBeVisible();
    await expect(page.getByLabel("Script")).toBeVisible();
    await expect(page.getByRole("button", { name: "Generate package" })).toBeVisible();

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

      await expectNoHorizontalOverflow(page);

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

  test("keeps keyboard focus inside the open navigation drawer", async ({ page }) => {
    await page.setViewportSize(VIEWPORTS.mobile);
    await page.goto("/next/creator");

    await page.getByRole("button", { name: "Open navigation" }).click();
    const drawer = page.getByRole("dialog", { name: "Navigation" });
    await expect(drawer).toBeVisible();
    // More presses than the drawer has stops: focus must wrap, never reach the page behind.
    for (let press = 0; press < 30; press += 1) await page.keyboard.press("Tab");
    expect(await drawer.evaluate((node) => node.contains(document.activeElement))).toBe(true);
  });

  test("serves the page with no inline script or event handler", async ({ request }) => {
    // The Content Security Policy allows only scripts served as files by this server.
    const html = await (await request.get("/next/creator")).text();
    expect(html).not.toMatch(/<script(?![^>]*\bsrc=)[^>]*>/i);
    expect(html).not.toMatch(/\son[a-z]+\s*=/i);
    expect(html).toContain("/app-assets/theme-init.js");
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

  test("expands the optional details", async ({ page }) => {
    await page.goto("/next/creator");

    const trigger = page.getByRole("button", { name: /More details \(optional\)/ });
    await expect(trigger).toHaveAttribute("aria-expanded", "false");

    await trigger.click();
    await expect(trigger).toHaveAttribute("aria-expanded", "true");
    await expect(page.getByLabel("Who is it for?")).toBeVisible();
  });

  test("keeps Generate disabled, with the reason, until there is a script", async ({ page }) => {
    await page.goto("/next/creator");

    const generate = page.getByRole("button", { name: "Generate package" });
    await expect(generate).toBeDisabled();
    await expect(page.getByText("Add your script or idea to generate a package.")).toBeVisible();

    await page.getByLabel("Script").fill("Silence says everything.");
    await expect(generate).toBeEnabled();
  });

  test("keeps the Generate bar in view while the form scrolls", async ({ page }) => {
    await page.setViewportSize(VIEWPORTS.mobile);
    await page.goto("/next/creator");

    await page.getByRole("button", { name: /More details \(optional\)/ }).click();
    await page.mouse.wheel(0, 400);
    await expect(page.getByRole("button", { name: "Generate package" })).toBeInViewport();
  });

  test("folds the desktop sidebar to an icon rail and remembers it", async ({ page }) => {
    await page.setViewportSize(VIEWPORTS.desktop);
    await page.goto("/next/creator");
    const sidebar = page.locator("#app-sidebar");
    const wide = (await sidebar.boundingBox())?.width ?? 0;

    await page.getByRole("button", { name: "Collapse sidebar" }).click();
    await expect(sidebar).toHaveAttribute("data-collapsed", "true");
    await expect.poll(async () => (await sidebar.boundingBox())?.width ?? 0).toBeLessThan(wide / 2);
    // Icons only, but every link keeps its name.
    await expect(page.getByRole("link", { name: "History" })).toBeVisible();
    await page.screenshot({ path: "screenshots/creator-sidebar-rail.png" });

    await page.reload();
    await expect(sidebar).toHaveAttribute("data-collapsed", "true");
    await page.getByRole("button", { name: "Expand sidebar" }).click();
    await expect(sidebar).toHaveAttribute("data-collapsed", "false");
  });

  test("reaches the primary action by keyboard alone", async ({ page }) => {
    await page.goto("/next/creator");

    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
  });
});
