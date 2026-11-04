import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { LearningPanel } from "./DashboardSections";
import { patternSignalText } from "@/lib/dashboardFormat";
import type { CohortLearning } from "@/api/historyTypes";

function renderPanel(data: CohortLearning | undefined) {
  return render(
    <MemoryRouter>
      <LearningPanel
        title="Learning confidence"
        description="Learning from results starts only once enough comparable videos have matured."
        sampleLabel="Comparable videos"
        data={data}
        isPending={false}
        isError={false}
      />
    </MemoryRouter>,
  );
}

// Fourteen Shorts in English and nine long-form videos in Hindi: 23 pooled,
// which the old panel showed as one "Large sample" with a green chip.
const MIXED: CohortLearning = {
  format: "all",
  language: "all",
  sample_size: 23,
  confidence_label: "Large sample (20+ videos)",
  learning_allowed: true,
  next_threshold: null,
  recommendation: "Large sample (20+ videos): use this format / language 24h cohort as a cautious comparison baseline.",
  cohort_scope: "mixed",
  cohorts: [
    {
      format: "long_form",
      language: "hindi",
      sample_size: 9,
      confidence_label: "Early signal (5+ videos)",
      learning_allowed: true,
      next_threshold: 10,
      recommendation: "Early signal (5+ videos): use this long_form / hindi 24h cohort as a cautious comparison baseline.",
    },
    {
      format: "youtube_shorts",
      language: "english",
      sample_size: 14,
      confidence_label: "Moderate sample (10+ videos)",
      learning_allowed: true,
      next_threshold: 20,
      recommendation: "Moderate sample (10+ videos): use this youtube_shorts / english 24h cohort as a cautious comparison baseline.",
      pattern_signal: {
        status: "no_pattern",
        reason: "the leading three videos' median views per day (130) is within 25% of the rest's (120), a spread noise explains.",
      },
    },
  ],
};

describe("LearningPanel", () => {
  it("never presents a mixed pool as one comparable cohort", () => {
    renderPanel(MIXED);
    // No green chip, and the pooled tier is not shown as the cohort's.
    expect(screen.getByText("Mixed formats or languages")).toBeInTheDocument();
    expect(screen.queryByText("Large sample (20+ videos)")).not.toBeInTheDocument();
    expect(screen.queryByText("23")).not.toBeInTheDocument();
    expect(screen.queryByText(/use this format \/ language/)).not.toBeInTheDocument();

    // The largest cohort leads, with its scope named.
    expect(screen.getByText("14")).toBeInTheDocument();
    // Its next tier, not the pool's: the pool has no tier of its own.
    expect(screen.getByText("Needed for the next sample size").previousElementSibling).toHaveTextContent("20");
    expect(screen.getByText("Comparable videos · YouTube Short · English, the largest cohort")).toBeInTheDocument();
    expect(screen.getAllByText("Moderate sample (10+ videos)").length).toBeGreaterThan(0);
    // The recommendation is the leading cohort's, not the pool's, and names it.
    expect(screen.getByTestId("learning-recommendation")).toHaveTextContent(
      "YouTube Short · English: Moderate sample (10+ videos): use this youtube_shorts / english 24h cohort",
    );

    // Every cohort is listed with its own count, largest first.
    const list = within(screen.getByTestId("learning-cohorts")).getAllByRole("listitem");
    expect(list.map((item) => item.textContent)).toEqual([
      "YouTube Short · English: 14 videos · Moderate sample (10+ videos) · No pattern",
      "Long-form · Hindi: 9 videos · Early signal (5+ videos)",
    ]);

    // Whether a pattern exists is said apart from the sample-size label.
    expect(screen.getByTestId("learning-pattern")).toHaveTextContent(
      "No pattern: the leading three videos' median views per day (130) is within 25% of the rest's (120)",
    );
  });

  it("does not call a cohort the largest when another is the same size", () => {
    const longForm = MIXED.cohorts?.[0] as CohortLearning;
    const shorts = MIXED.cohorts?.[1] as CohortLearning;
    renderPanel({ ...MIXED, cohorts: [shorts, { ...longForm, sample_size: 14 }] });
    expect(
      screen.getByText("Comparable videos · YouTube Short · English, one of the largest cohorts"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/, the largest cohort/)).not.toBeInTheDocument();
  });

  it("names a mixed pool even when the per-cohort counts are missing", () => {
    renderPanel({ ...MIXED, cohorts: undefined });
    expect(screen.getByText("Mixed formats or languages")).toBeInTheDocument();
    expect(screen.getByText("The per-format and language counts are unavailable.")).toBeInTheDocument();
    expect(screen.queryByText("23")).not.toBeInTheDocument();
    expect(screen.queryByText("Large sample (20+ videos)")).not.toBeInTheDocument();
  });

  it("keeps a single cohort as before, with the sample-size label and its pattern", () => {
    renderPanel({
      format: "youtube_shorts",
      language: "english",
      sample_size: 12,
      confidence_label: "Moderate sample (10+ videos)",
      learning_allowed: true,
      next_threshold: 20,
      cohort_scope: "single",
      pattern_signal: { status: "insufficient_sample", reason: "a leading group needs 10 comparable videos to stand apart from noise; there are 9." },
    });
    expect(screen.getByText("Moderate sample (10+ videos)")).toBeInTheDocument();
    expect(screen.queryByTestId("learning-cohorts")).not.toBeInTheDocument();
    expect(screen.getByText("Comparable videos")).toBeInTheDocument();
    expect(screen.getByText("Needed for the next sample size")).toBeInTheDocument();
    expect(screen.getByTestId("learning-pattern")).toHaveTextContent("No pattern yet: a leading group needs 10");
  });

  it("shows no pattern line when the payload has no pattern_signal", () => {
    renderPanel({ sample_size: 3, confidence_label: "Collecting evidence", learning_allowed: false, next_threshold: 5 });
    expect(screen.getByText("Collecting evidence")).toBeInTheDocument();
    expect(screen.queryByTestId("learning-pattern")).not.toBeInTheDocument();
  });
});

describe("patternSignalText", () => {
  it("words each status apart from sample size", () => {
    expect(patternSignalText(null)).toBeNull();
    expect(patternSignalText({ reason: "no status" })).toBeNull();
    expect(patternSignalText({ status: "pattern", reason: "the leading three beat the rest by 40%." })).toBe(
      "Pattern found: the leading three beat the rest by 40%.",
    );
    expect(
      patternSignalText({
        status: "mixed_cohort",
        reason: "a mixed cohort: the linked videos span more than one format or language, so their outcomes are not compared.",
      }),
    ).toBe(
      "No pattern is read from a mixed cohort: the linked videos span more than one format or language, so their outcomes are not compared.",
    );
    expect(patternSignalText({ status: "no_pattern" })).toBe("No pattern.");
    // A status this build does not know is never worded as a found pattern.
    expect(patternSignalText({ status: "new_status", reason: "a reason." })).toBe("Pattern signal: a reason.");
  });
});
