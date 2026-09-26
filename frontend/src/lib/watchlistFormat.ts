import type { EvidenceTone } from "@/components/common/EvidenceChip";
import { formatCompact } from "@/lib/format";
import { humanize } from "@/lib/labels";
import type { WatchChannel } from "@/api/watchlistTypes";

/**
 * Wording for the watchlist. The outlier rule is quoted from
 * `IntelligenceStore.analyze_outlier`: a video's views per day are compared
 * with those of at least five other watched videos from the same channel,
 * published within 180 days of it and measured at a similar age, and it is
 * flagged at 2.5 times their median or more.
 */

export const OUTLIER_THRESHOLD = 2.5;
export const OUTLIER_MINIMUM_PEERS = 5;
export const OUTLIER_PEER_WINDOW_DAYS = 180;
/** The backend calls anything up to this long a Short. */
const SHORT_MAX_SECONDS = 180;

const OUTLIERS: Record<string, { label: string; tone: EvidenceTone }> = {
  possible_outlier: { label: "Possible outlier", tone: "warn" },
  observed_normal: { label: "Within normal range", tone: "info" },
  // Too few peers is one cause; an unknown channel, view count or publish time
  // are others. The analysis's own explanation says which.
  insufficient_evidence: { label: "Not enough evidence", tone: "neutral" },
  not_analyzed: { label: "Not analysed", tone: "neutral" },
};

export function outlierLabel(status: unknown): { label: string; tone: EvidenceTone } {
  const key = String(status ?? "").trim();
  if (!key) return { label: "Not analysed", tone: "neutral" };
  return OUTLIERS[key] ?? { label: humanize(key), tone: "neutral" };
}

/**
 * 2.45 → "2.45×". Two decimals, as the backend rounds it: one decimal would
 * show 2.45 as "2.5×" beside "Within normal range" and a 2.5× threshold.
 */
export function formatMultiplier(value: number): string {
  return `${value.toFixed(2)}×`;
}

let languageNames: Intl.DisplayNames | null | undefined;

/**
 * YouTube stores a video's language as a code (`ta`, `en-us`); shows its
 * name. `unknown` (no language set on the video) stays unknown.
 */
export function languageName(code: unknown): string {
  const value = String(code ?? "").trim();
  if (!value || value.toLowerCase() === "unknown") return "Unknown";
  if (languageNames === undefined) {
    try {
      languageNames = new Intl.DisplayNames(["en"], { type: "language" });
    } catch {
      languageNames = null;
    }
  }
  try {
    const name = languageNames?.of(value);
    if (name && name.toLowerCase() !== value.toLowerCase()) return name;
  } catch {
    /* Not a language code: show it as stored. */
  }
  return value;
}

/** A channel can hide its subscriber count; that reads as unavailable, not zero. */
export function channelCounts(channel: Pick<WatchChannel, "subscriber_count" | "video_count">): string {
  const subscribers =
    typeof channel.subscriber_count === "number"
      ? `${formatCompact(channel.subscriber_count)} subscribers`
      : "Subscribers unavailable";
  const uploads =
    typeof channel.video_count === "number" ? `${formatCompact(channel.video_count)} videos` : "Videos unavailable";
  return `${subscribers} · ${uploads}`;
}

export function watchStateLabel(state: unknown): { label: string; tone: EvidenceTone } {
  return state === "archived" ? { label: "Archived", tone: "neutral" } : { label: "Active", tone: "ok" };
}

/** `youtube_shorts` and `long_form` are inferred from the video's duration. */
export function watchFormatLabel(format: unknown): string {
  if (format === "youtube_shorts") return "Short";
  if (format === "long_form") return "Long form";
  return "Unknown format";
}

/** Says the format is an inference from duration, not something YouTube reported. */
export function watchFormatBasis(format: unknown): string | null {
  if (format === "youtube_shorts" || format === "long_form") {
    return `Inferred from its duration: up to ${SHORT_MAX_SECONDS / 60} minutes counts as a Short.`;
  }
  return null;
}
