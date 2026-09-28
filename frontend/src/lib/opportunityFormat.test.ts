import { describe, expect, it } from "vitest";
import {
  OPPORTUNITY_INPUT_WEIGHTS,
  averageHeuristicCaption,
  calibrationStatus,
  parseOpportunityBreakdown,
  sourceLabel,
  weightText,
} from "./opportunityFormat";
import { BREAKDOWN } from "@/test/fixtures/opportunity";

describe("parseOpportunityBreakdown", () => {
  it("reads a stored breakdown", () => {
    const parsed = parseOpportunityBreakdown(BREAKDOWN);
    expect(parsed?.inputs).toHaveLength(5);
    expect(parsed?.score).toBe(48.34);
    expect(parsed?.warnings).toHaveLength(2);
    expect(parsed?.confidence).toBe("medium");
  });

  it("returns null when there is no breakdown, so older packages say so instead of guessing", () => {
    expect(parseOpportunityBreakdown(undefined)).toBeNull();
    expect(parseOpportunityBreakdown({})).toBeNull();
    expect(parseOpportunityBreakdown({ inputs: [] })).toBeNull();
    expect(parseOpportunityBreakdown("breakdown")).toBeNull();
  });

  it("drops malformed inputs and keeps an unmeasured score as null", () => {
    const parsed = parseOpportunityBreakdown({ ...BREAKDOWN, score: null, inputs: [...BREAKDOWN.inputs, { key: "x" }] });
    expect(parsed?.inputs).toHaveLength(5);
    expect(parsed?.score).toBeNull();
  });

  it("always carries the heuristic statement", () => {
    expect(parseOpportunityBreakdown({ ...BREAKDOWN, statement: "" })?.statement).toMatch(/not a prediction of views/);
  });
});

describe("wording", () => {
  it("labels where each input came from", () => {
    expect(sourceLabel("youtube_measured").label).toBe("Measured from YouTube results");
    expect(sourceLabel("local_heuristic").label).toBe("Local heuristic");
    expect(sourceLabel("missing_default").label).toBe("Default: data missing");
  });

  it("prints weights as percentages that add to 100", () => {
    expect(weightText(0.35)).toBe("35%");
    expect(OPPORTUNITY_INPUT_WEIGHTS.reduce((sum, item) => sum + item.weight, 0)).toBeCloseTo(1);
  });

  it("says the Dashboard averages a heuristic, not a prediction", () => {
    expect(averageHeuristicCaption(3)).toBe(
      "Averages a local heuristic, not a prediction of views. Calculated from your 3 saved analyses.",
    );
  });

  it("names every calibration verdict as an association", () => {
    expect(calibrationStatus("insufficient_evidence").label).toBe("Not enough evidence yet");
    expect(calibrationStatus("higher_scores_did_better").label).toBe("Higher scores did better");
    expect(calibrationStatus("lower_scores_did_better").tone).toBe("bad");
    expect(calibrationStatus("something_else").label).toBe("Unavailable");
  });
});
