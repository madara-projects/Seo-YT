import type { HistoryRun } from "@/api/historyTypes";

/**
 * Timestamp formatting for saved packages.
 *
 * The legacy UI hard-coded Asia/Kolkata with an " IST" suffix, matching the
 * backend's `WIN_ENGINE_CREATOR_TIMEZONE` default. That is preserved here so
 * migrating does not silently re-label every stored timestamp with a
 * different zone. If the creator timezone ever becomes configurable, this is
 * the single place to read it from.
 */
const DISPLAY_TIME_ZONE = "Asia/Kolkata";
const DISPLAY_LOCALE = "en-IN";

export function historyDate(value?: string | null): string {
  if (!value) return "Unknown";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Unknown";

  return `${parsed.toLocaleString(DISPLAY_LOCALE, {
    timeZone: DISPLAY_TIME_ZONE,
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })} IST`;
}

/**
 * Search matching, ported verbatim: case-insensitive substring across title,
 * query, content angle, and intent.
 */
export function matchesQuery(run: HistoryRun, query: string): boolean {
  const needle = query.trim().toLowerCase();
  if (!needle) return true;

  return [run.title, run.query, run.content_angle, run.intent].some((value) =>
    String(value ?? "")
      .toLowerCase()
      .includes(needle),
  );
}

export function runTitle(run: HistoryRun): string {
  return run.title || run.query || "Untitled package";
}

/** "3 saved packages" / "1 saved package" */
export function savedCountLabel(total: number): string {
  return `${total} saved ${total === 1 ? "package" : "packages"}`;
}

/** Result summary beneath the toolbar, matching the legacy wording. */
export function resultSummary(total: number, visible: number, query: string): string {
  const trimmed = query.trim();
  if (trimmed) return `${visible} of ${total} packages match “${trimmed}”`;
  return `${total} package${total === 1 ? "" : "s"} available`;
}
