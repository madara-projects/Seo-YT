import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DecisionStage } from "./DecisionStage";
import type { AnalyzeResponse, PackageOption } from "@/api/types";

const DATA: AnalyzeResponse = { title: "How I fixed my sleep", description: "", tags: [], hashtags: [], history_run_id: 42 };

/** Wording that would present a heuristic as a forecast. "Not a prediction" is allowed. */
const PREDICTION_CLAIM = /(?<!not a )predict(s|ed|ion)? (of )?(views|reach|ctr)|expected views|will get \d|guarantee/i;

const SELECTED: PackageOption = {
  id: "package-a", packageId: "package-a", label: "Package A", primary: true,
  title: "How I fixed my sleep", description: "", tags: [], hashtags: [], language: "english",
  thumbnailText: "FIXED", thumbnailVisual: "", viewerPromise: "", whySuggested: "The primary recommendation.",
  approach: "direct", packageIntent: "", bestFor: "Search", misleadingRisk: "", qualityStatus: "",
  titleQualityScore: 7.4, source: "AI suggestion", mechanism: "", reason: "",
};

function json(body: unknown) {
  return { ok: true, status: 200, text: async () => JSON.stringify(body) };
}

let overview: Record<string, unknown>;

function renderStage(data: AnalyzeResponse | null = DATA, selected: PackageOption | null = null) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <DecisionStage data={data} selected={selected} selectionStatus="unrecorded" onExport={() => undefined} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  overview = {
    eligible: true,
    min_variants: 2,
    max_variants: 3,
    candidates: [{ package_id: "package-a", title: "How I fixed my sleep", thumbnail_text: "FIXED" }],
    similar_pairs: [],
    tests: [],
    note: "This app never runs it; its own before/after comparisons are not equivalent to YouTube's test.",
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => json(String(url) === "/api/history/runs/42/studio-tests" ? overview : {})),
  );
});

afterEach(() => vi.unstubAllGlobals());

describe("DecisionStage", () => {
  it("offers the YouTube Studio test before publishing, even before a package is chosen", async () => {
    renderStage();

    expect(screen.getByText("No decision to review yet")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "YouTube Studio test (Test & Compare)" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Copy title" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy thumbnail text" })).toBeInTheDocument();
  });

  it("shows one line for a Short", async () => {
    overview = { ...overview, eligible: false, reason: "YouTube's Test & Compare is not available for Shorts." };
    renderStage();

    expect(await screen.findByTestId("studio-shorts-note")).toHaveTextContent("not available for Shorts");
  });

  it("has nothing to prepare before a package is generated", () => {
    renderStage(null);
    expect(screen.queryByTestId("studio-test-panel")).not.toBeInTheDocument();
  });

  it("says the Opportunity Score is the same for every option and forecasts nothing", () => {
    renderStage(
      { ...DATA, opportunity_gap_analysis: { opportunity_score: { score: 48.3, label: "WORKABLE" } } },
      SELECTED,
    );

    expect(screen.getByText("Opportunity: 48 / 100. Title quality: 7.4 / 10.")).toBeInTheDocument();
    // The score has no title input, so it cannot tell the options apart.
    expect(screen.getByText(/the same for every package option/)).toBeInTheDocument();
    expect(screen.queryByText(/help compare packaging/)).not.toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(PREDICTION_CLAIM);
  });
});
