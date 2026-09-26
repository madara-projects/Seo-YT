import { describe, expect, it } from "vitest";
import { cloudSyncRunOutcome, cloudSyncState, collectorState, geminiFailureLabel } from "./systemFormat";

describe("cloudSyncState", () => {
  it("maps known states to wording and tone", () => {
    expect(cloudSyncState("healthy/idle")).toEqual({ label: "Healthy", tone: "ok" });
    expect(cloudSyncState("offline/pending")).toEqual({ label: "Offline · changes queued", tone: "warn" });
    expect(cloudSyncState("unconfigured")).toEqual({ label: "Not configured", tone: "warn" });
  });

  it("shows an unknown state verbatim rather than guessing", () => {
    expect(cloudSyncState("rebalancing")).toEqual({ label: "rebalancing", tone: "neutral" });
    expect(cloudSyncState(undefined)).toEqual({ label: "Unavailable", tone: "neutral" });
  });
});

describe("cloudSyncRunOutcome", () => {
  it("calls only a healthy run a success", () => {
    expect(cloudSyncRunOutcome("healthy/idle").kind).toBe("success");
    // The run answers 200 even when it could not reach the cloud.
    expect(cloudSyncRunOutcome("offline/pending")).toEqual({
      kind: "warning",
      message: "Cloud sync couldn't finish. Changes stay queued and retry automatically.",
    });
    expect(cloudSyncRunOutcome("disabled").kind).toBe("warning");
    expect(cloudSyncRunOutcome("unconfigured").kind).toBe("warning");
    expect(cloudSyncRunOutcome("running").kind).toBe("info");
    expect(cloudSyncRunOutcome(undefined).kind).toBe("warning");
  });
});

describe("collectorState", () => {
  it("distinguishes a dry run from live collection", () => {
    expect(collectorState("dry-run").label).toBe("Dry run");
    expect(collectorState("healthy/idle").tone).toBe("ok");
  });

  it("says what unconfigured means for the collector", () => {
    expect(collectorState("unconfigured")).toEqual({ label: "Channel not connected", tone: "warn" });
  });
});

describe("geminiFailureLabel", () => {
  it("names the per-request call limit plainly", () => {
    expect(geminiFailureLabel("request_budget_exhausted")).toBe("Gemini call limit for this request reached");
    expect(geminiFailureLabel("rate_limited")).toBe("rate limited");
  });
});
