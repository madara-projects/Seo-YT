import { describe, expect, it } from "vitest";
import {
  channelCounts,
  formatMultiplier,
  languageName,
  outlierLabel,
  watchFormatBasis,
  watchFormatLabel,
  watchStateLabel,
} from "./watchlistFormat";
import { addChannelSchema, addVideoSchema, extractChannelId, extractVideoId } from "@/schemas/watchlist";

const CHANNEL = "UCzU9GK79bxzBfBYrc_D9jjg";

describe("outlierLabel", () => {
  it("names each result of the local check", () => {
    expect(outlierLabel("possible_outlier")).toEqual({ label: "Possible outlier", tone: "warn" });
    expect(outlierLabel("observed_normal").label).toBe("Within normal range");
    expect(outlierLabel("insufficient_evidence").label).toBe("Not enough evidence");
  });

  it("says when no check has run", () => {
    expect(outlierLabel(null)).toEqual({ label: "Not analysed", tone: "neutral" });
    expect(outlierLabel("not_analyzed")).toEqual({ label: "Not analysed", tone: "neutral" });
  });

  it("never rounds a multiplier across the threshold", () => {
    // 2.45 is within the normal range; one decimal would print the 2.5× threshold.
    expect(formatMultiplier(2.45)).toBe("2.45×");
    expect(formatMultiplier(4.47)).toBe("4.47×");
  });
});

describe("watchlist labels", () => {
  it("names stored language codes", () => {
    expect(languageName("ta")).toBe("Tamil");
    expect(languageName("unknown")).toBe("Unknown");
    expect(languageName("")).toBe("Unknown");
    expect(languageName("not a code!")).toBe("not a code!");
  });

  it("keeps hidden counts unavailable rather than zero", () => {
    expect(channelCounts({ subscriber_count: null, video_count: 12 })).toBe("Subscribers unavailable · 12 videos");
  });

  it("describes format and state", () => {
    expect(watchFormatLabel("youtube_shorts")).toBe("Short");
    expect(watchFormatLabel("unknown")).toBe("Unknown format");
    expect(watchStateLabel("archived").label).toBe("Archived");
    expect(watchStateLabel("active").label).toBe("Active");
  });

  it("says a format is inferred from duration, not reported by YouTube", () => {
    expect(watchFormatBasis("youtube_shorts")).toMatch(/Inferred from its duration: up to 3 minutes/);
    expect(watchFormatBasis("unknown")).toBeNull();
  });
});

describe("identifiers", () => {
  it("finds a channel ID in an ID or a channel link", () => {
    expect(extractChannelId(CHANNEL)).toBe(CHANNEL);
    expect(extractChannelId(` https://www.youtube.com/channel/${CHANNEL}?view=about `)).toBe(CHANNEL);
    expect(extractChannelId("@kindoflost")).toBeNull();
    expect(extractChannelId("https://www.youtube.com/@kindoflost")).toBeNull();
    expect(extractChannelId("UC123")).toBeNull();
  });

  it("finds a video ID the way the backend does", () => {
    expect(extractVideoId("https://youtu.be/z4HKMfQ3nJc?t=3")).toBe("z4HKMfQ3nJc");
    expect(extractVideoId("https://www.youtube.com/watch?v=z4HKMfQ3nJc&list=PL1")).toBe("z4HKMfQ3nJc");
    expect(extractVideoId("https://www.youtube.com/shorts/z4HKMfQ3nJc")).toBe("z4HKMfQ3nJc");
    expect(extractVideoId("z4HKMfQ3nJc")).toBe("z4HKMfQ3nJc");
    expect(extractVideoId("not a link")).toBeNull();
  });

  it("accepts only YouTube's hosts and paths, as the backend now does", () => {
    expect(extractVideoId("m.youtube.com/watch?v=z4HKMfQ3nJc")).toBe("z4HKMfQ3nJc");
    expect(extractVideoId("https://music.youtube.com/watch?v=z4HKMfQ3nJc")).toBe("z4HKMfQ3nJc");
    expect(extractVideoId("https://www.youtube-nocookie.com/embed/z4HKMfQ3nJc")).toBe("z4HKMfQ3nJc");
    expect(extractVideoId("https://www.youtube.com/live/z4HKMfQ3nJc?si=x")).toBe("z4HKMfQ3nJc");
    expect(extractVideoId("https://example.com/watch?v=z4HKMfQ3nJc")).toBeNull();
    expect(extractVideoId("https://youtube.com.evil.test/watch?v=z4HKMfQ3nJc")).toBeNull();
    // Longer than 11 characters is refused rather than cut.
    expect(extractVideoId("z4HKMfQ3nJcX")).toBeNull();
    expect(extractVideoId("https://youtu.be/z4HKMfQ3nJcX")).toBeNull();
    expect(extractVideoId("https://www.youtube.com/watch?v=z4HKMfQ3nJcX")).toBeNull();
  });

  it("explains why a handle can't be added", () => {
    const handle = addChannelSchema.safeParse({ channel: "@kindoflost", notes: "" });
    expect(handle.success).toBe(false);
    expect(handle.error?.issues.map((issue) => issue.message)).toEqual([
      "Handles can't be looked up. Use the channel ID that starts with UC (Share channel → Copy channel ID).",
    ]);
    expect(addChannelSchema.safeParse({ channel: "hello", notes: "" }).error?.issues[0]?.message).toMatch(
      /starts with UC/,
    );
    expect(addChannelSchema.safeParse({ channel: CHANNEL, notes: "" }).success).toBe(true);
    expect(addVideoSchema.safeParse({ video: "https://youtu.be/z4HKMfQ3nJc", notes: "" }).success).toBe(true);
  });
});
