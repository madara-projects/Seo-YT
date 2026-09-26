import {
  FORMAT_CHOICES,
  LANGUAGE_OPTIONS,
  LONG_TYPES,
  REGION_OPTIONS,
  VIDEO_LANGUAGE_OPTIONS,
  type FormatChoice,
} from "./creatorConstants";
import { isFormatChoice, type CreatorFormValues } from "@/schemas/creator";

const FORMAT_KEY = "win-engine-creator-format";

export interface RememberedFormat {
  format_choice: FormatChoice;
  long_type: string;
}

/**
 * The creator's last format choice, so the next package starts from it. A
 * Short when nothing valid is stored: this channel makes mostly Shorts.
 */
export function readRememberedFormat(): RememberedFormat {
  try {
    const stored = JSON.parse(localStorage.getItem(FORMAT_KEY) ?? "null") as Partial<RememberedFormat> | null;
    if (stored && isFormatChoice(stored.format_choice)) {
      const longType = LONG_TYPES.some((type) => type.value === stored.long_type) ? String(stored.long_type) : "";
      return { format_choice: stored.format_choice, long_type: longType };
    }
  } catch {
    /* Private mode, blocked storage or a damaged value: start from the default. */
  }
  return { format_choice: "short", long_type: "" };
}

export function rememberFormat(value: RememberedFormat): void {
  try {
    localStorage.setItem(FORMAT_KEY, JSON.stringify(value));
  } catch {
    /* Remembering the choice is a convenience; the form works without it. */
  }
}

function label(options: readonly { value: string; label: string }[], value: string, fallback: string): string {
  return options.find((option) => option.value === value)?.label ?? fallback;
}

/** "Short", "Long video · Tutorial", or "Format detected for you". */
export function formatLabel(values: Pick<CreatorFormValues, "format_choice" | "long_type">): string {
  if (values.format_choice === "auto") return "Format detected for you";
  const base = label(FORMAT_CHOICES, values.format_choice, "Short");
  const kind = values.format_choice === "long" ? LONG_TYPES.find((type) => type.value === values.long_type) : undefined;
  return kind && kind.value !== "other" ? `${base} · ${kind.label}` : base;
}

export function outputLanguageLabel(value: string): string {
  return value === "auto" ? "Video's language" : label(LANGUAGE_OPTIONS, value, "English");
}

export function spokenLanguageLabel(value: string): string {
  return label(VIDEO_LANGUAGE_OPTIONS, value, "English");
}

export function regionLabel(value: string): string {
  return label(REGION_OPTIONS, value, "Global");
}

/** Format, output language and region, as the setup summary shows them. */
export function summaryParts(values: CreatorFormValues): string[] {
  return [formatLabel(values), outputLanguageLabel(values.language), regionLabel(values.region)];
}

/** The one-line summary in the setup bar: "Short · English · Global". */
export function setupSummary(values: CreatorFormValues): string {
  return summaryParts(values).join(" · ");
}
