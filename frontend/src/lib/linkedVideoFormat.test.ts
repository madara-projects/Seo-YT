import { describe, expect, it } from "vitest";
import {
  diagnosisBasis,
  hasExhaustedWindows,
  labelChanges,
  labelDraft,
  labelErrors,
  labelOptions,
  learningStatus,
} from "./linkedVideoFormat";

describe("learningStatus", () => {
  it("names the unknown learning labels first", () => {
    const status = learningStatus({ comparable_metadata: { language: "unknown", format: "unknown", duration_bucket: "under_60s", topic_category: "sleep" } });
    expect(status.excluded).toBe(true);
    expect(status.body).toContain("Its format and language are unknown.");
  });

  it("treats a link with no label record as unlabelled", () => {
    expect(learningStatus({ comparable_metadata: {} }).body).toContain("Its format and language are unknown.");
  });

  it("explains an exclusion the labels do not cause", () => {
    const labelled = { language: "english", format: "youtube_shorts", duration_bucket: "under_60s", topic_category: "sleep" };
    expect(
      learningStatus({ comparable_metadata: labelled, ownership_verified: false, diagnosis: { counts_toward_generation: false } }).body,
    ).toContain("only videos verified as your connected channel's own are used");
    expect(
      learningStatus({ comparable_metadata: labelled, ownership_verified: true, diagnosis: { counts_toward_generation: false } }).body,
    ).toContain("once its 24-hour window has been collected");
  });

  it("does not blame the 24-hour window when the ownership check did not pass", () => {
    const labelled = { language: "english", format: "youtube_shorts" };
    const report = { comparable_metadata: labelled, ownership_verified: true, diagnosis: { counts_toward_generation: false } };
    expect(learningStatus({ ...report, ownership_state: "unverified", verified_channel_id: "UC1" }).body).toContain(
      "only videos verified as your connected channel's own are used",
    );
    expect(learningStatus({ ...report, ownership_state: "verified", verified_channel_id: null }).body).toContain(
      "only videos verified as your connected channel's own are used",
    );
    expect(learningStatus({ ...report, ownership_state: "verified", verified_channel_id: "UC1" }).body).toContain(
      "once its 24-hour window has been collected",
    );
  });

  it("counts only the exact placeholder as unknown, as the server does", () => {
    expect(learningStatus({ comparable_metadata: { language: "Unknown", format: "vlog" } }).excluded).not.toBe(true);
  });

  it("claims nothing about inclusion when the server does not say", () => {
    const status = learningStatus({ comparable_metadata: { language: "english", format: "vlog" } });
    expect(status.excluded).toBeNull();
    expect(status.body).toContain("once its duration and topic are set too");
  });
});

