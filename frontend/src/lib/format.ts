import { UNAVAILABLE } from "./utils";

/**
 * Number and time formatting for the channel and system pages.
 *
 * Every helper returns the "Unavailable" fallback for a missing value rather
 * than a zero, for the same reason as `displayValue`: an absent measurement
 * and a measured zero are different facts.
 */

export function toFiniteNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "" || typeof value === "boolean") {
    return null;
  }
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

const compactFormatter = new Intl.NumberFormat("en", {
  notation: "compact",
  maximumFractionDigits: 1,
});

/** 1234 → "1.2K". Small values stay exact. */
export function formatCompact(value: unknown, fallback: string = UNAVAILABLE): string {
  const number = toFiniteNumber(value);
  if (number === null) return fallback;
  return Math.abs(number) < 10_000 ? number.toLocaleString() : compactFormatter.format(number);
}

/**
 * Change from `previous` to `current` as a percentage, or null when it cannot
 * be computed honestly (a missing side, or a zero baseline where any change
 * would read as infinite).
 */
export function percentChange(current: unknown, previous: unknown): number | null {
  const now = toFiniteNumber(current);
  const before = toFiniteNumber(previous);
  if (now === null || before === null || before === 0) return null;
  return ((now - before) / Math.abs(before)) * 100;
}

/** 12.345 → "+12.3%", -3 → "−3.0%" (a true minus sign, which screen readers voice). */
export function formatSignedPercent(value: number): string {
  const rounded = Math.round(value * 10) / 10;
  if (rounded === 0) return "0.0%";
  return `${rounded > 0 ? "+" : "−"}${Math.abs(rounded).toFixed(1)}%`;
}

/** 205 → "3:25", 3725 → "1:02:05". */
export function formatSeconds(value: unknown, fallback: string = UNAVAILABLE): string {
  const number = toFiniteNumber(value);
  if (number === null || number < 0) return fallback;
  const total = Math.round(number);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  const ss = String(seconds).padStart(2, "0");
  return hours > 0 ? `${hours}:${String(minutes).padStart(2, "0")}:${ss}` : `${minutes}:${ss}`;
}

/** Watch time from minutes: 45 → "45 mins", 750 → "12.5 hrs". */
export function formatMinutes(value: unknown, fallback: string = UNAVAILABLE): string {
  const minutes = toFiniteNumber(value);
  if (minutes === null || minutes < 0) return fallback;
  if (minutes >= 60) return `${(minutes / 60).toLocaleString(undefined, { maximumFractionDigits: 1 })} hrs`;
  return `${Math.round(minutes).toLocaleString()} mins`;
}

export function formatBytes(value: unknown, fallback: string = UNAVAILABLE): string {
  const bytes = toFiniteNumber(value);
  if (bytes === null || bytes < 0) return fallback;
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let size = bytes / 1024;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toLocaleString(undefined, { maximumFractionDigits: size < 10 ? 1 : 0 })} ${units[unit]}`;
}

/** 11520 → "3 h 12 min". */
export function formatUptime(value: unknown, fallback: string = UNAVAILABLE): string {
  const seconds = toFiniteNumber(value);
  if (seconds === null || seconds < 0) return fallback;
  const days = Math.floor(seconds / 86_400);
  const hours = Math.floor((seconds % 86_400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days} d ${hours} h`;
  if (hours > 0) return `${hours} h ${minutes} min`;
  if (minutes > 0) return `${minutes} min`;
  return `${Math.floor(seconds)} s`;
}

/**
 * "5 min ago" / "in 12 min". Relative wording is timezone-independent, so it
 * can sit next to an IST timestamp without contradicting it.
 */
export function relativeTime(value: string | null | undefined, now: number = Date.now()): string {
  if (!value) return UNAVAILABLE;
  const time = new Date(value).getTime();
  if (Number.isNaN(time)) return UNAVAILABLE;

  const diff = time - now;
  const future = diff > 0;
  const seconds = Math.abs(diff) / 1000;

  let phrase: string;
  if (seconds < 45) return future ? "in a moment" : "just now";
  if (seconds < 3600) phrase = `${Math.round(seconds / 60)} min`;
  else if (seconds < 86_400) phrase = `${Math.round(seconds / 3600)} h`;
  else if (seconds < 86_400 * 30) phrase = `${Math.round(seconds / 86_400)} d`;
  else if (seconds < 86_400 * 365) phrase = `${Math.round(seconds / (86_400 * 30))} mo`;
  else phrase = `${Math.round(seconds / (86_400 * 365))} y`;

  return future ? `in ${phrase}` : `${phrase} ago`;
}

/** Engagement per 100 views; null when views are missing or zero. */
export function engagementRate(likes: unknown, comments: unknown, views: unknown): number | null {
  const viewCount = toFiniteNumber(views);
  if (viewCount === null || viewCount <= 0) return null;
  const interactions = (toFiniteNumber(likes) ?? 0) + (toFiniteNumber(comments) ?? 0);
  return (interactions / viewCount) * 100;
}

/** Initial for an avatar tile, tolerant of empty or emoji-led names. */
export function initialOf(name: string | null | undefined): string {
  const trimmed = String(name ?? "").trim();
  if (!trimmed) return "?";
  const first = Array.from(trimmed)[0] ?? "?";
  return first.toLocaleUpperCase();
}
