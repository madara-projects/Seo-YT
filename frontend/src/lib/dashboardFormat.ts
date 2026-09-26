import { UNAVAILABLE } from "./utils";

/**
 * Dashboard value formatting.
 *
 * Kept as pure functions so the null/zero distinctions this product cares
 * about are directly testable: an absent value must render as "Unavailable"
 * and never as a zero. Watch time itself is formatted by `formatMinutes`.
 */

/** Opportunity is shown as a whole number; title quality to one decimal. */
export function roundOpportunity(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? Math.round(value) : null;
}

export function roundTitleScore(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value)
    ? Math.round(value * 10) / 10
    : null;
}

/** "39 / 100". The scale is printed only beside a real score, never as "Unavailable / 100". */
export function opportunityText(value: unknown): string {
  const score = roundOpportunity(value);
  return score === null ? UNAVAILABLE : `${score} / 100`;
}

/** "7.5 / 10", or Unavailable. */
export function titleScoreText(value: unknown): string {
  const score = roundTitleScore(value);
  return score === null ? UNAVAILABLE : `${score} / 10`;
}

export type RiskTone = "bad" | "warn" | "info" | "neutral";

export function riskTone(risk: string): RiskTone {
  switch (risk.toUpperCase()) {
    case "HIGH":
      return "bad";
    case "MEDIUM":
      return "warn";
    case "LOW":
      return "info";
    default:
      return "neutral";
  }
}

/** "Calculated from your 3 saved analyses." — singular/plural matters here. */
export function savedAnalysesCaption(totalRuns: unknown): string {
  if (typeof totalRuns !== "number") return "No saved analyses yet.";
  return `Calculated from your ${totalRuns.toLocaleString()} saved ${
    totalRuns === 1 ? "analysis" : "analyses"
  }.`;
}

export type WatchTimeSource = "channel" | "linked" | "none";

interface WatchTimeFields {
  latest_sync?: { current_28_days?: { estimatedMinutesWatched?: number | null } | null } | null;
  estimated_watch_minutes?: number | null;
  linked_videos_count?: number | null;
  linked_videos_with_watch_time?: number | null;
}

/** How many linked videos the fallback total adds up; older servers only sent the link count. */
function contributingVideos(owned: WatchTimeFields): number | null {
  const count = owned.linked_videos_with_watch_time ?? owned.linked_videos_count;
  return typeof count === "number" ? count : null;
}

/**
 * Where the Dashboard's watch-time figure comes from. With a channel sync the
 * backend reports the 28-day channel total; without one it falls back to the
 * total of the linked videos that have watch time. Those are different
 * measures, so each gets its own label, and a fallback of zero is not shown
 * as a measurement.
 */
export function watchTimeSource(owned: WatchTimeFields): WatchTimeSource {
  if (typeof owned.latest_sync?.current_28_days?.estimatedMinutesWatched === "number") {
    return "channel";
  }
  const minutes = owned.estimated_watch_minutes;
  const videos = contributingVideos(owned);
  if (typeof minutes === "number" && minutes > 0 && videos !== null && videos > 0) {
    return "linked";
  }
  return "none";
}

/** "Across 4 of your 19 linked videos …": says how many videos the total covers. */
export function linkedWatchCaption(owned: WatchTimeFields): string {
  const withTime = owned.linked_videos_with_watch_time;
  const linked = owned.linked_videos_count;
  const noun = (count: number) => (count === 1 ? "video" : "videos");
  const scope =
    typeof withTime === "number" && typeof linked === "number" && withTime !== linked
      ? `${withTime.toLocaleString()} of your ${linked.toLocaleString()} linked ${noun(linked)}`
      : typeof withTime === "number"
        ? `your ${withTime.toLocaleString()} linked ${noun(withTime)} with watch time`
        : `your ${(linked ?? 0).toLocaleString()} linked ${noun(linked ?? 0)}`;
  return `Across ${scope}, at each video's highest snapshot — not a 28-day channel total.`;
}
