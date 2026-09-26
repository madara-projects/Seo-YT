import { describe, expect, it } from "vitest";
import {
  auditStateLabel,
  candidateTitle,
  comparisonText,
  fieldStateLabel,
  findingSeverity,
  metadataVerdict,
  publishedFieldState,
  windowLabel,
} from "./auditFormat";
import { AUDIT_FIXTURE } from "@/test/fixtures/audit";

describe("auditStateLabel", () => {
  it("names every summary state the audit can reach", () => {
    for (const state of [
      "not_run",
      "not_enough_data",
      "collecting_evidence",
      "observable",
      "mature_observation",
      "actionable_observation",
      "inconclusive",
    ]) {
      expect(auditStateLabel(state).meaning).not.toMatch(/isn't recognised/);
    }
    expect(auditStateLabel("actionable_observation").tone).toBe("ok");
  });

  it("never invents a state", () => {
    expect(auditStateLabel("something_new")).toMatchObject({ label: "Something new", tone: "neutral" });
  });
});

describe("metadataVerdict", () => {
  it("reads the backend's exact_match, which the legacy page never did", () => {
    const matching = AUDIT_FIXTURE.comparisons.map((item) => ({ ...item, generated_to_published: "exact_match" }));
    expect(metadataVerdict(matching)).toMatchObject({ label: "Matches your package", tone: "ok" });
  });

  it("names the fields that differ", () => {
    expect(metadataVerdict(AUDIT_FIXTURE.comparisons)).toEqual({
      label: "Differences found",
      tone: "warn",
      text: "What's on YouTube differs from the saved package in: description, hashtags.",
    });
  });

  it("says when YouTube's side was never captured", () => {
    const unavailable = AUDIT_FIXTURE.comparisons.map((item) => ({ ...item, generated_to_published: "unavailable" }));
    expect(metadataVerdict(unavailable).label).toBe("YouTube data unavailable");
    expect(metadataVerdict([]).label).toBe("YouTube data unavailable");
  });

  it("judges against the recorded selection, not the primary package", () => {
    // Package C was selected and published exactly; the primary differs everywhere.
    const selected = AUDIT_FIXTURE.comparisons.map((item) => ({
      ...item,
      generated_to_published: "changed",
      selected_to_published: "exact_match",
    }));
    expect(metadataVerdict(selected, true)).toEqual({
      label: "Matches your selection",
      tone: "ok",
      text: "The title, description, tags and hashtags on YouTube match the package you selected.",
    });
    expect(metadataVerdict(selected, false).label).toBe("Differences found");
    expect(publishedFieldState(selected[0]!, true)).toBe("exact_match");
    expect(publishedFieldState(selected[0]!, false)).toBe("changed");
  });

  it("names the fields that differ from the selection", () => {
    const selected = AUDIT_FIXTURE.comparisons.map((item) => ({
      ...item,
      selected_to_published: item.field === "title" ? "changed" : "exact_match",
    }));
    expect(metadataVerdict(selected, true).text).toBe(
      "What's on YouTube differs from the package you selected in: title.",
    );
  });
});

describe("audit values", () => {
  it("shows compared values as text, and empty ones as empty", () => {
    expect(comparisonText(["#shorts", " #silence "])).toBe("#shorts, #silence");
    expect(comparisonText([])).toBeNull();
    expect(comparisonText("  ")).toBeNull();
    expect(comparisonText(null)).toBeNull();
  });

  it("labels field states, severities and windows", () => {
    expect(fieldStateLabel("exact_match")).toEqual({ label: "Matches", tone: "ok" });
    expect(fieldStateLabel("changed").tone).toBe("warn");
    expect(fieldStateLabel(undefined).label).toBe("Unavailable");
    expect(findingSeverity("review")).toEqual({ label: "Review", tone: "warn" });
    expect(findingSeverity("info").label).toBe("Note");
    expect(windowLabel("7d")).toBe("7-day window");
    expect(windowLabel("current")).toBe("Current counts");
  });

  it("titles a video from the best source available", () => {
    const base = { youtube_video_id: "z4HKMfQ3nJc", selected_title: null, package_topic: null, youtube_metadata: null };
    expect(candidateTitle({ ...base, youtube_metadata: { title: "On YouTube" }, selected_title: "Selected" })).toBe("On YouTube");
    expect(candidateTitle({ ...base, package_topic: "Topic" })).toBe("Topic");
    expect(candidateTitle(base)).toBe("z4HKMfQ3nJc");
  });
});
