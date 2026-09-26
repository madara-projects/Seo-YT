import { describe, expect, it, vi, beforeAll, beforeEach, afterEach } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { App } from "./App";

/**
 * Mount smoke tests.
 *
 * A green `vite build` only proves the bundle compiles; these prove the
 * provider stack, router, lazy routes and the Creator page actually render.
 */

/**
 * Lazy routes load their chunk on first render; under a parallel test run on a
 * busy machine that has exceeded the default wait, so their first query waits
 * longer. The assertions themselves are unchanged.
 */
const LAZY = { timeout: 20_000 };

// The first import of a lazy page transforms its whole module graph (Recharts
// for Dashboard and Channel), which on a cold cache and a busy machine has
// outrun the wait above. Loading them once here, under a hook timeout sized
// for that, leaves each test's wait to measure rendering alone.
beforeAll(async () => {
  await Promise.all([
    import("@/pages/Dashboard"),
    import("@/pages/History"),
    import("@/pages/Channel"),
    import("@/pages/Settings"),
    import("@/pages/Ideas"),
    import("@/pages/Demand"),
    import("@/pages/Audits"),
    import("@/pages/Experiments"),
    import("@/pages/Watchlist"),
  ]);
}, 120_000);

function renderApp(route = "/creator") {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <App />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  // The sidebar health probe would otherwise hit the network under jsdom.
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ status: "ok", version: "0.13.0" }),
    }),
  );
});

afterEach(() => vi.unstubAllGlobals());

