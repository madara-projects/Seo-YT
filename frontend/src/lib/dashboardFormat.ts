/**
 * Dashboard value formatting.
 *
 * Kept as pure functions so the null/zero distinctions this product cares
 * about are directly testable: a connected channel reporting zero is a
 * measurement and must render as "0 mins", while an absent value must render
 * as "Unavailable" and never as a zero.
 */

export function formatWatchTime(minutes: unknown, isConnected: boolean): string {
  if (typeof minutes === "number" && minutes >= 60) return `${(minutes / 60).toFixed(1)} hrs`;
  if (typeof minutes === "number" && minutes > 0) return `${minutes} mins`;
  if (isConnected && minutes === 0) return "0 mins";
  return "Unavailable";
}

/** Opportunity is shown as a whole number; title quality to one decimal. */
export function roundOpportunity(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? Math.round(value) : null;
}

export function roundTitleScore(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value)
    ? Math.round(value * 10) / 10
    : null;
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

/**
 * Where the Dashboard's watch-time figure comes from. With a channel sync the
 * backend reports the 28-day channel total; without one it falls back to the
 * total of linked videos at their latest snapshots. Those are different
 * measures, so each gets its own label, and a fallback of zero is not shown
 * as a measurement.
 */
export function watchTimeSource(owned: {
  latest_sync?: { current_28_days?: { estimatedMinutesWatched?: number | null } } | null;
  estimated_watch_minutes?: number | null;
  linked_videos_count?: number | null;
}): WatchTimeSource {
  if (typeof owned.latest_sync?.current_28_days?.estimatedMinutesWatched === "number") {
    return "channel";
  }
  const minutes = owned.estimated_watch_minutes;
  const linked = owned.linked_videos_count;
  if (typeof minutes === "number" && minutes > 0 && typeof linked === "number" && linked > 0) {
    return "linked";
  }
  return "none";
}
