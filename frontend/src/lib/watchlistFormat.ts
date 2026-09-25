import type { EvidenceTone } from "@/components/common/EvidenceChip";
import { formatCompact } from "@/lib/format";
import { humanize } from "@/lib/labels";
import type { WatchChannel } from "@/api/watchlistTypes";

/**
 * Wording for the watchlist. The outlier rule is quoted from
 * `IntelligenceStore.analyze_outlier`: a video is compared with the median
 * latest views of at least five other watched videos from the same channel,
 * and flagged at 2.5 times that median or more.
 */

export const OUTLIER_THRESHOLD = 2.5;
export const OUTLIER_MINIMUM_PEERS = 5;

const OUTLIERS: Record<string, { label: string; tone: EvidenceTone }> = {
  possible_outlier: { label: "Possible outlier", tone: "warn" },
  observed_normal: { label: "Within normal range", tone: "info" },
  insufficient_evidence: { label: "Not enough peers", tone: "neutral" },
};

export function outlierLabel(status: unknown): { label: string; tone: EvidenceTone } {
  const key = String(status ?? "").trim();
  if (!key) return { label: "Not analysed", tone: "neutral" };
  return OUTLIERS[key] ?? { label: humanize(key), tone: "neutral" };
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
