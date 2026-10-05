import { describe, expect, it } from "vitest";
import {
  buildPackageOptions,
  cleanHashtags,
  cleanTags,
  copyValue,
  hashtagsText,
  researchHasEvidence,
  tagsText,
  titleScore,
  uploadBundleText,
} from "./packages";
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

  it("copies tags as one line with no comma inside any tag, whatever the generator sent", () => {
    // Two published videos ended up with "deep quotes," as a tag: the comma
    // travelled inside the tag text, and YouTube splits a paste on commas only.
    const dirty = buildPackageOptions(
      baseResponse({
        tags: ["deep quotes,", " life quotes, ", "Deep Quotes", "quotes\nabout life,", "", "“wisdom”"],
        hashtags: ["#one,", "two", "#one", "#three #four", "#five\n"],
      }),
    )[0]!;

    expect(copyValue(dirty, "tags")).toBe("deep quotes, life quotes, quotes, about life, wisdom");
    expect(copyValue(dirty, "tags")).not.toMatch(/,\s*$|\n|,,/);
    expect(copyValue(dirty, "hashtags")).toBe("#one #two #three #four #five");
    // What is shown is what is copied, so the count on screen is the count pasted.
    expect(dirty.tags).toEqual(["deep quotes", "life quotes", "quotes", "about life", "wisdom"]);
    expect(dirty.hashtags).toEqual(["#one", "#two", "#three", "#four", "#five"]);
  });

  it("returns an empty string for a missing option", () => {
    expect(copyValue(null, "title")).toBe("");
  });
});

describe("tag text for YouTube Studio", () => {
  it("joins clean tags with a comma and a space, and never ends with a comma", () => {
    expect(tagsText(["alpha", "beta"])).toBe("alpha, beta");
    expect(tagsText(["alpha,", "beta,"])).toBe("alpha, beta");
    expect(tagsText(["alpha"])).toBe("alpha");
  });

  it("splits a list the generator sent as one string, on commas or line breaks", () => {
    expect(cleanTags(["deep quotes, life quotes,quotes"])).toEqual(["deep quotes", "life quotes", "quotes"]);
    expect(cleanTags(["deep quotes\nlife quotes\r\n"])).toEqual(["deep quotes", "life quotes"]);
  });

  it("keeps each tag's own spelling and drops only exact repeats", () => {
    expect(cleanTags(["Deep Quotes", "deep quotes", "deep  quotes"])).toEqual(["Deep Quotes"]);
  });

  it("is empty, not a crash, for anything that is not a list", () => {
    expect(tagsText(undefined)).toBe("");
    expect(tagsText("alpha, beta")).toBe("");
    expect(cleanTags([null, 7, ""])).toEqual(["7"]);
  });

  it("drops a hashtag's # from a tag and splits on semicolons and bars too", () => {
    // YouTube's tag box takes the "#" as part of the tag.
    expect(cleanTags(["#deep quotes", "##life", "＃trust"])).toEqual(["deep quotes", "life", "trust"]);
    expect(cleanTags(["deep quotes; life quotes|quotes", "“#love”"])).toEqual(["deep quotes", "life quotes", "quotes", "love"]);
    expect(cleanTags(["#", " ; | "])).toEqual([]);
  });

  it("writes one hashtag per word with a single leading hash", () => {
    expect(hashtagsText(["#shorts", "quotes", "##life", "#shorts"])).toBe("#shorts #quotes #life");
    expect(cleanHashtags(["#a, #b", "#c\n#d."])).toEqual(["#a", "#b", "#c", "#d"]);
    expect(hashtagsText([])).toBe("");
  });

  it("joins a multi-word hashtag into one, as the backend does, rather than splitting it", () => {
    // A hashtag ends at the first space: "#cold brew" would publish as #cold and a stray "brew".
    expect(cleanHashtags(["#cold brew", "life lessons."])).toEqual(["#ColdBrew", "#LifeLessons"]);
    // Inner capitals and a single word keep their spelling; a repeat in another spelling is dropped.
    expect(cleanHashtags(["#iPhone tips", "#shorts", "#ColdBrew", "cold brew"])).toEqual(["#iPhoneTips", "#shorts", "#ColdBrew"]);
    // Hashtags sent as one string still come apart at each "#".
    expect(cleanHashtags(["#shorts #quotes #life"])).toEqual(["#shorts", "#quotes", "#life"]);
  });

  it("puts the same clean lines in the upload bundle", () => {
    const lines = uploadBundleText({ title: "T", tags: ["a,", "b\nc"], hashtags: ["#x,", "y"] }).split("\n");
    expect(lines[lines.indexOf("TAGS") + 1]).toBe("a, b, c");
    expect(lines[lines.indexOf("HASHTAGS") + 1]).toBe("#x #y");
    expect(lines.filter((line) => /,\s*$/.test(line))).toEqual([]);
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
