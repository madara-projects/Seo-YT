import { describe, expect, it } from "vitest";
import { cloudSyncState, collectorState } from "./systemFormat";

describe("cloudSyncState", () => {
  it("maps known states to wording and tone", () => {
    expect(cloudSyncState("healthy/idle")).toEqual({ label: "Healthy", tone: "ok" });
    expect(cloudSyncState("offline/pending")).toEqual({ label: "Offline · changes queued", tone: "warn" });
    expect(cloudSyncState("error")).toEqual({ label: "Error", tone: "bad" });
  });

  it("shows an unknown state verbatim rather than guessing", () => {
    expect(cloudSyncState("rebalancing")).toEqual({ label: "rebalancing", tone: "neutral" });
    expect(cloudSyncState(undefined)).toEqual({ label: "Unavailable", tone: "neutral" });
  });
});

describe("collectorState", () => {
  it("distinguishes a dry run from live collection", () => {
    expect(collectorState("dry-run").label).toBe("Dry run");
    expect(collectorState("healthy/idle").tone).toBe("ok");
    expect(collectorState("unconfigured").tone).toBe("warn");
  });
});
