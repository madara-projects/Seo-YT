import { describe, expect, it } from "vitest";
import { researchEvidence } from "./researchEvidence";

describe("research evidence accounting", () => {
  it("distinguishes retrieved videos from rejected results", () => {
    const result = researchEvidence({ youtube_results: [], keyword_research: { diagnostics: { youtube_results_unique: 150 } } });
    expect(result.summary).toBe("150 unique videos retrieved; 0 passed relevance checks.");
  });
  it("keeps legacy retrieval counts unknown", () => {
    expect(researchEvidence({ youtube_results: [] }).retrieved).toBeNull();
    expect(researchEvidence({ youtube_results: [] }).summary).toContain("retrieval count was not recorded");
  });
});