describe("App shell", () => {
  it("renders the Creator page with its navigation", async () => {
    renderApp();

    expect(await screen.findByRole("heading", { name: "Creator", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: /workflow stages/i })).toBeInTheDocument();
  });

  it("starts on the idea stage with the script field required", async () => {
    renderApp();

    expect(await screen.findByLabelText("Script")).toBeInTheDocument();
    expect(screen.getByText(/Stage 1 \/ 8/)).toBeInTheDocument();
  });

  it("locks later stages until an analysis exists", async () => {
    renderApp();

    const compare = await screen.findByRole("button", { name: /Compare/ });
    expect(compare).toBeDisabled();
    expect(compare).toHaveAttribute("title", expect.stringContaining("Run Analyze"));
  });

  it("validates an empty script instead of calling the API", async () => {
    const user = userEvent.setup();
    renderApp();

    await user.click(await screen.findByRole("button", { name: /Generate SEO package/i }));

    expect(await screen.findByText("Enter a script or video idea first.")).toBeInTheDocument();
    // Only the health probe may have fired; /analyze must not have been called.
    const calls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls;
    expect(calls.every(([url]) => !String(url).includes("/analyze"))).toBe(true);
  });

  it("loads a sample idea into the script field", async () => {
    const user = userEvent.setup();
    renderApp();

    await user.click(await screen.findByRole("button", { name: "Quote short" }));

    await waitFor(() =>
      expect(screen.getByLabelText("Script")).toHaveValue(
        "The biggest betrayal is knowing that if you didn't find out, they would have never told you.",
      ),
    );
  });

  it("renders the History page and names the browser tab after it", async () => {
    renderApp("/history");

    expect(
      await screen.findByRole("heading", { name: "Package library", level: 1 }, LAZY),
    ).toBeInTheDocument();
    expect(document.title).toBe("History · Win-Engine");
  });

  it("renders the Dashboard page", async () => {
    renderApp("/dashboard");

    expect(
      await screen.findByRole("heading", { name: "Dashboard", level: 1 }, LAZY),
    ).toBeInTheDocument();
    expect(document.title).toBe("Dashboard · Win-Engine");
  });

  it.each([
    ["/ideas", "Ideas", "Backlog"],
    ["/watchlist", "Watchlist", "Watch something new"],
    ["/audits", "Audits", "Published videos"],
    ["/experiments", "Experiments", "Comparisons"],
  ])("renders the %s page", async (route, title, section) => {
    renderApp(route);

    expect(await screen.findByRole("heading", { name: title, level: 1 }, LAZY)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: section })).toBeInTheDocument();
    expect(document.title).toBe(`${title} · Win-Engine`);
  });

  it("marks no page in the navigation as legacy", async () => {
    renderApp();

    const nav = await screen.findByRole("navigation", { name: "Main" });
    expect(nav).not.toHaveTextContent(/legacy/i);
  });

  it("renders the Settings page with its section navigation", async () => {
    renderApp("/settings");

    expect(
      await screen.findByRole("heading", { name: "Settings", level: 1 }, LAZY),
    ).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Settings sections" })).toBeInTheDocument();
  });

  it("renders the Demand page with its research form", async () => {
    renderApp("/demand");

    expect(await screen.findByRole("heading", { name: "Demand", level: 1 }, LAZY)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Research a topic" })).toBeInTheDocument();
  });

  it("renders the Channel page", async () => {
    renderApp("/channel");

    expect(await screen.findByRole("heading", { name: "Channel", level: 1 }, LAZY)).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /Connect YouTube channel/ })).toBeInTheDocument();
  });

  it("jumps between pages from the command palette", async () => {
    const user = userEvent.setup();
    renderApp();
    await screen.findByRole("heading", { name: "Creator", level: 1 });

    await user.keyboard("{Control>}k{/Control}");
    const search = await screen.findByRole("combobox", { name: "Search pages and actions" });
    await user.type(search, "history");
    await user.keyboard("{Enter}");

    expect(
      await screen.findByRole("heading", { name: "Package library", level: 1 }, LAZY),
    ).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Search pages and actions" })).not.toBeInTheDocument();
  });

  it("opens the classic dashboard at /app from the palette", async () => {
    const open = vi.spyOn(window, "open").mockImplementation(() => null);
    const user = userEvent.setup();
    renderApp();
    await screen.findByRole("heading", { name: "Creator", level: 1 });

    await user.keyboard("{Control>}k{/Control}");
    await user.type(await screen.findByRole("combobox", { name: "Search pages and actions" }), "classic");
    await user.keyboard("{Enter}");

    // /app is the static classic dashboard; the old embedded route no longer exists.
    expect(open).toHaveBeenCalledWith("/app", "_blank", "noopener");
    open.mockRestore();
  });

  it("returns focus to the menu button when the navigation drawer closes", async () => {
    const user = userEvent.setup();
    renderApp();
    const menu = await screen.findByRole("button", { name: "Open navigation" });

    await user.click(menu);
    expect(await screen.findByRole("dialog", { name: "Navigation" })).toBeInTheDocument();
    await user.keyboard("{Escape}");

    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Navigation" })).not.toBeInTheDocument());
    expect(menu).toHaveFocus();
  });

  it("closes the drawer when the window widens past the sidebar breakpoint", async () => {
    const listeners: Array<(event: { matches: boolean }) => void> = [];
    const original = window.matchMedia;
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: (_: string, listener: (event: { matches: boolean }) => void) => {
        if (query === "(min-width: 64rem)") listeners.push(listener);
      },
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
      onchange: null,
    })) as unknown as typeof window.matchMedia;
    try {
      const user = userEvent.setup();
      renderApp();
      await user.click(await screen.findByRole("button", { name: "Open navigation" }));
      expect(await screen.findByRole("dialog", { name: "Navigation" })).toBeInTheDocument();

      // A hidden drawer would still hold the page inert, so it closes instead.
      act(() => listeners.forEach((listener) => listener({ matches: true })));

      await waitFor(() => expect(screen.queryByRole("dialog", { name: "Navigation" })).not.toBeInTheDocument());
    } finally {
      window.matchMedia = original;
    }
  });

  it("offers a skip link for keyboard users", async () => {
    renderApp();
    expect(await screen.findByRole("link", { name: "Skip to content" })).toBeInTheDocument();
  });
});
