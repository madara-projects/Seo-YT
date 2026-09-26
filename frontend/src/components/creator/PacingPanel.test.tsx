import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { PacingPanel } from "./PacingPanel";

/** The value shown under a field's label. */
function field(panel: HTMLElement, label: string) {
  return within(panel).getByText(label).nextElementSibling;
}

describe("PacingPanel", () => {
  it("reads a spoken script's pace as a heuristic", () => {
    render(
      <PacingPanel
        pacing={{
          analysis_type: "spoken_script",
          pace_label: "balanced",
          avg_sentence_length: 17.25,
          hook_density: "medium",
          recommendation: "Pacing is balanced. Keep the opening hook tight.",
        }}
      />,
    );

    const panel = screen.getByTestId("pacing-analysis");
    expect(within(panel).getByRole("heading", { name: "Script pacing" })).toBeInTheDocument();
    expect(within(panel).getByText("Local heuristic")).toHaveClass("text-tone-warn");
    expect(field(panel, "Pacing assessment")).toHaveTextContent("Balanced");
    expect(field(panel, "Avg sentence length")).toHaveTextContent(`${(17.3).toLocaleString()} words`);
    expect(field(panel, "Hook density")).toHaveTextContent("Medium");
    expect(within(panel).getByText("Pacing is balanced. Keep the opening hook tight.")).toBeInTheDocument();
  });

  it("names a quote Short's readings for what they measure", () => {
    render(
      <PacingPanel
        pacing={{
          analysis_type: "quote_short",
          pace_label: "reflective",
          avg_sentence_length: 12,
          hook_density: "single emotional hook",
          recommendation: "Show the quote within the first second.",
        }}
      />,
    );

    const panel = screen.getByTestId("pacing-analysis");
    expect(within(panel).getByRole("heading", { name: "Quote Short pacing" })).toBeInTheDocument();
    expect(field(panel, "Format assessment")).toHaveTextContent("Reflective");
    expect(field(panel, "Quote length")).toHaveTextContent("12 words");
    expect(field(panel, "Hook structure")).toHaveTextContent("Single emotional hook");
    expect(within(panel).queryByText("Avg sentence length")).not.toBeInTheDocument();
  });

  it("shows an unmeasured script as unavailable, not as zero", () => {
    render(
      <PacingPanel
        pacing={{ analysis_type: "spoken_script", pace_label: "unknown", avg_sentence_length: 0, hook_density: "low" }}
      />,
    );

    const panel = screen.getByTestId("pacing-analysis");
    expect(field(panel, "Pacing assessment")).toHaveTextContent("Unavailable");
    expect(field(panel, "Avg sentence length")).toHaveTextContent("Unavailable");
    expect(field(panel, "Hook density")).toHaveTextContent("Unavailable");
    expect(within(panel).queryByText(/0 words/)).not.toBeInTheDocument();
    expect(within(panel).getByText("No pacing recommendation was returned.")).toBeInTheDocument();
  });

  it("says so when a run has no pacing analysis", () => {
    render(<PacingPanel pacing={undefined} />);

    expect(screen.getByText("No pacing analysis was returned for this run.")).toBeInTheDocument();
  });
});
