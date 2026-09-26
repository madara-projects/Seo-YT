import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { KeywordResearchPanel } from "./KeywordResearchPanel";
import type { KeywordResearch } from "@/api/types";

// Shaped like `keyword_research` after `select_final_tags`.
const RESEARCH: KeywordResearch = {
  status: "youtube_evidence",
  confidence: "observed_youtube_relevance",
  search_volume_available: false,
  selected_keywords: [
    { keyword: "silence hurts", classification: "topic", evidence_count: 3 },
    { keyword: "unsaid words", classification: "emotion", evidence_count: 0 },
    { keyword: "shorts", classification: "platform_format", evidence_count: 9 },
  ],
};

describe("KeywordResearchPanel", () => {
  it("counts subject tags with YouTube support apart from source-only ones", () => {
    render(<KeywordResearchPanel research={RESEARCH} />);

    const panel = screen.getByTestId("keyword-research");
    expect(within(panel).getByText("YouTube evidence")).toHaveClass("text-tone-ok");
    // The format tag is neither: it says nothing about the subject.
    expect(
      within(panel).getByText(/1 subject tag matches sampled public result metadata; 1 is source-only\./),
    ).toBeInTheDocument();
    expect(within(panel).getByText("Search volume: unavailable.")).toBeInTheDocument();
    expect(within(panel).getByText("Matched 3 sampled results")).toBeInTheDocument();
    expect(within(panel).getByText("From the script only")).toBeInTheDocument();
    expect(within(panel).getByText("Format tag")).toBeInTheDocument();
  });

  it("marks tags chosen without YouTube research as limited", () => {
    render(
      <KeywordResearchPanel
        research={{
          status: "semantic_only",
          confidence: "limited_without_youtube_research",
          selected_keywords: [{ keyword: "unsaid words", classification: "topic", evidence_count: 0 }],
        }}
      />,
    );

    const panel = screen.getByTestId("keyword-research");
    expect(within(panel).getByText("Script only")).toHaveClass("text-tone-warn");
    expect(within(panel).getByText(/0 subject tags match sampled public result metadata; 1 is source-only\./)).toBeInTheDocument();
    expect(within(panel).getByText(/because YouTube research was limited/)).toBeInTheDocument();
  });

  it("says so when a run has no tag research", () => {
    render(<KeywordResearchPanel research={undefined} />);

    expect(screen.getByText("Tag research wasn't returned for this run.")).toBeInTheDocument();
    expect(screen.queryByText(/subject tag/)).not.toBeInTheDocument();
  });
});
