import { describe, expect, it } from "vitest";
import {
  chosenSimilarPairs,
  clockTime,
  retentionReasonLabel,
  studioResultText,
  studioStatusLabel,
  trafficSourceLabel,
} from "./learningFormat";

describe("learningFormat", () => {
  it("names traffic sources as YouTube Studio does", () => {
    expect(trafficSourceLabel("RELATED_VIDEO")).toBe("Suggested videos");
    expect(trafficSourceLabel("SUBSCRIBER")).toBe("Browse features");
    expect(trafficSourceLabel("yt_search")).toBe("YouTube search");
    expect(trafficSourceLabel("SHORTS")).toBe("Shorts feed");
    expect(trafficSourceLabel("SOME_NEW_SOURCE")).toBe("Some new source");
    expect(trafficSourceLabel(null)).toBe("Unknown source");
  });

  it("explains every retention probe reason", () => {
    expect(retentionReasonLabel("missing_scope")).toBe("Analytics permission missing");
    expect(retentionReasonLabel("not_channel_video")).toBe("Not the channel's own video");
    expect(retentionReasonLabel("no_data_yet")).toBe("No retention data yet");
    expect(retentionReasonLabel("api_error")).toBe("YouTube request failed");
    expect(retentionReasonLabel("not_connected")).toBe("Channel not connected");
    expect(retentionReasonLabel("other")).toBe("Unavailable");
  });

  it("keeps only the similar pairs among the chosen packages", () => {
    const pairs = [
      { first: "package-a", second: "package-b", similarity: 0.9, message: "" },
      { first: "package-c", second: "package-d", similarity: 0.85, message: "" },
    ];
    expect(chosenSimilarPairs(pairs, ["package-a", "package-b", "package-c"])).toEqual([pairs[0]]);
    expect(chosenSimilarPairs(pairs, ["package-a"])).toEqual([]);
  });

  it("describes a test's state and Studio's result", () => {
    expect(studioStatusLabel({ status: "prepared", linked_video: null })).toBe("Prepared, not linked");
    expect(studioStatusLabel({ status: "linked", linked_video: { link_id: 1, youtube_video_id: "v" } })).toBe(
      "Linked to the published video",
    );
    expect(studioStatusLabel({ status: "completed", linked_video: null })).toBe("Result recorded");
    expect(
      studioResultText({ winner_variant: "B", result: { outcome: "winner", watch_time_share: { A: 41.2, B: 58.8 } } }),
    ).toBe("Studio picked B · watch-time share A 41.2% · B 58.8%");
    expect(studioResultText({ winner_variant: null, result: { outcome: "no_clear_winner" } })).toBe("No clear winner");
    expect(studioResultText({ winner_variant: null, result: null })).toBeNull();
  });

  it("formats seconds as a clock", () => {
    expect(clockTime(30)).toBe("0:30");
    expect(clockTime(125)).toBe("2:05");
    expect(clockTime(3723)).toBe("1:02:03");
    expect(clockTime(null)).toBe("");
  });
});
