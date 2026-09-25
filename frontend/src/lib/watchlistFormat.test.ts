import { describe, expect, it } from "vitest";
import { channelCounts, languageName, outlierLabel, watchFormatLabel, watchStateLabel } from "./watchlistFormat";
import { addChannelSchema, addVideoSchema, extractChannelId, extractVideoId } from "@/schemas/watchlist";

const CHANNEL = "UCzU9GK79bxzBfBYrc_D9jjg";

describe("outlierLabel", () => {
  it("names each result of the local check", () => {
    expect(outlierLabel("possible_outlier")).toEqual({ label: "Possible outlier", tone: "warn" });
    expect(outlierLabel("observed_normal").label).toBe("Within normal range");
    expect(outlierLabel("insufficient_evidence").label).toBe("Not enough peers");
  });

  it("says when no check has run", () => {
    expect(outlierLabel(null)).toEqual({ label: "Not analysed", tone: "neutral" });
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
