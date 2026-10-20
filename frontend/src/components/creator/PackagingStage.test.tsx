import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PackagingStage } from "./PackagingStage";
import { BREAKDOWN } from "@/test/fixtures/opportunity";
import type { AnalyzeResponse, PackageOption } from "@/api/types";

const PREDICTION_CLAIM = /(?<!not a )predict(s|ed|ion)? (of )?(views|reach|ctr)|expected views|will get \d|guarantee/i;

const OPTION: PackageOption = {
  id: "package-a", packageId: "package-a", label: "Package A", primary: true,
  title: "Cold Brew Coffee at Home With Just a Mason Jar", description: "Make cold brew at home.",
  tags: ["cold brew"], hashtags: ["#ColdBrew"], language: "english", thumbnailText: "COLD BREW",
  thumbnailVisual: "A mason jar", viewerPromise: "Smooth coffee", whySuggested: "", approach: "",
  packageIntent: "", bestFor: "", misleadingRisk: "", qualityStatus: "", titleQualityScore: 7.4,
  source: "Generated", mechanism: "", reason: "",
};

function renderStage(opportunityScore: Record<string, unknown>) {
  const data = { opportunity_gap_analysis: { opportunity_score: opportunityScore } } as AnalyzeResponse;
  return render(
    <PackagingStage data={data} options={[OPTION]} chosen={null} selectionStatus="unrecorded" onSelect={() => undefined} />,
  );
}

function opportunityCard() {
  const card = document.querySelector<HTMLElement>('[data-stat="Opportunity score"]');
  if (!card) throw new Error("No opportunity card");
  return card;
}

describe("PackagingStage opportunity score", () => {
  it("shows the five inputs, missing data and confidence next to the score", async () => {
    renderStage({ score: 48.34, label: "WORKABLE", breakdown: BREAKDOWN });
    const card = within(opportunityCard());

    expect(card.getByText("48 / 100")).toBeInTheDocument();
    expect(card.getByText("Medium input confidence")).toBeInTheDocument();
    // The score has no title input: it is one figure for the run, not one per option.
    expect(
      card.getByText("Local heuristic for this run's research, the same for every option. Not a prediction of views."),
    ).toBeInTheDocument();
    await userEvent.click(card.getByRole("button", { name: /why this score/i }));
    expect(card.getAllByTestId("opportunity-input")).toHaveLength(5);
    expect(card.getByRole("list", { name: "Missing data" })).toBeInTheDocument();
    expect(opportunityCard().textContent).not.toMatch(PREDICTION_CLAIM);
  });

  it("explains an unmeasured score", async () => {
    renderStage({
      score: null, label: "UNMEASURED",
      breakdown: { ...BREAKDOWN, score: null, confidence: "none", warnings: ["No competitor results were available."] },
    });
    const card = within(opportunityCard());

    // The value and its source chip both say so; no "0 / 100".
    expect(card.getAllByText("Unavailable")).toHaveLength(2);
    expect(card.getByText("No input confidence")).toBeInTheDocument();
    await userEvent.click(card.getByRole("button", { name: /why this score/i }));
    expect(card.getByText("No competitor results were available.")).toBeInTheDocument();
  });
});

function renderWithQuality(generation_quality: AnalyzeResponse["generation_quality"]) {
  const data = { generation_quality } as AnalyzeResponse;
  return render(
    <PackagingStage data={data} options={[OPTION]} chosen={null} selectionStatus="unrecorded" onSelect={() => undefined} />,
  );
}

describe("PackagingStage quality verdict", () => {
  it("shows a RED verdict with its reasons above the copy controls, which stay but are marked", () => {
    renderWithQuality({
      status: "fail",
      passed: false,
      verdict: "RED",
      issues: [
        { code: "no_acceptable_title", field: "titles", severity: "error", message: "No title candidate passed the local quality gate." },
      ],
      warnings: [],
    });
    const banner = within(screen.getByRole("alert", { name: "Package quality verdict" }));
    expect(banner.getByText("Failed quality check")).toBeInTheDocument();
    expect(banner.getByText(/not ready to upload/)).toBeInTheDocument();
    expect(banner.getByText("No title candidate passed the local quality gate.")).toBeInTheDocument();

    const card = within(screen.getByTestId("package-card"));
    expect(card.getByText("Not upload-ready")).toBeInTheDocument();
    expect(card.getByText(/fix the notes above before copying/)).toBeInTheDocument();
    expect(card.getByRole("button", { name: /copy all/i })).toBeInTheDocument();
  });

  it("shows a YELLOW verdict's warnings, which the per-title status does not carry", () => {
    renderWithQuality({
      status: "pass",
      passed: true,
      verdict: "YELLOW",
      issues: [],
      warnings: ["Only 2 materially distinct title alternative(s) passed; the result was not padded."],
    });
    const banner = within(screen.getByRole("status", { name: "Package quality verdict" }));
    expect(banner.getByText("Quality check: review warnings")).toBeInTheDocument();
    expect(banner.getByText(/Only 2 materially distinct title alternative/)).toBeInTheDocument();
    expect(screen.queryByText("Not upload-ready")).not.toBeInTheDocument();
  });

  it("never reads a missing verdict as a pass, and treats a failed status without one as RED", () => {
    const { unmount } = renderWithQuality(undefined);
    expect(screen.getByRole("status", { name: "Package quality verdict" })).toHaveTextContent("Quality not checked");
    unmount();

    renderWithQuality({ status: "fail", passed: false, issues: ["Description is empty."] });
    expect(screen.getByRole("alert", { name: "Package quality verdict" })).toHaveTextContent("Failed quality check");
  });
});
