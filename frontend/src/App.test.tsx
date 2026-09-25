import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
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

  it("renders the migrated History page rather than a placeholder", async () => {
    renderApp("/history");

    expect(
      await screen.findByRole("heading", { name: "Package library", level: 1 }, LAZY),
    ).toBeInTheDocument();
    expect(screen.queryByText("Not migrated yet")).not.toBeInTheDocument();
  });

  it("renders the migrated Dashboard page", async () => {
    renderApp("/dashboard");

    expect(
      await screen.findByRole("heading", { name: "Dashboard", level: 1 }, LAZY),
    ).toBeInTheDocument();
    expect(screen.queryByText("Not migrated yet")).not.toBeInTheDocument();
  });

  it("still links unmigrated pages out to the legacy dashboard", async () => {
    renderApp("/ideas");

    expect(await screen.findByRole("heading", { name: "Ideas", level: 1 }, LAZY)).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /legacy dashboard/i })).toHaveAttribute(
      "href",
      "/dashboard_legacy#ideas",
    );
  });

  it("renders the Settings page instead of the legacy placeholder", async () => {
    renderApp("/settings");

    expect(
      await screen.findByRole("heading", { name: "Settings", level: 1 }, LAZY),
    ).toBeInTheDocument();
    expect(screen.queryByText("Not migrated yet")).not.toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Settings sections" })).toBeInTheDocument();
  });

  it("renders the Demand page instead of the legacy placeholder", async () => {
    renderApp("/demand");

    expect(await screen.findByRole("heading", { name: "Demand", level: 1 }, LAZY)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Research a topic" })).toBeInTheDocument();
    expect(screen.queryByText("Not migrated yet")).not.toBeInTheDocument();
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

  it("offers a skip link for keyboard users", async () => {
    renderApp();
    expect(await screen.findByRole("link", { name: "Skip to content" })).toBeInTheDocument();
  });
});
