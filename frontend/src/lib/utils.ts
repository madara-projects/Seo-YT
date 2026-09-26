import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * The backend deliberately returns null/absent rather than guessing a value.
 * The UI must render that distinction rather than hiding it behind a zero or
 * an em dash, so every display helper funnels through here.
 */
export const UNAVAILABLE = "Unavailable";

export function displayValue(value: unknown, fallback: string = UNAVAILABLE): string {
  if (value === null || value === undefined || value === "") return fallback;
  return String(value);
}

export function formatNumber(value: unknown, fallback: string = UNAVAILABLE): string {
  if (typeof value === "number" && Number.isFinite(value)) return value.toLocaleString();
  const parsed = Number(value);
  if (value !== null && value !== undefined && value !== "" && Number.isFinite(parsed)) {
    return parsed.toLocaleString();
  }
  return fallback;
}

export function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

export function asObject(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

export function normalizeTitle(value: unknown): string {
  return String(value ?? "").trim().toLocaleLowerCase();
}
