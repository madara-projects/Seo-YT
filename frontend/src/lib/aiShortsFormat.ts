import type { AiShortsPlan, AiShortsShot, QualityNote } from "@/api/aiShortsTypes";
import type { EvidenceTone } from "@/components/common/EvidenceChip";
import { LANGUAGE_OPTIONS } from "./creatorConstants";
import { asArray } from "./utils";

/** The limits mirror the backend's request model, so a 422 is caught in the field. */
export const QUOTE_MIN = 6;
export const QUOTE_MAX = 400;
export const MOOD_MAX = 200;

/** Flow generates 8-second clips; a Short here is one to three of them chained with Extend. */
export const SECONDS_PER_PART = 8;
export const PART_OPTIONS = [1, 2, 3] as const;
export const DEFAULT_PARTS = 2;

/**
 * The Creator's output languages, without "Match the video language": there
 * is no video yet, only a quote, so the package language must be chosen.
 */
export const AI_SHORTS_LANGUAGE_OPTIONS = LANGUAGE_OPTIONS.filter((option) => option.value !== "auto");

export interface AiShortsFormValues {
  quote: string;
  moodHint: string;
  parts: number;
  language: string;
}

export const aiShortsFormDefaults: AiShortsFormValues = {
  quote: "",
  moodHint: "",
  parts: DEFAULT_PARTS,
  language: "english",
};

/** "1 part · 8 s", "2 parts · 16 s". A saved plan passes the server's own total, null when unknown ("2 parts · —"). */
export function partsLabel(parts: number, totalSeconds: number | null = parts * SECONDS_PER_PART): string {
  const total = typeof totalSeconds === "number" && Number.isFinite(totalSeconds) ? `${totalSeconds} s` : "—";
  return `${parts} ${parts === 1 ? "part" : "parts"} · ${total}`;
}

/**
 * Why "Write Flow prompts" can't run yet, in words, or null when it can. The
 * button is disabled rather than left to fail, so the reason is shown beside it.
 */
export function quoteBlocker(values: Pick<AiShortsFormValues, "quote" | "moodHint">): string | null {
  const quote = values.quote.trim();
  if (!quote) return "Type the quote first.";
  if (quote.length < QUOTE_MIN) return `The quote needs at least ${QUOTE_MIN} characters.`;
  if (quote.length > QUOTE_MAX) return `Shorten the quote to ${QUOTE_MAX} characters or fewer.`;
  if (values.moodHint.trim().length > MOOD_MAX) return `Shorten the mood or scene wish to ${MOOD_MAX} characters or fewer.`;
  return null;
}

/** "Text to Video" for the first part; "Extend from Part 1" for the next. */
export function flowModeLabel(shot: Pick<AiShortsShot, "part" | "flow_mode">): string {
  if (shot.flow_mode === "extend") return `Extend from Part ${Math.max(1, shot.part - 1)}`;
  return "Text to Video";
}

/** "Part 2 · 8 s · Extend from Part 1". */
export function shotHeading(shot: AiShortsShot): string {
  return `Part ${shot.part} · ${shot.seconds} s · ${flowModeLabel(shot)}`;
}

/** Every prompt, labelled by part, for one paste into a notes file. */
export function allPromptsText(shots: AiShortsShot[]): string {
  return shots
    .map((shot) => `${shotHeading(shot).toUpperCase()}\n${shot.prompt}`)
    .join("\n\n");
}

/** The label and tone of a generation source chip. Generated text is never an observation. */
export function sourceChip(source: string | undefined): { label: string; tone: EvidenceTone } {
  return source === "fallback"
    ? { label: "Draft: built-in template", tone: "warn" }
    : { label: "Written with Gemini", tone: "warn" };
}

/**
 * The package's quality verdict, in the Creator's vocabulary: a passed check
 * is a local heuristic, a failed one is a failure, and none is not a pass.
 */
export function verdictChip(verdict: string | undefined): { label: string; tone: EvidenceTone } {
  switch (String(verdict ?? "").toUpperCase()) {
    case "GREEN":
      return { label: "Passed quality check", tone: "warn" };
    case "YELLOW":
      return { label: "Quality check: review warnings", tone: "warn" };
    case "RED":
      return { label: "Failed quality check", tone: "bad" };
    default:
      return { label: "Quality not checked", tone: "neutral" };
  }
}

/** The quality gate's notes as sentences, whatever shape the backend sent them in. */
export function qualityNotes(items: unknown): string[] {
  return asArray<QualityNote>(items)
    .map((item) => {
      if (typeof item === "string") return item.trim();
      if (item && typeof item === "object") {
        const text = item.message ?? item.reason ?? item.code;
        return text ? String(text).trim() : JSON.stringify(item);
      }
      return "";
    })
    .filter(Boolean);
}

/** The primary title first, then the variants, with repeats removed. */
export function titleOptions(plan: AiShortsPlan): string[] {
  const seen = new Set<string>();
  const titles: string[] = [];
  for (const candidate of [plan.package?.title, ...asArray<string>(plan.package?.title_variants)]) {
    const title = String(candidate ?? "").trim();
    const key = title.toLocaleLowerCase();
    if (!title || seen.has(key)) continue;
    seen.add(key);
    titles.push(title);
  }
  return titles;
}

/** The first words of a quote, for a list row or a dialog. */
export function quoteExcerpt(quote: string, max = 90): string {
  const text = quote.replace(/\s+/g, " ").trim();
  return text.length > max ? `${text.slice(0, max - 1).trimEnd()}…` : text;
}
