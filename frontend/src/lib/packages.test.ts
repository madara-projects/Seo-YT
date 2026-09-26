import { describe, expect, it } from "vitest";
import { buildPackageOptions, copyValue, researchHasEvidence, titleScore } from "./packages";
import type { AnalyzeResponse } from "@/api/types";

function baseResponse(overrides: Partial<AnalyzeResponse> = {}): AnalyzeResponse {
  return {
    title: "Primary title",
    description: "A description.",
    tags: ["alpha", "beta"],
    hashtags: ["#one", "#two"],
    generation_source: "gemini",
    ...overrides,
  };
}

describe("buildPackageOptions", () => {
  it("puts the primary title first and labels it", () => {
    const options = buildPackageOptions(baseResponse());
    expect(options).toHaveLength(1);
    expect(options[0]).toMatchObject({ label: "Package A", title: "Primary title", primary: true });
  });

  it("de-duplicates titles case-insensitively", () => {
    const options = buildPackageOptions(
      baseResponse({ title_variants: ["PRIMARY TITLE", "Second title"] }),
    );
    expect(options.map((option) => option.title)).toEqual(["Primary title", "Second title"]);
  });

  it("caps the option list at five", () => {
    const options = buildPackageOptions(
      baseResponse({ title_variants: ["a", "b", "c", "d", "e", "f", "g"] }),
    );
    expect(options).toHaveLength(5);
  });

  it("skips blank titles instead of creating an empty option", () => {
    const options = buildPackageOptions(baseResponse({ title_variants: ["", "   ", "Real"] }));
    expect(options.map((option) => option.title)).toEqual(["Primary title", "Real"]);
  });

  it("prefers the requested language package over top-level fields", () => {
    const options = buildPackageOptions(
      baseResponse({
        multilang: {
          tamil: { title: "Tamil title", description: "Tamil description", tags: ["t1"] },
        },
      }),
      { language: "tamil" },
    );
    expect(options[0]?.title).toBe("Tamil title");
    expect(options[0]?.description).toBe("Tamil description");
  });

  it("resolves language 'auto' to the spoken video language", () => {
    const options = buildPackageOptions(
      baseResponse({ multilang: { tamil: { title: "Tamil title" } } }),
      { language: "auto", video_language: "tamil" },
    );
    expect(options[0]?.title).toBe("Tamil title");
  });

  it("shares one metadata bundle across options, as the API returns it", () => {
    const options = buildPackageOptions(baseResponse({ title_variants: ["Second"] }));
    expect(options[1]?.description).toBe(options[0]?.description);
    expect(options[1]?.tags).toEqual(options[0]?.tags);
  });

  it("labels the source by generator", () => {
    expect(buildPackageOptions(baseResponse())[0]?.source).toBe("AI suggestion");
    expect(
      buildPackageOptions(baseResponse({ generation_source: "fallback" }))[0]?.source,
    ).toBe("Generated suggestion");
  });

  it("carries rich package metadata through when present", () => {
    const options = buildPackageOptions(
      baseResponse({
        title_thumbnail_packages: [
          {
            package_id: "pkg-real",
            title: "Primary title",
            thumbnail_text: "BIG TEXT",
            best_for: "Search",
            misleading_risk: "low",
          },
        ],
      }),
    );
    expect(options[0]).toMatchObject({
      id: "pkg-real",
      packageId: "pkg-real",
      thumbnailText: "BIG TEXT",
      bestFor: "Search",
      misleadingRisk: "low",
    });
  });

  it("never gives a title-only option a server package ID", () => {
    // "Match the video language": the primary is the Tamil title, which is not
    // one of the saved packages, while package-a is the English one.
    const options = buildPackageOptions(
      baseResponse({
        multilang: { tamil: { title: "Tamil title" } },
        title_thumbnail_packages: [{ package_id: "package-a", title: "English title" }],
        title_variants: ["A plain variant"],
      }),
      { language: "auto", video_language: "tamil" },
    );
    expect(options.map((option) => [option.title, option.packageId])).toEqual([
      ["Tamil title", null],
      ["English title", "package-a"],
      ["A plain variant", null],
    ]);
    expect(new Set(options.map((option) => option.id)).size).toBe(options.length);
    expect(options.filter((option) => option.id === "package-a")).toHaveLength(1);
  });

  it("mirrors the server's positional IDs for packages saved without one", () => {
    const options = buildPackageOptions(
      baseResponse({
        title_thumbnail_packages: [{ title: "Primary title" }, { title: "Second package" }],
      }),
    );
    expect(options.map((option) => option.packageId)).toEqual(["package-a", "package-b"]);
    expect(options[0]?.primary).toBe(true);
  });

  it("does not claim a quality check that never ran", () => {
    const [option] = buildPackageOptions(baseResponse());
    expect(option).toMatchObject({ misleadingRisk: "not evaluated", qualityStatus: "not evaluated" });
  });
});

describe("titleScore", () => {
  it("returns the scored variant when the title matches", () => {
    const data = baseResponse({
      title_optimization: { scored_variants: [{ title: "Primary title", score: 8.5 }] },
    });
    expect(titleScore(data, "Primary title")).toBe(8.5);
  });

  it("falls back to the CTR quality score for the primary title", () => {
    const data = baseResponse({ ctr_prediction: { title_quality_score: 7 } });
    expect(titleScore(data, "Primary title")).toBe(7);
  });

  it("returns null rather than zero when unscored", () => {
    expect(titleScore(baseResponse(), "Unknown title")).toBeNull();
  });
});

describe("copyValue", () => {
  const option = buildPackageOptions(baseResponse())[0]!;

  it("joins tags with commas and hashtags with spaces", () => {
    expect(copyValue(option, "tags")).toBe("alpha, beta");
    expect(copyValue(option, "hashtags")).toBe("#one #two");
  });

  it("builds a labelled upload bundle", () => {
    const text = copyValue(option, "upload-package");
    expect(text).toContain("TITLE\nPrimary title");
    expect(text).toContain("DESCRIPTION\nA description.");
    expect(text).toContain("HASHTAGS\n#one #two");
  });

  it("returns an empty string for a missing option", () => {
    expect(copyValue(null, "title")).toBe("");
  });
});

describe("researchHasEvidence", () => {
  it("is false for an empty or missing payload", () => {
    expect(researchHasEvidence(null)).toBe(false);
    expect(researchHasEvidence(baseResponse())).toBe(false);
  });

  it("is true when any evidence array is populated", () => {
    expect(researchHasEvidence(baseResponse({ youtube_results: [{ title: "x" }] }))).toBe(true);
    expect(researchHasEvidence(baseResponse({ keyword_signals: [{ keyword: "x" }] }))).toBe(true);
  });
});
