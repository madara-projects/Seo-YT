import { describe, expect, it } from "vitest";
import { cloudDeletionNote } from "./useHistory";

// States are the ones `CloudSyncService` reports: disabled, waiting, running,
// unconfigured, healthy/idle and offline/pending. The delete route answers
// with `request_run()`, or `{ state: "disabled", run_requested: false }` when
// there is no sync service at all.
describe("cloudDeletionNote", () => {
  it("says the deletion goes out shortly only when the background sync was woken", () => {
    expect(
      cloudDeletionNote({ state: "healthy/idle", enabled: true, run_requested: true, pending_deletions: 1 }),
    ).toBe("Cloud deletion is queued and will sync shortly.");
  });

  it("doesn't promise a prompt sync for a queued deletion when nothing was woken", () => {
    expect(
      cloudDeletionNote({ state: "offline/pending", enabled: true, run_requested: false, pending_deletions: 2 }),
    ).toBe("Cloud deletion is queued and will retry automatically.");
  });

  it("says the cloud copy waits for the next sync when sync is off", () => {
    expect(
      cloudDeletionNote({ state: "disabled", enabled: false, run_requested: false, pending_deletions: 1 }),
    ).toBe("Cloud sync is off; the cloud copy is removed when sync next runs.");
    expect(cloudDeletionNote({ state: "disabled", enabled: false, run_requested: false, pending_deletions: 3 }, 3)).toBe(
      "Cloud sync is off; the cloud copies are removed when sync next runs.",
    );
  });

  it("says the package stayed local when sync is off and it was never synced", () => {
    expect(
      cloudDeletionNote({ state: "disabled", enabled: false, run_requested: false, pending_deletions: 0 }),
    ).toBe("Cloud sync is off; the package was deleted on this device only.");
    // The route's answer when the app has no sync service.
    expect(cloudDeletionNote({ state: "disabled", run_requested: false }, 2)).toBe(
      "Cloud sync is off; the packages were deleted on this device only.",
    );
  });

  it("falls back to the retry wording when the status is missing or can't be read", () => {
    expect(cloudDeletionNote(undefined)).toBe("Cloud deletion is queued and will retry automatically.");
    expect(
      cloudDeletionNote({ state: "unconfigured", enabled: true, run_requested: false, pending_deletions: null }),
    ).toBe("Cloud deletion is queued and will retry automatically.");
  });
});
