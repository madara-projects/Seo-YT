import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ThemeProvider } from "@/lib/theme";
import { AppShell } from "./AppShell";

const original = window.matchMedia;

/** A desktop-width window: the rail shortcut only works where the sidebar shows. */
function desktop() {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query === "(min-width: 64rem)",
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}

function renderShell() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <MemoryRouter initialEntries={["/creator"]}>
          <Routes>
            <Route element={<AppShell />}>
              <Route path="/creator" element={<h1>Creator</h1>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

function sidebar() {
  return document.getElementById("app-sidebar") as HTMLElement;
}

beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, status: 200, text: async () => JSON.stringify({ status: "ok" }) }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.matchMedia = original;
  localStorage.clear();
});

describe("AppShell sidebar", () => {
  it("folds to an icon rail and back, and says which way the button goes", async () => {
    const user = userEvent.setup();
    renderShell();

    const toggle = within(sidebar()).getByRole("button", { name: "Collapse sidebar" });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(toggle).toHaveAttribute("aria-controls", "app-sidebar");

    await user.click(toggle);

    expect(sidebar()).toHaveAttribute("data-collapsed", "true");
    const expand = within(sidebar()).getByRole("button", { name: "Expand sidebar" });
    expect(expand).toHaveAttribute("aria-expanded", "false");
    // Icons only, but every link keeps its name.
    expect(within(sidebar()).getByRole("link", { name: "History" })).toBeInTheDocument();
    expect(within(sidebar()).getByRole("link", { name: "New package" })).toBeInTheDocument();

    await user.click(expand);
    expect(sidebar()).toHaveAttribute("data-collapsed", "false");
  });

  it("remembers the rail across visits", async () => {
    const user = userEvent.setup();
    const first = renderShell();
    await user.click(within(sidebar()).getByRole("button", { name: "Collapse sidebar" }));
    expect(localStorage.getItem("win-engine-sidebar")).toBe("collapsed");
    first.unmount();

    renderShell();

    expect(sidebar()).toHaveAttribute("data-collapsed", "true");
  });

  it("names an icon beside it on keyboard focus in the rail", async () => {
    localStorage.setItem("win-engine-sidebar", "collapsed");
    renderShell();

    within(sidebar()).getByRole("link", { name: "History" }).focus();

    expect(await screen.findByTestId("rail-tooltip")).toHaveTextContent("History");
  });

  it("folds with Ctrl+B on a desktop, but not while typing", async () => {
    desktop();
    const user = userEvent.setup();
    renderShell();

    await user.keyboard("{Control>}b{/Control}");
    expect(sidebar()).toHaveAttribute("data-collapsed", "true");

    const search = document.createElement("input");
    document.body.appendChild(search);
    search.focus();
    await user.keyboard("{Control>}b{/Control}");
    expect(sidebar()).toHaveAttribute("data-collapsed", "true");
    search.remove();
  });
});
