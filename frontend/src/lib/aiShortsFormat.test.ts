import { afterEach, describe, expect, it, vi } from "vitest";
import {
  AI_SHORTS_LANGUAGE_OPTIONS,
  allPromptsText,
  checkFindings,
  flowModeLabel,
  overlaySecondsLabel,
  packageFindings,
  partOverlay,
  partsLabel,
  planAdjustments,
  planStatus,
  promptParagraphs,
  promptSections,
  qualityNotes,
  quoteBlocker,
  quoteExcerpt,
  rangeLabel,
  readPlanTab,
  rememberPlanTab,
  shotHeading,
  shotRanges,
  sourceChip,
  stepPromptPart,
  stepText,
  titleOptions,
  verdictChip,
  verdictSummary,
} from "./aiShortsFormat";
import { AI_SHORTS_LEGACY_PLAN, AI_SHORTS_PLAN } from "@/test/fixtures/aiShorts";

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

  it("says how each part is made in Flow and where it sits in the Short", () => {
    expect(flowModeLabel({ part: 1, flow_mode: "text_to_video" })).toBe("Text to video");
    expect(flowModeLabel({ part: 2, flow_mode: "extend" })).toBe("Extend Part 1");
    expect(flowModeLabel({ part: 1 })).toBe("Text to video");

    const ranges = shotRanges(AI_SHORTS_PLAN.shots);
    expect(ranges).toEqual([{ start: 0, end: 8 }, { start: 8, end: 16 }]);
    expect(rangeLabel(ranges[1]!)).toBe("8–16 s");
    expect(shotHeading(AI_SHORTS_PLAN.shots[0]!, ranges[0]!)).toBe("Part 1 · 0–8 s · Text to video");
    expect(shotHeading(AI_SHORTS_PLAN.shots[1]!, ranges[1]!)).toBe("Part 2 · 8–16 s · Extend Part 1");
    // A part with no usable length counts as Flow's 8 seconds.
    expect(shotRanges([{ seconds: 8 }, { seconds: 0 }, { seconds: 8 }])).toEqual([
      { start: 0, end: 8 },
      { start: 8, end: 16 },
      { start: 16, end: 24 },
    ]);
  });

  it("labels every prompt by part when copying them together", () => {
    const text = allPromptsText(AI_SHORTS_PLAN.shots);
    expect(text.startsWith("PART 1 · 0–8 S · TEXT TO VIDEO\n")).toBe(true);
    expect(text).toContain("\n\nPART 2 · 8–16 S · EXTEND PART 1\n");
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

  it("says what each verdict means in a sentence", () => {
    expect(verdictSummary("GREEN")).toBe("The title, description and tags stay true to the quote.");
    expect(verdictSummary("yellow")).toMatch(/notes to read before you upload/);
    expect(verdictSummary("RED")).toMatch(/^Fix the notes/);
    expect(verdictSummary(undefined)).toBe("No quality check ran on this package.");
  });

  it("shortens a long quote for a row", () => {
    expect(quoteExcerpt("  Some   silences are louder than words. ")).toBe("Some silences are louder than words.");
    expect(quoteExcerpt("word ".repeat(40), 20)).toMatch(/…$/);
  });
});

describe("prompt text", () => {
  it("keeps the sections that have a label and text", () => {
    expect(promptSections(AI_SHORTS_PLAN.shots[0]!).map((section) => section.label)).toEqual([
      "Shot",
      "Subject",
      "Setting",
      "Light",
      "Look",
      "Keep out",
    ]);
    expect(
      promptSections({
        sections: [{ label: " Light ", text: " Dawn. " }, { label: "", text: "orphan" }, { label: "Look", text: "" }, null as never],
      }),
    ).toEqual([{ label: "Light", text: "Dawn." }]);
    expect(promptSections({ sections: undefined })).toEqual([]);
    expect(promptSections({ sections: "Shot: wide" as never })).toEqual([]);
  });

  it("splits an older prompt into paragraphs of about three sentences without breaking numbers", () => {
    const prompt =
      "Vertical 9:16 video, 8 seconds. A lens at f/2.8 holds 2.5 metres in focus. Slow push-in. Rain on glass. No text. Quiet.";
    const paragraphs = promptParagraphs(prompt);
    expect(paragraphs).toEqual([
      "Vertical 9:16 video, 8 seconds. A lens at f/2.8 holds 2.5 metres in focus. Slow push-in.",
      "Rain on glass. No text. Quiet.",
    ]);
    // Nothing is lost: the paragraphs read back as the prompt.
    expect(paragraphs.join(" ")).toBe(prompt);
    expect(promptParagraphs(AI_SHORTS_LEGACY_PLAN.shots[0]!.prompt).join(" ")).toBe(AI_SHORTS_LEGACY_PLAN.shots[0]!.prompt);
  });

  it("keeps the prompt's own line breaks and reports an empty prompt as none", () => {
    expect(promptParagraphs("First line.\n\nSecond line.\nThird.")).toEqual(["First line.", "Second line.", "Third."]);
    expect(promptParagraphs("   ")).toEqual([]);
  });

  it("finds a part's on-screen lines and times", () => {
    expect(partOverlay(AI_SHORTS_PLAN, 2)).toEqual({
      lines: ["that if you didn't find out,", "they would have never told you."],
      seconds: "8–16 s",
    });
    expect(partOverlay(AI_SHORTS_PLAN, 3)).toBeNull();
    expect(partOverlay({ text_overlay_plan: undefined }, 1)).toBeNull();
    expect(overlaySecondsLabel("0-8")).toBe("0–8 s");
    expect(overlaySecondsLabel("8 - 16 s")).toBe("8–16 s");
    expect(overlaySecondsLabel("")).toBeNull();
  });

  it("reads a Flow step without its number and finds the prompt it pastes", () => {
    expect(stepText("3. Paste the Part 1 prompt and generate.")).toBe("Paste the Part 1 prompt and generate.");
    expect(stepText("Open Flow.")).toBe("Open Flow.");
    expect(stepPromptPart("Paste the Part 1 prompt and generate.")).toBe(1);
    expect(stepPromptPart("In the prompt box, paste the Part 2 prompt, then generate.")).toBe(2);
    expect(stepPromptPart("Keep Part 1 on a Veo 3.1 model at 8 s.")).toBeNull();
  });
});

