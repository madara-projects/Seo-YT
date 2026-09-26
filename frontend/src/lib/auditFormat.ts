import type { EvidenceTone } from "@/components/common/EvidenceChip";
import { humanize, type LabelledOption } from "@/lib/labels";
import type { AuditCandidate, AuditComparison } from "@/api/auditTypes";

/**
 * Wording for published-video audits. Each state's meaning restates the
 * condition `build_published_audit` checks, so the page never claims more
 * than the audit established — and never that anything caused anything.
 */

interface StateLabel {
  label: string;
  tone: EvidenceTone;
  meaning: string;
}

const AUDIT_STATES: Record<string, StateLabel> = {
  not_run: {
    label: "Not audited",
    tone: "neutral",
    meaning: "No audit has been saved for this video yet.",
  },
  not_enough_data: {
    label: "Not enough data",
    tone: "neutral",
    meaning: "The video's published metadata hasn't been captured, so nothing could be compared.",
  },
  collecting_evidence: {
    label: "Collecting evidence",
    tone: "info",
    meaning: "The published metadata was compared; no performance snapshot exists yet.",
  },
  observable: {
    label: "Observable",
    tone: "info",
    meaning: "Current counts are available, but no 24-hour, 7-day or 28-day window has completed.",
  },
  mature_observation: {
    label: "Mature observation",
    tone: "info",
    meaning: "At least one completed 24-hour, 7-day or 28-day window is available.",
  },
  actionable_observation: {
    label: "Actionable observation",
    tone: "ok",
    meaning: "A completed window plus enough comparable videos from your channel to compare against.",
  },
  inconclusive: {
    label: "Inconclusive",
    tone: "warn",
    meaning: "Snapshots exist, but none could be used as an observation.",
  },
};

export function auditStateLabel(state: unknown): StateLabel {
  const key = String(state ?? "").trim();
  return (
    AUDIT_STATES[key] ?? {
      label: key ? humanize(key) : "Unknown",
      tone: "neutral",
      meaning: "This audit state isn't recognised.",
    }
  );
}

const EVIDENCE_STATES: Record<string, { label: string; tone: EvidenceTone }> = {
  unavailable: { label: "No performance data", tone: "neutral" },
  observed: { label: "Current counts", tone: "info" },
  mature: { label: "Completed window", tone: "ok" },
};

export function evidenceStateLabel(state: unknown): { label: string; tone: EvidenceTone } {
  return EVIDENCE_STATES[String(state ?? "")] ?? { label: "No performance data", tone: "neutral" };
}

const FIELD_STATES: Record<string, { label: string; tone: EvidenceTone }> = {
  exact_match: { label: "Matches", tone: "ok" },
  changed: { label: "Changed", tone: "warn" },
  missing: { label: "Missing", tone: "warn" },
  unknown: { label: "Unknown", tone: "neutral" },
  unavailable: { label: "Unavailable", tone: "neutral" },
};

export function fieldStateLabel(state: unknown): { label: string; tone: EvidenceTone } {
  return FIELD_STATES[String(state ?? "")] ?? { label: "Unavailable", tone: "neutral" };
}

export function fieldName(field: string): string {
  return { title: "Title", description: "Description", tags: "Tags", hashtags: "Hashtags" }[field] ?? humanize(field);
}

/** A compared value as text; an empty field is null, never "". */
export function comparisonText(value: unknown): string | null {
  if (Array.isArray(value)) {
    const items = value.map((item) => String(item).trim()).filter(Boolean);
    return items.length ? items.join(", ") : null;
  }
  const text = String(value ?? "").trim();
  return text || null;
}

/**
 * How a field on YouTube compares with what the creator meant to publish:
 * the package they explicitly selected when one was recorded (the backend's
 * `selection_attribution`), otherwise the generated package.
 */
export function publishedFieldState(item: AuditComparison, selectionRecorded: boolean): string | undefined {
  return selectionRecorded ? item.selected_to_published : item.generated_to_published;
}

/**
 * The metadata check's headline. The legacy page compared against "match",
 * a value the backend never returns, so it always reported differences.
 */
export function metadataVerdict(
  comparisons: AuditComparison[],
  selectionRecorded = false,
): { label: string; tone: EvidenceTone; text: string } {
  const states = comparisons.map((item) => publishedFieldState(item, selectionRecorded));
  const target = selectionRecorded ? "the package you selected" : "the saved package";
  if (!states.length || states.every((state) => state === "unavailable")) {
    return {
      label: "YouTube data unavailable",
      tone: "neutral",
      text: "The published title, description and tags weren't captured for this audit.",
    };
  }
  if (states.every((state) => state === "exact_match")) {
    return {
      label: selectionRecorded ? "Matches your selection" : "Matches your package",
      tone: "ok",
      text: `The title, description, tags and hashtags on YouTube match ${target}.`,
    };
  }
  const differing = comparisons
    .filter((item) => publishedFieldState(item, selectionRecorded) !== "exact_match")
    .map((item) => fieldName(item.field).toLowerCase());
  return {
    label: "Differences found",
    tone: "warn",
    text: `What's on YouTube differs from ${target} in: ${differing.join(", ")}.`,
  };
}

export function findingSeverity(severity: unknown): { label: string; tone: EvidenceTone } {
  return severity === "review" ? { label: "Review", tone: "warn" } : { label: "Note", tone: "info" };
}

export function candidateTitle(candidate: Pick<AuditCandidate, "youtube_metadata" | "selected_title" | "package_topic" | "youtube_video_id">): string {
  return (
    candidate.youtube_metadata?.title ||
    candidate.selected_title ||
    candidate.package_topic ||
    candidate.youtube_video_id
  );
}

/** 24h → "24-hour window"; `current` is a running count, not a window. */
export function windowLabel(window: unknown): string {
  switch (window) {
    case "24h":
      return "24-hour window";
    case "7d":
      return "7-day window";
    case "28d":
      return "28-day window";
    case "current":
      return "Current counts";
    default:
      return "Unknown window";
  }
}

export const AUDIT_STATE_FILTERS: LabelledOption[] = [
  { value: "", label: "All audit states" },
  ...Object.entries(AUDIT_STATES).map(([value, state]) => ({ value, label: state.label })),
];

export const AUDIT_EVIDENCE_FILTERS: LabelledOption[] = [
  { value: "", label: "All evidence" },
  { value: "unavailable", label: "No performance data" },
  { value: "observed", label: "Current counts" },
  { value: "mature", label: "Completed window" },
];
