import type { EvidenceTone } from "@/components/common/EvidenceChip";
import type { OpportunityBreakdown, OpportunityInput } from "@/api/opportunityTypes";
import { savedAnalysesCaption } from "./dashboardFormat";
import { asArray, asObject } from "./utils";

/**
 * Opportunity Score wording and parsing.
 *
 * The score is a local heuristic built from five research inputs. Nothing
 * here may present it as a prediction of views, reach or CTR.
 */

export const OPPORTUNITY_STATEMENT =
  "A local heuristic that weighs five signals from this idea's YouTube research. It is not a prediction of views, reach or click-through rate.";

export const NO_STORED_BREAKDOWN =
  "This package was saved before score breakdowns were stored, so its inputs are not shown.";

/** The heuristic's inputs and weights, as gap_engine.OPPORTUNITY_INPUTS defines them. */
export const OPPORTUNITY_INPUT_WEIGHTS = [
  { name: "Demand (view velocity)", weight: 0.35, detail: "Views per day of the top research videos" },
  { name: "Competition room", weight: 0.25, detail: "100 minus a competition heuristic" },
  { name: "Keyword gaps", weight: 0.2, detail: "Script keywords competitors underuse" },
  { name: "Small-channel breakouts", weight: 0.1, detail: "Top videos from small channels with 100K+ views" },
  { name: "Research relevance", weight: 0.1, detail: "How many research queries found each top video" },
] as const;

const SOURCES: Record<string, { label: string; tone: EvidenceTone }> = {
  youtube_measured: { label: "Measured from YouTube results", tone: "info" },
  local_heuristic: { label: "Local heuristic", tone: "warn" },
  missing_default: { label: "Default: data missing", tone: "neutral" },
};

export function sourceLabel(source: string): { label: string; tone: EvidenceTone } {
  return SOURCES[source] ?? { label: "Unknown source", tone: "neutral" };
}

const NO_CONFIDENCE = { label: "No input confidence", tone: "neutral" } as const;
const CONFIDENCE: Record<string, { label: string; tone: EvidenceTone }> = {
  high: { label: "High input confidence", tone: "info" },
  medium: { label: "Medium input confidence", tone: "warn" },
  low: { label: "Low input confidence", tone: "warn" },
  none: NO_CONFIDENCE,
};

/** How complete the inputs were, not how likely the video is to get views. */
export function confidenceLabel(confidence: string): { label: string; tone: EvidenceTone } {
  return CONFIDENCE[confidence.toLowerCase()] ?? NO_CONFIDENCE;
}

/** 0.35 → "35%". */
export function weightText(weight: number): string {
  return `${Math.round(weight * 100)}%`;
}

/** "75 / 100 × 35% = 26.3 points": the whole calculation for one input. */
export function contributionText(input: OpportunityInput): string {
  return `${Math.round(input.value)} / 100 × ${weightText(input.weight)} = ${input.contribution.toFixed(1)} points`;
}

function finite(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/**
 * The stored breakdown, or null when there is none. Older packages have none,
 * and the UI says so rather than rebuilding one from guesses.
 */
export function parseOpportunityBreakdown(value: unknown): OpportunityBreakdown | null {
  const raw = asObject(value);
  const inputs = asArray<unknown>(raw.inputs)
    .map((item) => asObject(item))
    .filter(
      (item) =>
        typeof item.name === "string" &&
        finite(item.value) !== null &&
        finite(item.weight) !== null &&
        finite(item.contribution) !== null,
    )
    .map(
      (item): OpportunityInput => ({
        key: String(item.key ?? item.name),
        name: String(item.name),
        value: item.value as number,
        weight: item.weight as number,
        contribution: item.contribution as number,
        source: String(item.source ?? ""),
        basis: String(item.basis ?? ""),
      }),
    );
  if (!inputs.length) return null;
  return {
    version: typeof raw.version === "string" ? raw.version : undefined,
    statement: typeof raw.statement === "string" && raw.statement.trim() ? raw.statement : OPPORTUNITY_STATEMENT,
    score: finite(raw.score),
    inputs,
    warnings: asArray<unknown>(raw.warnings).filter((item): item is string => typeof item === "string" && Boolean(item)),
    confidence: typeof raw.confidence === "string" ? raw.confidence : "none",
    confidence_reason: typeof raw.confidence_reason === "string" ? raw.confidence_reason : undefined,
    inputs_with_data: finite(raw.inputs_with_data) ?? undefined,
    top_videos_used: finite(raw.top_videos_used) ?? undefined,
    research_results: finite(raw.research_results),
  };
}

/** The Dashboard's average card: an average of a heuristic, said plainly. */
export function averageHeuristicCaption(totalRuns: unknown): string {
  return `Averages a local heuristic, not a prediction of views. ${savedAnalysesCaption(totalRuns)}`;
}

const CALIBRATION: Record<string, { label: string; tone: EvidenceTone }> = {
  insufficient_evidence: { label: "Not enough evidence yet", tone: "neutral" },
  no_clear_relationship: { label: "No clear relationship", tone: "warn" },
  higher_scores_did_better: { label: "Higher scores did better", tone: "info" },
  lower_scores_did_better: { label: "Lower scores did better", tone: "bad" },
};

export function calibrationStatus(status: unknown): { label: string; tone: EvidenceTone } {
  return CALIBRATION[String(status ?? "")] ?? { label: "Unavailable", tone: "neutral" };
}

export const RECOMMENDATION_LABEL: Record<string, string> = {
  keep: "Keep",
  recalibrate: "Recalibrate",
  retire: "Retire",
};

export const EXCLUSION_LABEL: Record<string, string> = {
  not_ownership_verified: "not ownership-verified",
  missing_format_or_language: "missing format or language",
  score_not_measured: "score not measured",
  no_completed_snapshot: "without a completed snapshot",
};
