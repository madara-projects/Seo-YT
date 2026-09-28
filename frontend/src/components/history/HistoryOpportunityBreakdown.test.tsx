import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { HistoryRow } from "./HistoryRow";
import { HistoryOpportunityBreakdown } from "./HistoryOpportunityBreakdown";
import { BREAKDOWN } from "@/test/fixtures/opportunity";
import type { HistoryRun, HistoryRunDetail } from "@/api/historyTypes";

const RUN: HistoryRun = {
  id: 7,
  created_at: "2026-09-20T10:00:00Z",
  title: "Cold brew at home",
  opportunity_score: 48.34,
  title_score: 7.2,
  query: "cold brew",
  has_full_package: true,
};

function detail(breakdown: unknown): HistoryRunDetail {
  return {
    ...RUN,
    opportunity_label: "WORKABLE",
    package: { opportunity_gap_analysis: { opportunity_score: { score: 48.34, breakdown } } },
  } as HistoryRunDetail;
}

let response: unknown;

function renderRow() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <HistoryRow
        run={RUN}
        selected={false}
        isOpen={false}
        onToggleSelect={() => undefined}
        onOpen={() => undefined}
        onLink={() => undefined}
        onDelete={() => undefined}
      />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (String(url) !== "/api/history/runs/7") throw new Error(`Unexpected request ${url}`);
      return { ok: true, status: 200, text: async () => JSON.stringify(response) };
    }),
  );
});

afterEach(() => vi.unstubAllGlobals());

describe("History row score inputs", () => {
  it("loads the saved breakdown only when asked, next to the score", async () => {
    response = detail(BREAKDOWN);
    renderRow();
    expect(fetch).not.toHaveBeenCalled();

    const toggle = screen.getByRole("button", { name: "Score inputs for Cold brew at home" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(toggle);

    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(await screen.findAllByTestId("opportunity-input")).toHaveLength(5);
    expect(screen.getByText("Medium input confidence")).toBeInTheDocument();
    expect(screen.getByText(/not a prediction of views/)).toBeInTheDocument();
  });

  it("says an older package has no stored breakdown", async () => {
    response = detail(undefined);
    renderRow();
    await userEvent.click(screen.getByRole("button", { name: "Score inputs for Cold brew at home" }));

    expect(await screen.findByText(/saved before score breakdowns were stored/)).toBeInTheDocument();
  });
});

describe("HistoryOpportunityBreakdown", () => {
  it("shows the stored breakdown in the package detail", async () => {
    render(<HistoryOpportunityBreakdown run={detail(BREAKDOWN)} />);
    await userEvent.click(screen.getByRole("button", { name: /why this score/i }));
    expect(screen.getAllByTestId("opportunity-input")).toHaveLength(5);
  });

  it("says so when an older record stored no package at all", async () => {
    render(<HistoryOpportunityBreakdown run={{ ...RUN, package: null } as HistoryRunDetail} />);
    await userEvent.click(screen.getByRole("button", { name: /why this score/i }));
    expect(screen.getByText(/saved before score breakdowns were stored/)).toBeInTheDocument();
  });
});
