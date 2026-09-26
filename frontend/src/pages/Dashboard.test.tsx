import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import DashboardPage from "./Dashboard";

let fetchMock: ReturnType<typeof vi.fn>;

function json(body: unknown, status = 200) {
  return { ok: status < 400, status, text: async () => JSON.stringify(body) };
}

function renderDashboard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/"]}>
        <DashboardPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  fetchMock = vi.fn(async (url: string) => {
    if (String(url) === "/api/history") {
      return json({ error: { code: "database_unavailable", message: "The database is unavailable.", request_id: "req-5" } }, 503);
    }
    if (String(url) === "/api/learning/cohorts") {
      return json({ sample_size: 0, next_threshold: 5, confidence_label: "Collecting evidence", learning_allowed: false });
    }
    return json({});
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

describe("DashboardPage", () => {
  it("doesn't turn a failed summary into facts about the channel or the library", async () => {
    renderDashboard();

    expect(await screen.findByText("The database is unavailable.")).toBeInTheDocument();
    // Nothing is known about the connection or the saved packages.
    expect(screen.queryByText("Not connected")).not.toBeInTheDocument();
    expect(screen.queryByText(/No saved packages yet/)).not.toBeInTheDocument();
    expect(screen.queryByText(/No scored titles yet/)).not.toBeInTheDocument();
    expect(screen.queryByText(/No retention assessments/)).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Key numbers" })).not.toBeInTheDocument();
    expect(screen.getByText(/Channel status is unavailable/)).toBeInTheDocument();
    expect(screen.getByText("Recent packages are unavailable right now.")).toBeInTheDocument();
    expect(screen.getByText("Scored titles are unavailable right now.")).toBeInTheDocument();
  });
});