describe("diagnosisBasis", () => {
  it("is null for an older payload", () => {
    expect(diagnosisBasis({ verdict: "x" })).toBeNull();
    expect(diagnosisBasis(undefined)).toBeNull();
  });

  const labelled = { language: "english", format: "youtube_shorts", duration_bucket: "under_60s", topic_category: "sleep" };

  it("makes no peer claim before a window has completed", () => {
    // The server sends a size of 0 here without looking for peers, so
    // comparable videos may well exist.
    expect(diagnosisBasis({ window: "none", baseline_sample_size: 0, peer_baseline_available: false }, labelled)).toBe(
      "No completed window yet.",
    );
    expect(diagnosisBasis({ window: null, baseline_sample_size: null, peer_baseline_available: false })).toBe(
      "No completed window yet.",
    );
    expect(diagnosisBasis({ window: "28d", baseline_sample_size: 1, peer_baseline_available: true })).toBe(
      "From the 28-day window · compared with 1 comparable video.",
    );
  });

  it("never claims that no comparable videos exist after a completed window", () => {
    // With every label set, a 0 can still come from a server that did not
    // look, so the wording only says no comparison was made.
    expect(diagnosisBasis({ window: "24h", baseline_sample_size: 0, peer_baseline_available: false }, labelled)).toBe(
      "From the 24-hour window · not compared with other videos.",
    );
    expect(diagnosisBasis({ window: "24h", baseline_sample_size: null, peer_baseline_available: false })).toBe(
      "From the 24-hour window · not compared with other videos.",
    );
  });

  it("names the unknown labels that stopped the comparison", () => {
    const partial = { ...labelled, duration_bucket: "unknown", topic_category: "" };
    expect(diagnosisBasis({ window: "24h", baseline_sample_size: 0, peer_baseline_available: false }, partial)).toBe(
      "From the 24-hour window · not compared with other videos while its duration and topic are unknown.",
    );
    // A legacy link with no label record has all four unknown.
    expect(diagnosisBasis({ window: "7d", baseline_sample_size: 0, peer_baseline_available: false }, {})).toBe(
      "From the 7-day window · not compared with other videos while its language, format, duration and topic are unknown.",
    );
  });

  it("never says there were no peers when the server used a baseline", () => {
    expect(diagnosisBasis({ window: "7d", baseline_sample_size: null, peer_baseline_available: true })).toBe(
      "From the 7-day window · compared with similar videos.",
    );
  });
});

describe("label edits", () => {
  const stored = { language: "unknown", format: "youtube_shorts", duration_bucket: "unknown", topic_category: "Sleep" };

  it("treats a stored label with inner spaces as unchanged until it is edited", () => {
    const spaced = { ...stored, topic_category: "money  tips" };
    expect(labelChanges(labelDraft(spaced), spaced)).toEqual({});
  });

  it("checks only the labels that will be sent", () => {
    const odd = { ...stored, duration_bucket: "about_a_minute" };
    // The older stored duration is not sent with a language edit, so it does not block it.
    expect(labelErrors({ ...labelDraft(odd), language: "tamil" }, odd)).toEqual({});
    expect(labelErrors({ ...labelDraft(odd), duration_bucket: "about_two_minutes" }, odd)).toHaveProperty("duration_bucket");
  });

  it("sends only changed labels, with a cleared one as null", () => {
    const draft = { ...labelDraft(stored), language: "english", topic_category: " " };
    expect(labelChanges(draft, stored)).toEqual({ language: "english", topic_category: null });
    expect(labelChanges(labelDraft(stored), stored)).toEqual({});
  });

  it("catches what the route would refuse", () => {
    const draft = { ...labelDraft(stored), topic_category: "x".repeat(81), duration_bucket: "two_minutes" };
    expect(labelErrors(draft)).toEqual({
      topic_category: "Limited to 80 characters.",
      duration_bucket: "Choose one of the listed durations.",
    });
    expect(labelErrors(labelDraft(stored))).toEqual({});
  });

  it("keeps a stored spelling outside the list as a choice", () => {
    expect(labelOptions("language", "telugu").at(-1)).toEqual({ value: "telugu", label: "Telugu" });
    expect(labelOptions("language", "english").some((option) => option.value === "telugu")).toBe(false);
  });
});

describe("hasExhaustedWindows", () => {
  it("is true only for a window the server marks exhausted", () => {
    expect(hasExhaustedWindows([{ retry_exhausted: false }, { retry_exhausted: true }])).toBe(true);
    expect(hasExhaustedWindows([{ snapshot_status: "failed", attempt_count: 3 }])).toBe(false);
    expect(hasExhaustedWindows(undefined)).toBe(false);
  });

  it("is true for a completed window whose traffic breakdown the server marks exhausted", () => {
    expect(
      hasExhaustedWindows([{ snapshot_status: "complete", retry_exhausted: false, traffic_retry_exhausted: true }]),
    ).toBe(true);
    expect(hasExhaustedWindows([{ snapshot_status: "complete", traffic_retry_exhausted: false }])).toBe(false);
  });
});
