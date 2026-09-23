import { describe, expect, it } from "vitest";
import {
  formatWatchTime,
  riskTone,
  roundOpportunity,
  roundTitleScore,
  savedAnalysesCaption,
} from "./dashboardFormat";
import { historyDate, matchesQuery, resultSummary, runTitle, savedCountLabel } from "./historyFormat";
import type { HistoryRun } from "@/api/historyTypes";

describe("formatWatchTime", () => {
  it("shows hours to one decimal at or above an hour", () => {
    expect(formatWatchTime(60, true)).toBe("1.0 hrs");
    expect(formatWatchTime(90, true)).toBe("1.5 hrs");
  });

  it("shows minutes below an hour", () => {
    expect(formatWatchTime(45, true)).toBe("45 mins");
  });

  it("treats a connected zero as a measurement, not an absence", () => {
    expect(formatWatchTime(0, true)).toBe("0 mins");
  });

  it("reports unavailable when disconnected or absent", () => {
    expect(formatWatchTime(0, false)).toBe("Unavailable");
    expect(formatWatchTime(null, true)).toBe("Unavailable");
    expect(formatWatchTime(undefined, true)).toBe("Unavailable");
  });
});

describe("score rounding", () => {
  it("rounds opportunity to a whole number and title score to one decimal", () => {
    expect(roundOpportunity(38.6)).toBe(39);
    expect(roundTitleScore(7.54)).toBe(7.5);
  });

  it("returns null rather than zero for absent scores", () => {
    expect(roundOpportunity(null)).toBeNull();
    expect(roundTitleScore(undefined)).toBeNull();
    expect(roundOpportunity("7")).toBeNull();
  });
});

describe("riskTone", () => {
  it("maps risk levels to reserved status tones", () => {
    expect(riskTone("HIGH")).toBe("bad");
    expect(riskTone("medium")).toBe("warn");
    expect(riskTone("Low")).toBe("info");
    expect(riskTone("anything else")).toBe("neutral");
  });
});

describe("savedAnalysesCaption", () => {
  it("agrees in number", () => {
    expect(savedAnalysesCaption(1)).toBe("Calculated from your 1 saved analysis.");
    expect(savedAnalysesCaption(3)).toBe("Calculated from your 3 saved analyses.");
  });

  it("does not claim a count it does not have", () => {
    expect(savedAnalysesCaption(undefined)).toBe("No saved analyses yet.");
  });
});

describe("historyDate", () => {
  it("renders an IST-suffixed timestamp", () => {
    const formatted = historyDate("2026-09-22T17:53:19.965599+00:00");
    expect(formatted).toContain("IST");
    expect(formatted).toContain("2026");
  });

  it("returns Unknown for missing or unparseable values", () => {
    expect(historyDate(null)).toBe("Unknown");
    expect(historyDate("")).toBe("Unknown");
    expect(historyDate("not a date")).toBe("Unknown");
  });
});

describe("history search", () => {
  const run: HistoryRun = {
    id: 1,
    title: "Three Morning Habits",
    query: "waking at the same time daily",
    content_angle: "Story",
  };

  it("matches case-insensitively across title, query and angle", () => {
    expect(matchesQuery(run, "morning")).toBe(true);
    expect(matchesQuery(run, "WAKING")).toBe(true);
    expect(matchesQuery(run, "story")).toBe(true);
  });

  it("returns everything for an empty or whitespace query", () => {
    expect(matchesQuery(run, "")).toBe(true);
    expect(matchesQuery(run, "   ")).toBe(true);
  });

  it("excludes non-matches", () => {
    expect(matchesQuery(run, "zzz")).toBe(false);
  });

  it("tolerates a run with no title or query", () => {
    expect(matchesQuery({ id: 2 }, "anything")).toBe(false);
    expect(runTitle({ id: 2 })).toBe("Untitled package");
  });
});

describe("history labels", () => {
  it("agrees in number for the saved count", () => {
    expect(savedCountLabel(1)).toBe("1 saved package");
    expect(savedCountLabel(4)).toBe("4 saved packages");
  });

  it("summarises filtered vs total results", () => {
    expect(resultSummary(10, 3, "focus")).toBe("3 of 10 packages match “focus”");
    expect(resultSummary(10, 10, "")).toBe("10 packages available");
    expect(resultSummary(1, 1, "")).toBe("1 package available");
  });
});
