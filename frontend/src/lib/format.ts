import { shortDate } from "./historyFormat";
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

/**
 * One locale for both ranges, so the exact and the compact forms agree on
 * separators. "en" keeps YouTube's K/M style rather than lakh and crore.
 */
const COMPACT_LOCALE = "en";

const compactFormatter = new Intl.NumberFormat(COMPACT_LOCALE, {
  notation: "compact",
  maximumFractionDigits: 1,
});

/** 1234 → "1,234", 18432 → "18.4K". Small values stay exact. */
export function formatCompact(value: unknown, fallback: string = UNAVAILABLE): string {
  const number = toFiniteNumber(value);
  if (number === null) return fallback;
  return Math.abs(number) < 10_000 ? number.toLocaleString(COMPACT_LOCALE) : compactFormatter.format(number);
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

/** Watch time from minutes: 1 → "1 min", 45 → "45 mins", 60 → "1 hr", 750 → "12.5 hrs". */
export function formatMinutes(value: unknown, fallback: string = UNAVAILABLE): string {
  const minutes = toFiniteNumber(value);
  if (minutes === null || minutes < 0) return fallback;
  // Rounded first, so 59.7 minutes reads as "1 hr" rather than "60 mins".
  const whole = Math.round(minutes);
  if (whole < 60) return `${whole.toLocaleString()} ${whole === 1 ? "min" : "mins"}`;
  const hours = Math.round((minutes / 60) * 10) / 10;
  return `${hours.toLocaleString(undefined, { maximumFractionDigits: 1 })} ${hours === 1 ? "hr" : "hrs"}`;
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
  if (seconds < 45) return future ? "in a moment" : "just now";

  // Each unit is chosen after rounding, so 59.6 minutes becomes "1 h", never "60 min".
  const minutes = Math.round(seconds / 60);
  const hours = Math.round(seconds / 3600);
  const days = Math.round(seconds / 86_400);
  const months = Math.round(seconds / (86_400 * 30));
  const phrase =
    minutes < 60
      ? `${minutes} min`
      : hours < 24
        ? `${hours} h`
        : days < 30
          ? `${days} d`
          : months < 12
            ? `${months} mo`
            : `${Math.max(1, Math.round(seconds / (86_400 * 365)))} y`;

  return future ? `in ${phrase}` : `${phrase} ago`;
}

/**
 * When a scheduled check will run. A time that has already passed means the
 * status was read before it ran, so it says "due now" instead of "4 min ago".
 */
export function scheduledTime(value: string | null | undefined, now: number = Date.now()): string {
  if (!value) return UNAVAILABLE;
  const time = new Date(value).getTime();
  if (Number.isNaN(time)) return UNAVAILABLE;
  return time <= now ? "Due now" : relativeTime(value, now);
}

/**
 * "1.2K views on 23 Aug 2026". A stored count is only as current as its
 * capture, so it never appears without the date it was read.
 */
export function viewsAsOf(views: unknown, capturedAt: string | null | undefined): string {
  const count = `${formatCompact(views)} views`;
  const date = shortDate(capturedAt);
  return date === UNAVAILABLE ? `${count}, capture date unavailable` : `${count} on ${date}`;
}

/**
 * Engagement per 100 views; null when views are missing or zero, or when
 * neither likes nor comments are known (hidden counts are not zero).
 */
export function engagementRate(likes: unknown, comments: unknown, views: unknown): number | null {
  const viewCount = toFiniteNumber(views);
  if (viewCount === null || viewCount <= 0) return null;
  const likeCount = toFiniteNumber(likes);
  const commentCount = toFiniteNumber(comments);
  if (likeCount === null && commentCount === null) return null;
  return (((likeCount ?? 0) + (commentCount ?? 0)) / viewCount) * 100;
}

/** Initial for an avatar tile, tolerant of empty or emoji-led names. */
export function initialOf(name: string | null | undefined): string {
  const trimmed = String(name ?? "").trim();
  if (!trimmed) return "?";
  const first = Array.from(trimmed)[0] ?? "?";
  return first.toLocaleUpperCase();
}
