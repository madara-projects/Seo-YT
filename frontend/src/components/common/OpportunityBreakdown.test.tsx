import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { OpportunityBreakdownDisclosure, OpportunityWeightsNote } from "./OpportunityBreakdown";
import { parseOpportunityBreakdown } from "@/lib/opportunityFormat";
import { BREAKDOWN } from "@/test/fixtures/opportunity";

/** Wording that would present the heuristic as a forecast. "Not a prediction" is allowed. */
const PREDICTION_CLAIM = /(?<!not a )predict(s|ed|ion)? (of )?(views|reach|ctr)|expected views|will get \d|guarantee/i;

describe("OpportunityBreakdownDisclosure", () => {
  it("shows each input's value, weight, contribution and source next to the score", async () => {
    render(<OpportunityBreakdownDisclosure breakdown={parseOpportunityBreakdown(BREAKDOWN)} />);
    await userEvent.click(screen.getByRole("button", { name: /why this score/i }));

    const inputs = screen.getAllByTestId("opportunity-input");
    expect(inputs).toHaveLength(5);
    const [demandItem, competitionItem, keywordItem] = inputs as [HTMLElement, HTMLElement, HTMLElement];
    const demand = within(demandItem);
    expect(demand.getByText("Demand (view velocity)")).toBeInTheDocument();
    expect(demand.getByText("75 / 100 × 35% = 26.3 points")).toBeInTheDocument();
    expect(demand.getByText("Measured from YouTube results")).toBeInTheDocument();
    expect(within(keywordItem).getByText("Default: data missing")).toBeInTheDocument();
    expect(within(competitionItem).getByText("Local heuristic")).toBeInTheDocument();
    expect(screen.getByText("Total: 48.3 / 100")).toBeInTheDocument();
  });

  it("lists missing data and the input confidence", async () => {
    render(<OpportunityBreakdownDisclosure breakdown={parseOpportunityBreakdown(BREAKDOWN)} />);
    await userEvent.click(screen.getByRole("button", { name: /why this score/i }));

    expect(screen.getByText("Medium input confidence")).toBeInTheDocument();
    expect(screen.getByText(/not how likely the video is to get views/)).toBeInTheDocument();
    const missing = within(screen.getByRole("list", { name: "Missing data" }));
    expect(missing.getAllByRole("listitem")).toHaveLength(2);
    expect(missing.getByText(/No keywords were extracted/)).toBeInTheDocument();
  });

  it("says the score is a heuristic and never claims a prediction", async () => {
    const { container } = render(<OpportunityBreakdownDisclosure breakdown={parseOpportunityBreakdown(BREAKDOWN)} />);
    await userEvent.click(screen.getByRole("button", { name: /why this score/i }));

    expect(screen.getByText(/It is not a prediction of views, reach or click-through rate/)).toBeInTheDocument();
    expect(container.textContent).not.toMatch(PREDICTION_CLAIM);
  });

  it("says an older package stored no breakdown instead of guessing", async () => {
    render(<OpportunityBreakdownDisclosure breakdown={null} />);
    await userEvent.click(screen.getByRole("button", { name: /why this score/i }));

    expect(screen.getByText(/saved before score breakdowns were stored/)).toBeInTheDocument();
    expect(screen.queryByTestId("opportunity-input")).not.toBeInTheDocument();
  });

  it("explains an unmeasured score without a total", async () => {
    const unmeasured = parseOpportunityBreakdown({
      ...BREAKDOWN,
      score: null,
      confidence: "none",
      warnings: ["No competitor results were available, so demand and competition could not be measured."],
    });
    render(<OpportunityBreakdownDisclosure breakdown={unmeasured} />);
    await userEvent.click(screen.getByRole("button", { name: /why this score/i }));

    expect(screen.getByText(/No competitor results were available/)).toBeInTheDocument();
    expect(screen.getByText("No input confidence")).toBeInTheDocument();
    expect(screen.queryByText(/^Total:/)).not.toBeInTheDocument();
    expect(screen.queryByTestId("opportunity-input")).not.toBeInTheDocument();
  });
});

describe("OpportunityWeightsNote", () => {
  it("names the five inputs an average is built from", async () => {
    const { container } = render(<OpportunityWeightsNote />);
    await userEvent.click(screen.getByRole("button", { name: /what it averages/i }));

    expect(screen.getAllByRole("listitem")).toHaveLength(5);
    expect(screen.getByText("Demand (view velocity)")).toBeInTheDocument();
    expect(screen.getByText("35%")).toBeInTheDocument();
    expect(container.textContent).toMatch(/not a prediction of views/);
    expect(container.textContent).not.toMatch(PREDICTION_CLAIM);
  });
});
