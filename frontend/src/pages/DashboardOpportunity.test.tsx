import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import DashboardPage from "./Dashboard";
import { INSUFFICIENT_CALIBRATION } from "@/test/fixtures/opportunity";

const PREDICTION_CLAIM = /(?<!not a )predict(s|ed|ion)? (of )?(views|reach|ctr)|expected views|will get \d|guarantee/i;

function json(body: unknown) {
  return { ok: true, status: 200, text: async () => JSON.stringify(body) };
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (String(url) === "/api/history") {
        return json({ scorecard: { total_runs: 3, avg_opportunity_score: 48.34, avg_title_score: 7.1 }, learning: {}, owned_performance: {} });
      }
      if (String(url) === "/api/opportunity-score/calibration") return json(INSUFFICIENT_CALIBRATION);
      return json({});
    }),
  );
});

afterEach(() => vi.unstubAllGlobals());

describe("Dashboard opportunity score", () => {
  it("says the average is of a local heuristic and names what it averages", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <DashboardPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const card = await screen.findByText("48 / 100");
    const stat = within(card.closest<HTMLElement>('[data-stat="Avg opportunity score"]')!);
    expect(
      stat.getByText("Averages a local heuristic, not a prediction of views. Calculated from your 3 saved analyses."),
    ).toBeInTheDocument();
    await userEvent.click(stat.getByRole("button", { name: /what it averages/i }));
    expect(stat.getAllByRole("listitem")).toHaveLength(5);
    expect(stat.getByText("Competition room")).toBeInTheDocument();

    expect(screen.getByRole("heading", { name: "Does the Opportunity Score track your results?" })).toBeInTheDocument();
    expect(await screen.findByText("Not enough evidence yet")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(PREDICTION_CLAIM);
  });
});
