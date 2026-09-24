import { describe, expect, it } from "vitest";
import {
  hasMetrics,
  periodComparison,
  recentUploadsSeries,
  sortVideos,
  youtubeChannelUrl,
  youtubeWatchUrl,
} from "./channelFormat";
import type { ChannelVideo } from "@/api/systemTypes";

const videos: ChannelVideo[] = [
  { video_id: "aaaaaaaaaaa", title: "Oldest", published_at: "2026-09-01T00:00:00Z", views: 500, likes: 10, comments: 0 },
  { video_id: "bbbbbbbbbbb", title: "Newest", published_at: "2026-09-20T00:00:00Z", views: 100, likes: 30, comments: 20 },
  { video_id: "ccccccccccc", title: "Middle", published_at: "2026-09-10T00:00:00Z", views: 900, likes: 9, comments: 0 },
];

describe("periodComparison", () => {
  it("compares every metric the two windows share", () => {
    const rows = periodComparison(
      { views: 1200, averageViewDuration: 17 },
      { views: 1000, averageViewDuration: 20 },
    );
    const views = rows.find((row) => row.key === "views");
    const duration = rows.find((row) => row.key === "averageViewDuration");

    expect(views?.change).toBeCloseTo(20);
    expect(duration?.change).toBeCloseTo(-15);
  });

  it("keeps a missing metric null rather than zero", () => {
    const likes = periodComparison({ views: 10 }, { views: 5 }).find((row) => row.key === "likes");
    expect(likes).toMatchObject({ current: null, previous: null, change: null });
  });

  it("does not compare against an empty earlier window", () => {
    const views = periodComparison({ views: 10 }, {}).find((row) => row.key === "views");
    expect(views?.current).toBe(10);
    expect(views?.change).toBeNull();
  });
});

describe("hasMetrics", () => {
  it("recognises an Analytics query that returned nothing", () => {
    expect(hasMetrics({})).toBe(false);
    expect(hasMetrics(undefined)).toBe(false);
    expect(hasMetrics({ views: 0 })).toBe(true);
  });
});

describe("sortVideos", () => {
  it("orders by publish date, views, or engagement", () => {
    expect(sortVideos(videos, "newest").map((video) => video.title)).toEqual(["Newest", "Middle", "Oldest"]);
    expect(sortVideos(videos, "views").map((video) => video.title)).toEqual(["Middle", "Oldest", "Newest"]);
    expect(sortVideos(videos, "engagement")[0]?.title).toBe("Newest");
  });

  it("does not reorder the caller's array", () => {
    const copy = [...videos];
    sortVideos(videos, "views");
    expect(videos).toEqual(copy);
  });
});

describe("recentUploadsSeries", () => {
  it("returns the latest uploads oldest first", () => {
    expect(recentUploadsSeries(videos, 2).map((video) => video.title)).toEqual(["Middle", "Newest"]);
  });
});

describe("YouTube links", () => {
  it("builds links only from plausible ids", () => {
    expect(youtubeWatchUrl("dQw4w9WgXcQ")).toBe("https://www.youtube.com/watch?v=dQw4w9WgXcQ");
    expect(youtubeWatchUrl("bad id!")).toBeNull();
    expect(youtubeChannelUrl("UCfixturechannel0000001")).toBe(
      "https://www.youtube.com/channel/UCfixturechannel0000001",
    );
    expect(youtubeChannelUrl("javascript:alert(1)")).toBeNull();
  });
});