describe("checks", () => {
  it("files the planner's own fixes by part, from the new list and from an older plan's warnings", () => {
    const fresh = planAdjustments(AI_SHORTS_PLAN.checks);
    expect([...fresh.byPart.entries()]).toEqual([[1, ["added a calm upper-middle, audio line"]]]);
    expect(fresh.general).toEqual([]);

    const legacy = planAdjustments(AI_SHORTS_LEGACY_PLAN.checks);
    expect(legacy.byPart.get(1)).toEqual(["added a calm upper-middle, audio line, no dialogue, narration or music"]);
    expect(legacy.byPart.get(2)).toEqual(["trimmed from 131 to 118 words"]);

    expect(planAdjustments({ adjustments: ["Prompts were shortened to fit Veo."] }).general).toEqual([
      "Prompts were shortened to fit Veo.",
    ]);
    expect(planAdjustments(undefined).byPart.size).toBe(0);
  });

  it("lists only real issues and warnings, as sentences with their part", () => {
    expect(checkFindings(AI_SHORTS_PLAN.checks)).toEqual([
      {
        severity: "warning",
        part: null,
        text: "Part 2 continues a face-down phone; an Extend may re-light the screen earlier than written.",
      },
    ]);
    expect(checkFindings(AI_SHORTS_LEGACY_PLAN.checks)).toEqual([
      { severity: "warning", part: 2, text: "Prompt names no camera move." },
    ]);
    // A fix the backend also left among the warnings is still a fix, and an issue is never one.
    expect(
      checkFindings({
        issues: ["Part 2: Gemini returned no prompt"],
        warnings: ["Part 1: added audio line", "Part 1: kept the scene"],
        adjustments: ["Part 1: kept the scene"],
      }),
    ).toEqual([{ severity: "issue", part: 2, text: "Gemini returned no prompt." }]);
  });

  it("sums the checks up as ready or a number of things to check", () => {
    expect(planStatus({ passed: true, issues: [], warnings: [] })).toEqual({ label: "Ready", tone: "ok", count: 0 });
    // Fixes alone leave the plan ready.
    expect(planStatus({ passed: true, warnings: ["Part 1: added a calm upper-middle"] }).label).toBe("Ready");
    expect(planStatus(AI_SHORTS_PLAN.checks)).toEqual({ label: "1 thing to check", tone: "warn", count: 1 });
    expect(planStatus({ passed: false, issues: ["Part 1: no prompt"], warnings: ["Part 2: long"] })).toEqual({
      label: "2 things to check",
      tone: "bad",
      count: 2,
    });
    expect(planStatus({ passed: false })).toEqual({ label: "Checks failed", tone: "bad", count: 0 });
    expect(planStatus(undefined)).toEqual({ label: "Checks unavailable", tone: "neutral", count: 0 });
  });

  it("counts the package's quality notes in the same status: ready only when both are clean", () => {
    const yellow = { verdict: "YELLOW", issues: [], warnings: [{ code: "few", message: "Only 2 titles passed" }, "Add a theme tag"] };
    expect(packageFindings(yellow)).toEqual([
      { severity: "warning", part: null, text: "Only 2 titles passed." },
      { severity: "warning", part: null, text: "Add a theme tag." },
    ]);
    // Plan 10: the prompts' only notes were fixes, and the package asks for a review.
    expect(planStatus({ passed: true, warnings: ["Part 1: added a calm upper-middle"] }, yellow)).toEqual({
      label: "2 things to check",
      tone: "warn",
      count: 2,
    });
    expect(planStatus(AI_SHORTS_PLAN.checks, yellow).label).toBe("3 things to check");
    expect(planStatus({ passed: true }, { verdict: "RED", issues: ["The title cuts the quote"] })).toEqual({
      label: "1 thing to check",
      tone: "bad",
      count: 1,
    });
    // A verdict that lists no notes still asks for a look; a clean or missing one does not.
    expect(planStatus({ passed: true }, { verdict: "YELLOW" }).label).toBe("1 thing to check");
    expect(planStatus({ passed: true }, { verdict: "GREEN", issues: [], warnings: [] }).label).toBe("Ready");
    expect(planStatus({ passed: true }, undefined).label).toBe("Ready");
  });
});

describe("remembered tab", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("opens on the prompts until another tab is chosen, and ignores a damaged value", () => {
    expect(readPlanTab()).toBe("prompts");
    rememberPlanTab("package");
    expect(readPlanTab()).toBe("package");
    localStorage.setItem("win-engine-ai-shorts-tab", "settings");
    expect(readPlanTab()).toBe("prompts");
  });

  it("works when storage is blocked", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(() => rememberPlanTab("flow")).not.toThrow();
    expect(readPlanTab()).toBe("prompts");
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
