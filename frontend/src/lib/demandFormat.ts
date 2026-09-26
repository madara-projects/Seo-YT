import type { EvidenceTone } from "@/components/common/EvidenceChip";
import { humanize, optionLabel } from "@/lib/labels";
import { DEMAND_FORMAT_OPTIONS, DEMAND_LANGUAGE_OPTIONS, DEMAND_REGION_OPTIONS } from "@/schemas/demand";

/**
 * Wording for the Demand explorer. The classification thresholds are quoted
 * from `analyze_demand`, so what the page says a level means is exactly what
 * the backend checked — never a softer or stronger claim.
 */

export interface ClassificationLabel {
  label: string;
  tone: EvidenceTone;
  meaning: string;
}

const CLASSIFICATIONS: Record<string, ClassificationLabel> = {
  strong_observed_interest: {
    label: "Strong observed interest",
    tone: "info",
    meaning:
      "8 or more sampled results from at least 4 channels, 3 or more published in the last 90 days, plus outlier or engagement evidence.",
  },
  active_topic: {
    label: "Active topic",
    tone: "info",
    meaning:
      "5 or more sampled results from at least 3 channels, 2 or more published in the last 90 days, with view data.",
  },
  emerging_signal: {
    label: "Emerging signal",
    tone: "info",
    meaning: "3 or more sampled results, with a recent upload or coverage from at least 2 channels.",
  },
  insufficient_evidence: {
    label: "Insufficient evidence",
    tone: "warn",
    meaning: "The sampled results were too sparse to classify interest in this topic.",
  },
};

export function classificationLabel(classification: unknown): ClassificationLabel {
  const key = String(classification ?? "").trim();
  return (
    CLASSIFICATIONS[key] ?? {
      label: key ? humanize(key) : "Unavailable",
      tone: "neutral",
      meaning: "No classification was recorded for this snapshot.",
    }
  );
}

const SIGNAL_NAMES: Record<string, string> = {
  sampled_relevant_results: "Sampled relevant results",
  recent_publications_90d: "Published in the last 90 days",
  independent_channels: "Independent channels",
  median_captured_views: "Median views at capture",
  watchlist_possible_outliers: "Watchlist possible outliers",
};

export function signalName(name: unknown): string {
  const key = String(name ?? "");
  return SIGNAL_NAMES[key] ?? humanize(key);
}

export function sourceLabel(source: unknown): { label: string; tone: EvidenceTone } {
  switch (source) {
    case "public_observation":
      return { label: "Public observation", tone: "info" };
    case "heuristic":
      return { label: "Local heuristic", tone: "warn" };
    default:
      return { label: "Unavailable", tone: "neutral" };
  }
}

/**
 * Snapshots researched from an idea carry the Ideas form's spellings (`in`,
 * `global`, `unknown`). Each maps to the option it means; the backend itself
 * substitutes `global` for a blank region and `unknown` for a blank format.
 */
const REGION_ALIASES = new Map([
  ["in", "india"],
  ["usa", "us"],
  ["gb", "uk"],
  ["global", ""],
]);
const FORMAT_ALIASES = new Map([["unknown", ""]]);

// A snapshot saved with no language was researched in English.
export const languageLabel = (value: unknown) => optionLabel(DEMAND_LANGUAGE_OPTIONS, value, "English (default)");
export const formatLabel = (value: unknown) =>
  optionLabel(DEMAND_FORMAT_OPTIONS, value, "Any format", FORMAT_ALIASES);
export const regionLabel = (value: unknown) =>
  optionLabel(DEMAND_REGION_OPTIONS, value, "Any region", REGION_ALIASES);
