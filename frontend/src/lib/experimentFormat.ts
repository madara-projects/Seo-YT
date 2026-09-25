import type { EvidenceTone } from "@/components/common/EvidenceChip";
import { humanize, optionLabel } from "@/lib/labels";
import { formatNumber } from "@/lib/utils";
import {
  EXPERIMENT_METRIC_OPTIONS,
  EXPERIMENT_VARIABLE_OPTIONS,
  EXPERIMENT_WINDOW_OPTIONS,
} from "@/schemas/experiment";
import type { ExperimentStatus } from "@/api/experimentTypes";

/**
 * Wording and rules for structured experiments. Transitions restate
 * `STATUS_TRANSITIONS` in `audit_experiment_store`, and result states quote
 * `compare_experiment`, so the page offers only what the backend accepts and
 * claims no more than it computed.
 */

const STATUSES: Record<ExperimentStatus, { label: string; tone: EvidenceTone }> = {
  draft: { label: "Draft", tone: "neutral" },
  planned: { label: "Planned", tone: "info" },
  active: { label: "Active", tone: "ok" },
  paused: { label: "Paused", tone: "warn" },
  completed: { label: "Completed", tone: "ok" },
  cancelled: { label: "Cancelled", tone: "neutral" },
  inconclusive: { label: "Inconclusive", tone: "warn" },
};

export function experimentStatusLabel(status: unknown): { label: string; tone: EvidenceTone } {
  const key = String(status ?? "");
  return STATUSES[key as ExperimentStatus] ?? { label: key ? humanize(key) : "Unknown", tone: "neutral" };
}

export function modeLabel(mode: unknown): { label: string; tone: EvidenceTone } {
  return mode === "observational"
    ? { label: "Observational", tone: "warn" }
    : { label: "Planned experiment", tone: "info" };
}

export const variableLabel = (value: unknown) => optionLabel(EXPERIMENT_VARIABLE_OPTIONS, value, "Unknown variable");
export const metricLabel = (value: unknown) => optionLabel(EXPERIMENT_METRIC_OPTIONS, value, "Unknown metric");
export const observationWindowLabel = (value: unknown) => optionLabel(EXPERIMENT_WINDOW_OPTIONS, value, "Unknown window");

const TRANSITIONS: Record<ExperimentStatus, ExperimentStatus[]> = {
  draft: ["planned", "cancelled"],
  planned: ["active", "paused", "cancelled"],
  active: ["completed", "paused", "inconclusive", "cancelled"],
  paused: ["active", "completed", "inconclusive", "cancelled"],
  completed: [],
  cancelled: [],
  inconclusive: [],
};

export interface Transition {
  to: ExperimentStatus;
  label: string;
  /** The step that moves the experiment forward. */
  primary: boolean;
  /** Completed, inconclusive and cancelled can never be left again. */
  final: boolean;
}

export function isClosed(status: unknown): boolean {
  return status === "completed" || status === "cancelled" || status === "inconclusive";
}

export function transitionsFrom(status: unknown): Transition[] {
  const from = String(status ?? "") as ExperimentStatus;
  return (TRANSITIONS[from] ?? []).map((to, index) => ({
    to,
    label:
      to === "planned"
        ? "Mark planned"
        : to === "active"
          ? from === "paused"
            ? "Resume"
            : "Start"
          : to === "paused"
            ? "Pause"
            : to === "completed"
              ? "Mark completed"
              : to === "inconclusive"
                ? "Mark inconclusive"
                : "Cancel experiment",
    primary: index === 0,
    final: isClosed(to),
  }));
}

const RESULTS: Record<string, { label: string; tone: EvidenceTone }> = {
  insufficient_evidence: { label: "Insufficient evidence", tone: "warn" },
  directional_variant: { label: "Variant ahead", tone: "info" },
  directional_control: { label: "Control ahead", tone: "info" },
  inconclusive: { label: "Inconclusive", tone: "neutral" },
  mixed_results: { label: "Mixed results", tone: "warn" },
  observational_pattern: { label: "Observational pattern", tone: "info" },
};

export function resultStateLabel(state: unknown): { label: string; tone: EvidenceTone } {
  const key = String(state ?? "");
  return RESULTS[key] ?? { label: key ? humanize(key) : "Not compared", tone: "neutral" };
}

export function directionLabel(direction: unknown): string {
  return direction === "variant" ? "Variant higher" : direction === "control" ? "Control higher" : "No clear direction";
}

/** Percentages for the two rate metrics, whole counts for the rest. */
export function metricValue(metric: unknown, value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "Unavailable";
  if (metric === "average_view_percentage" || metric === "engagement_rate") return `${value.toFixed(1)}%`;
  return formatNumber(Math.round(value));
}

export function relativeDifference(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "Unavailable";
  return `${value > 0 ? "+" : value < 0 ? "−" : ""}${Math.abs(value).toFixed(1)}%`;
}

/** `compare_experiment` never counts fewer than five per group, whatever was entered. */
export function minimumPerGroup(minimum: unknown): number {
  return Math.max(5, typeof minimum === "number" && Number.isFinite(minimum) ? minimum : 5);
}
