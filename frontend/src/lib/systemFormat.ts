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

const CLOUD_SYNC_STATES: Record<string, StateLabel> = {
  disabled: { label: "Disabled", tone: "neutral" },
  waiting: { label: "Waiting for first run", tone: "info" },
  running: { label: "Syncing", tone: "info" },
  "healthy/idle": { label: "Healthy", tone: "ok" },
  "offline/pending": { label: "Offline · changes queued", tone: "warn" },
  unconfigured: { label: "Not configured", tone: "warn" },
  cooldown: { label: "Cooling down", tone: "warn" },
  error: { label: "Error", tone: "bad" },
};

const COLLECTOR_STATES: Record<string, StateLabel> = {
  disabled: { label: "Disabled", tone: "neutral" },
  "dry-run": { label: "Dry run", tone: "info" },
  unconfigured: { label: "Not configured", tone: "warn" },
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
