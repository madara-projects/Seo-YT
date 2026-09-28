import { describe, expect, it } from "vitest";
import { render, within } from "@testing-library/react";
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
    expect(card.getByText("Local heuristic, not a prediction of views.")).toBeInTheDocument();
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
