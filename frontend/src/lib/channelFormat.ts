import type { ChannelMetrics, ChannelVideo } from "@/api/systemTypes";
import { engagementRate, percentChange, toFiniteNumber } from "./format";

/**
 * Derived views of a channel sync payload, kept pure so the rules are tested:
 * a metric YouTube did not return stays null (never 0), and a comparison is
 * only offered when both 28-day windows carry the metric.
 */

export interface PeriodMetric {
  key: keyof ChannelMetrics;
  label: string;
  current: number | null;
  previous: number | null;
  change: number | null;
}

const PERIOD_METRICS: { key: keyof ChannelMetrics; label: string }[] = [
  { key: "views", label: "Views" },
  { key: "estimatedMinutesWatched", label: "Watch time" },
  { key: "averageViewDuration", label: "Avg view duration" },
  { key: "subscribersGained", label: "Subscribers gained" },
  { key: "likes", label: "Likes" },
  { key: "comments", label: "Comments" },
];

export function periodComparison(
  current: ChannelMetrics | undefined,
  previous: ChannelMetrics | undefined,
): PeriodMetric[] {
  return PERIOD_METRICS.map(({ key, label }) => {
    const now = toFiniteNumber(current?.[key]);
    const before = toFiniteNumber(previous?.[key]);
    return { key, label, current: now, previous: before, change: percentChange(now, before) };
  });
}

/** True when the Analytics query returned nothing for the window. */
export function hasMetrics(metrics: ChannelMetrics | undefined): boolean {
  return Boolean(metrics && Object.values(metrics).some((value) => toFiniteNumber(value) !== null));
}

export type VideoSort = "newest" | "views" | "engagement";

export function sortVideos(videos: ChannelVideo[], sort: VideoSort): ChannelVideo[] {
  const copy = [...videos];
  if (sort === "views") {
    return copy.sort((a, b) => (toFiniteNumber(b.views) ?? -1) - (toFiniteNumber(a.views) ?? -1));
  }
  if (sort === "engagement") {
    // Unknown engagement sorts last, below a measured zero.
    const rate = (video: ChannelVideo) => engagementRate(video.likes, video.comments, video.views);
    return copy.sort((a, b) => {
      const first = rate(a);
      const second = rate(b);
      if (first === null || second === null) return first === null ? (second === null ? 0 : 1) : -1;
      return second - first;
    });
  }
  return copy.sort((a, b) => String(b.published_at ?? "").localeCompare(String(a.published_at ?? "")));
}

/** The latest uploads, oldest first, for a left-to-right chart. */
export function recentUploadsSeries(videos: ChannelVideo[], count = 12): ChannelVideo[] {
  return sortVideos(videos, "newest").slice(0, count).reverse();
}

export function youtubeWatchUrl(videoId?: string): string | null {
  return videoId && /^[A-Za-z0-9_-]{6,20}$/.test(videoId)
    ? `https://www.youtube.com/watch?v=${videoId}`
    : null;
}

export function youtubeChannelUrl(channelId?: string): string | null {
  return channelId && /^[A-Za-z0-9_-]{10,40}$/.test(channelId)
    ? `https://www.youtube.com/channel/${channelId}`
    : null;
}
