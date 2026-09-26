import type { EvidenceTone } from "@/components/common/EvidenceChip";

/**
 * Status vocabulary for the background services. The backend reports short
 * machine states; these map them to a tone and wording a creator can act on.
 * Unknown states are shown verbatim rather than guessed at.
 */

export interface StateLabel {
  label: string;
  tone: EvidenceTone;
}

/** Every state `CloudSyncService` reports. */
const CLOUD_SYNC_STATES: Record<string, StateLabel> = {
  disabled: { label: "Disabled", tone: "neutral" },
  waiting: { label: "Waiting for first run", tone: "info" },
  running: { label: "Syncing", tone: "info" },
  "healthy/idle": { label: "Healthy", tone: "ok" },
  "offline/pending": { label: "Offline · changes queued", tone: "warn" },
  unconfigured: { label: "Not configured", tone: "warn" },
};

const COLLECTOR_STATES: Record<string, StateLabel> = {
  disabled: { label: "Disabled", tone: "neutral" },
  "dry-run": { label: "Dry run", tone: "info" },
  // The collector checks ownership against the connected channel's id, so
  // without one it has nothing it may read.
  unconfigured: { label: "Channel not connected", tone: "warn" },
  waiting: { label: "Waiting for first run", tone: "info" },
  running: { label: "Collecting", tone: "info" },
  "healthy/idle": { label: "Healthy", tone: "ok" },
  cooldown: { label: "Cooling down", tone: "warn" },
  error: { label: "Error", tone: "bad" },
};

function lookup(table: Record<string, StateLabel>, state: unknown): StateLabel {
  const key = String(state ?? "").trim();
  if (!key) return { label: "Unavailable", tone: "neutral" };
  return table[key] ?? { label: key, tone: "neutral" };
}

export function cloudSyncState(state: unknown): StateLabel {
  return lookup(CLOUD_SYNC_STATES, state);
}

export function collectorState(state: unknown): StateLabel {
  return lookup(COLLECTOR_STATES, state);
}

/**
 * What a "Sync now" achieved. The run answers HTTP 200 whatever happened, so
 * only a healthy result is reported as a success.
 */
export function cloudSyncRunOutcome(state: unknown): { kind: "success" | "warning" | "info"; message: string } {
  switch (state) {
    case "healthy/idle":
      return { kind: "success", message: "Cloud sync finished; your packages are in step." };
    case "offline/pending":
      return { kind: "warning", message: "Cloud sync couldn't finish. Changes stay queued and retry automatically." };
    case "running":
      return { kind: "info", message: "A cloud sync is already running." };
    case "disabled":
      return { kind: "warning", message: "Cloud sync is disabled, so nothing was synced." };
    case "unconfigured":
      return { kind: "warning", message: "Cloud sync isn't configured, so nothing was synced." };
    default:
      return { kind: "warning", message: `Cloud sync ended in an unexpected state (${cloudSyncState(state).label}).` };
  }
}

/** Gemini's failure categories in words; anything else is shown as stored. */
const GEMINI_FAILURES: Record<string, string> = {
  request_budget_exhausted: "Gemini call limit for this request reached",
};

export function geminiFailureLabel(category: unknown): string {
  const key = String(category ?? "").trim();
  return GEMINI_FAILURES[key] ?? key.replaceAll("_", " ");
}
