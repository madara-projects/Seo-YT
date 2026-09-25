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

/** Date only, in the same zone as `historyDate`: "24 Sept 2026". */
export function shortDate(value?: string | null): string {
  if (!value) return "Unknown";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Unknown";

  return parsed.toLocaleDateString(DISPLAY_LOCALE, {
    timeZone: DISPLAY_TIME_ZONE,
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

const ISO_TIMESTAMP = /\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?/g;

/**
 * Backend explanations embed raw timestamps ("Most recent observed
 * publication: 2026-09-19T14:03:11Z."); shows each as a date instead.
 */
export function withReadableDates(text: string): string {
  return text.replace(ISO_TIMESTAMP, (match) => {
    const date = shortDate(match);
    return date === "Unknown" ? match : date;
  });
}

/** The greeting for the current hour in the creator's zone. */
export function greetingFor(date: Date = new Date()): string {
  const hour = Number(
    date.toLocaleString("en-US", { timeZone: DISPLAY_TIME_ZONE, hour: "numeric", hourCycle: "h23" }),
  );
  if (hour < 5) return "Working late";
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
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
