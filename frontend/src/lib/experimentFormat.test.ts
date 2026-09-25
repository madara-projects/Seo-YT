import { describe, expect, it } from "vitest";
import {
  directionLabel,
  experimentStatusLabel,
  isClosed,
  metricValue,
  minimumPerGroup,
  modeLabel,
  relativeDifference,
  resultStateLabel,
  transitionsFrom,
  variableLabel,
} from "./experimentFormat";

describe("transitionsFrom", () => {
  const targets = (status: string) => transitionsFrom(status).map((item) => item.to);

  it("offers exactly the backend's allowed transitions", () => {
    expect(targets("draft")).toEqual(["planned", "cancelled"]);
    expect(targets("planned")).toEqual(["active", "paused", "cancelled"]);
    expect(targets("active")).toEqual(["completed", "paused", "inconclusive", "cancelled"]);
    expect(targets("paused")).toEqual(["active", "completed", "inconclusive", "cancelled"]);
    for (const closed of ["completed", "cancelled", "inconclusive"]) expect(targets(closed)).toEqual([]);
  });

  it("puts the natural next step first, as the legacy page did", () => {
    expect(transitionsFrom("planned")[0]).toMatchObject({ to: "active", label: "Start", primary: true });
    expect(transitionsFrom("paused")[0]).toMatchObject({ to: "active", label: "Resume" });
    expect(transitionsFrom("active")[0]?.label).toBe("Mark completed");
  });

  it("marks the transitions that can't be undone", () => {
    const final = transitionsFrom("active").filter((item) => item.final).map((item) => item.to);
    expect(final).toEqual(["completed", "inconclusive", "cancelled"]);
    expect(isClosed("inconclusive")).toBe(true);
    expect(isClosed("paused")).toBe(false);
  });
});

describe("experiment wording", () => {
  it("labels status, type and variable", () => {
    expect(experimentStatusLabel("paused")).toEqual({ label: "Paused", tone: "warn" });
    expect(experimentStatusLabel("archived").label).toBe("Archived");
    expect(modeLabel("observational").label).toBe("Observational");
    expect(modeLabel("controlled").label).toBe("Planned experiment");
    expect(variableLabel("first_frame_text")).toBe("First-frame text");
  });

  it("states results without claiming more than the comparison did", () => {
    expect(resultStateLabel("directional_variant").label).toBe("Variant ahead");
    expect(resultStateLabel("insufficient_evidence").tone).toBe("warn");
    expect(resultStateLabel(undefined).label).toBe("Not compared");
    expect(directionLabel("even")).toBe("No clear direction");
  });

  it("formats rates as percentages and counts as numbers", () => {
    expect(metricValue("average_view_percentage", 60)).toBe("60.0%");
    expect(metricValue("engagement_rate", 5.123)).toBe("5.1%");
    expect(metricValue("views", 980.4)).toBe((980).toLocaleString());
    expect(metricValue("views", null)).toBe("Unavailable");
    expect(relativeDifference(13.33)).toBe("+13.3%");
    expect(relativeDifference(-2.5)).toBe("−2.5%");
    expect(relativeDifference(null)).toBe("Unavailable");
  });

  it("never reports fewer than five videos per side, as the comparison enforces", () => {
    expect(minimumPerGroup(3)).toBe(5);
    expect(minimumPerGroup(8)).toBe(8);
    expect(minimumPerGroup(undefined)).toBe(5);
  });
});
