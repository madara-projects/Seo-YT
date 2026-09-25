import { describe, expect, it } from "vitest";
import {
  classificationLabel,
  formatLabel,
  languageLabel,
  regionLabel,
  signalName,
  sourceLabel,
} from "./demandFormat";

describe("classificationLabel", () => {
  it("names every level the backend can return", () => {
    expect(classificationLabel("strong_observed_interest").label).toBe("Strong observed interest");
    expect(classificationLabel("active_topic").label).toBe("Active topic");
    expect(classificationLabel("emerging_signal").label).toBe("Emerging signal");
    expect(classificationLabel("insufficient_evidence")).toMatchObject({
      label: "Insufficient evidence",
      tone: "warn",
    });
  });

  it("quotes the thresholds the backend actually checks", () => {
    expect(classificationLabel("active_topic").meaning).toContain("5 or more sampled results");
    expect(classificationLabel("strong_observed_interest").meaning).toContain("at least 4 channels");
  });

  it("never invents a level for an unknown or missing value", () => {
    expect(classificationLabel("new_level")).toMatchObject({ label: "New level", tone: "neutral" });
    expect(classificationLabel(undefined).label).toBe("Unavailable");
  });
});

describe("signal and source wording", () => {
  it("names the recorded signals", () => {
    expect(signalName("recent_publications_90d")).toBe("Published in the last 90 days");
    expect(signalName("median_captured_views")).toBe("Median views at capture");
    expect(signalName("some_future_signal")).toBe("Some future signal");
  });

  it("keeps heuristics distinguishable from observations", () => {
    expect(sourceLabel("public_observation")).toEqual({ label: "Public observation", tone: "info" });
    expect(sourceLabel("heuristic")).toEqual({ label: "Local heuristic", tone: "warn" });
    expect(sourceLabel("unavailable").tone).toBe("neutral");
  });
});

describe("filter labels", () => {
  it("treats a blank filter as any", () => {
    expect(languageLabel("")).toBe("Any language");
    expect(formatLabel(null)).toBe("Any format");
    expect(regionLabel(undefined)).toBe("Any region");
  });

  it("shows known values whatever their case", () => {
    expect(formatLabel("youtube_shorts")).toBe("YouTube Short");
    expect(languageLabel("tamil")).toBe("Tamil");
    // Typed into the legacy free-text fields.
    expect(regionLabel("Tamil Nadu")).toBe("Tamil Nadu");
    expect(languageLabel("TANGLISH")).toBe("Tanglish");
  });

  it("reads the Ideas form's spellings as the options they mean", () => {
    expect(regionLabel("in")).toBe("India");
    expect(regionLabel("global")).toBe("Any region");
    expect(formatLabel("unknown")).toBe("Any format");
    expect(formatLabel("tutorial")).toBe("Tutorial");
  });

  it("keeps other free text as it was typed", () => {
    expect(regionLabel("UAE")).toBe("UAE");
    expect(languageLabel("malayalam")).toBe("Malayalam");
    expect(regionLabel("constructor")).toBe("Constructor");
  });
});
