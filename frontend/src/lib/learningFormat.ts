import type { RetentionReason, SimilarPair, StudioTest } from "@/api/learningTypes";

/** YouTube Studio's names for YouTube Analytics' `insightTrafficSourceType` values. */
const TRAFFIC_SOURCE_LABELS: Record<string, string> = {
  ADVERTISING: "YouTube advertising",
  ANNOTATION: "Annotations",
  CAMPAIGN_CARD: "Campaign cards",
  END_SCREEN: "End screens",
  EXT_URL: "External",
  HASHTAGS: "Hashtag pages",
  LIVE_REDIRECT: "Live redirect",
  NO_LINK_EMBEDDED: "Embedded players",
  NO_LINK_OTHER: "Direct or unknown",
  NOTIFICATION: "Notifications",
  PLAYLIST: "Playlists",
  PRODUCT_PAGE: "Product pages",
  PROMOTED: "Promoted",
  RELATED_VIDEO: "Suggested videos",
  SHORTS: "Shorts feed",
  SHORTS_CONTENT_LINKS: "Shorts content links",
  SOUND_PAGE: "Sound pages",
  SUBSCRIBER: "Browse features",
  VIDEO_REMIXES: "Remixes",
  YT_CHANNEL: "Channel pages",
  YT_OTHER_PAGE: "Other YouTube features",
  YT_PLAYLIST_PAGE: "Playlist pages",
  YT_SEARCH: "YouTube search",
};

export function trafficSourceLabel(source: string | null | undefined): string {
  const key = String(source ?? "").trim().toUpperCase();
  if (!key) return "Unknown source";
  if (TRAFFIC_SOURCE_LABELS[key]) return TRAFFIC_SOURCE_LABELS[key];
  const words = key.toLowerCase().split("_").filter(Boolean).join(" ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

const RETENTION_REASONS: Record<RetentionReason, string> = {
  not_connected: "Channel not connected",
  not_channel_video: "Not the channel's own video",
  missing_scope: "Analytics permission missing",
  no_data_yet: "No retention data yet",
  api_error: "YouTube request failed",
};

export function retentionReasonLabel(reason: string | null | undefined): string {
  return RETENTION_REASONS[reason as RetentionReason] ?? "Unavailable";
}

/** The overview's similar pairs where both packages are among those chosen. */
export function chosenSimilarPairs(pairs: SimilarPair[], chosen: string[]): SimilarPair[] {
  const picked = new Set(chosen);
  return pairs.filter((pair) => picked.has(pair.first) && picked.has(pair.second));
}

export function studioStatusLabel(test: Pick<StudioTest, "status" | "linked_video">): string {
  if (test.status === "completed") return "Result recorded";
  if (test.status === "linked" && test.linked_video) return "Linked to the published video";
  return "Prepared, not linked";
}

export function studioResultText(test: Pick<StudioTest, "result" | "winner_variant">): string | null {
  const result = test.result;
  if (!result?.outcome) return null;
  const shares = Object.entries(result.watch_time_share ?? {})
    .map(([label, share]) => `${label} ${share.toFixed(1)}%`)
    .join(" · ");
  const headline = result.outcome === "winner" ? `Studio picked ${test.winner_variant ?? "a variant"}` : "No clear winner";
  return shares ? `${headline} · watch-time share ${shares}` : headline;
}

/** Seconds as the clock YouTube shows (1:05, 1:02:03). */
export function clockTime(seconds: number | null | undefined): string {
  if (typeof seconds !== "number" || !Number.isFinite(seconds)) return "";
  const total = Math.max(0, Math.round(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = String(total % 60).padStart(2, "0");
  return hours ? `${hours}:${String(minutes).padStart(2, "0")}:${secs}` : `${minutes}:${secs}`;
}
