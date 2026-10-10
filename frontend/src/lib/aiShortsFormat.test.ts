import { describe, expect, it } from "vitest";
import {
  AI_SHORTS_LANGUAGE_OPTIONS,
  allPromptsText,
  flowModeLabel,
  partsLabel,
  qualityNotes,
  quoteBlocker,
  quoteExcerpt,
  shotHeading,
  sourceChip,
  titleOptions,
  verdictChip,
} from "./aiShortsFormat";
import { AI_SHORTS_PLAN } from "@/test/fixtures/aiShorts";

describe("quoteBlocker", () => {
  it("asks for the quote first", () => {
    expect(quoteBlocker({ quote: "", moodHint: "" })).toBe("Type the quote first.");
    expect(quoteBlocker({ quote: "   ", moodHint: "" })).toBe("Type the quote first.");
  });

  it("mirrors the backend's 6–400 character limits on the trimmed quote", () => {
    expect(quoteBlocker({ quote: "Short", moodHint: "" })).toBe("The quote needs at least 6 characters.");
    expect(quoteBlocker({ quote: "  Enough  ", moodHint: "" })).toBeNull();
    expect(quoteBlocker({ quote: "x".repeat(400), moodHint: "" })).toBeNull();
    expect(quoteBlocker({ quote: "x".repeat(401), moodHint: "" })).toBe("Shorten the quote to 400 characters or fewer.");
  });

  it("caps the mood wish at 200 characters", () => {
    expect(quoteBlocker({ quote: "Silence says everything.", moodHint: "m".repeat(201) })).toMatch(/mood or scene wish to 200/);
  });
});

describe("labels", () => {
  it("names the parts and their length", () => {
    expect(partsLabel(1)).toBe("1 part · 8 s");
    expect(partsLabel(2)).toBe("2 parts · 16 s");
    // A saved plan reports its own total, which wins over the arithmetic.
    expect(partsLabel(3, 24)).toBe("3 parts · 24 s");
  });

  it("shows a dash, never \"null s\", when a saved plan's total is unknown", () => {
    // The list reads the total from the stored plan, which is null when that JSON is damaged.
    expect(partsLabel(2, null)).toBe("2 parts · —");
    expect(partsLabel(2, Number.NaN)).toBe("2 parts · —");
  });

  it("says how each part is made in Flow", () => {
    expect(flowModeLabel({ part: 1, flow_mode: "text_to_video" })).toBe("Text to Video");
    expect(flowModeLabel({ part: 2, flow_mode: "extend" })).toBe("Extend from Part 1");
    expect(flowModeLabel({ part: 1 })).toBe("Text to Video");
    expect(shotHeading(AI_SHORTS_PLAN.shots[1]!)).toBe("Part 2 · 8 s · Extend from Part 1");
  });

  it("labels every prompt by part when copying them together", () => {
    const text = allPromptsText(AI_SHORTS_PLAN.shots);
    expect(text.startsWith("PART 1 · 8 S · TEXT TO VIDEO\n")).toBe(true);
    expect(text).toContain("\n\nPART 2 · 8 S · EXTEND FROM PART 1\n");
    expect(text).toContain(AI_SHORTS_PLAN.shots[0]!.prompt);
    expect(text).toContain(AI_SHORTS_PLAN.shots[1]!.prompt);
  });

  it("marks generated text as generated, whoever wrote it", () => {
    expect(sourceChip("gemini")).toEqual({ label: "Written with Gemini", tone: "warn" });
    expect(sourceChip("fallback")).toEqual({ label: "Draft: built-in template", tone: "warn" });
  });

  it("uses the Creator's quality vocabulary, where no check is never a pass", () => {
    expect(verdictChip("GREEN")).toEqual({ label: "Passed quality check", tone: "warn" });
    expect(verdictChip("yellow").label).toMatch(/review warnings/);
    expect(verdictChip("RED")).toEqual({ label: "Failed quality check", tone: "bad" });
    expect(verdictChip(undefined)).toEqual({ label: "Quality not checked", tone: "neutral" });
  });

  it("shortens a long quote for a row", () => {
    expect(quoteExcerpt("  Some   silences are louder than words. ")).toBe("Some silences are louder than words.");
    expect(quoteExcerpt("word ".repeat(40), 20)).toMatch(/…$/);
  });
});

describe("package helpers", () => {
  it("puts the primary title first and drops repeats", () => {
    const titles = titleOptions({
      ...AI_SHORTS_PLAN,
      package: { ...AI_SHORTS_PLAN.package, title: "One", title_variants: ["Two", "one", "", "Three"] },
    });
    expect(titles).toEqual(["One", "Two", "Three"]);
    expect(titleOptions({ ...AI_SHORTS_PLAN, package: undefined })).toEqual([]);
  });

  it("reads quality notes whether they are strings or objects", () => {
    expect(qualityNotes(["Too long", { message: "Missing #shorts" }, { reason: "Generic" }, { code: "dup" }, 7, ""])).toEqual([
      "Too long",
      "Missing #shorts",
      "Generic",
      "dup",
    ]);
    expect(qualityNotes(undefined)).toEqual([]);
    expect(qualityNotes([{ message: "Same note" }, "Same note", { message: "Another note" }])).toEqual(["Same note", "Another note"]);
  });

  it("offers the Creator's languages without the one that needs a video", () => {
    expect(AI_SHORTS_LANGUAGE_OPTIONS.map((option) => option.value)).toEqual(["english", "tamil", "tanglish", "hindi"]);
  });
});
