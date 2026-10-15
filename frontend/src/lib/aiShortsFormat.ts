import type {
  AiShortsChecks,
  AiShortsGenerationQuality,
  AiShortsOverlay,
  AiShortsPlan,
  AiShortsPromptSection,
  AiShortsShot,
  QualityNote,
} from "@/api/aiShortsTypes";
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

/** "Text to video" for the first part; "Extend Part 1" for the next. */
export function flowModeLabel(shot: Pick<AiShortsShot, "part" | "flow_mode">): string {
  if (shot.flow_mode === "extend") return `Extend Part ${Math.max(1, shot.part - 1)}`;
  return "Text to video";
}

export interface SecondsRange {
  start: number;
  end: number;
}

/** Where each part sits in the Short, in order: the second of two 8 s parts runs 8–16 s. */
export function shotRanges(shots: Pick<AiShortsShot, "seconds">[]): SecondsRange[] {
  let start = 0;
  return shots.map((shot) => {
    const seconds = typeof shot.seconds === "number" && shot.seconds > 0 ? shot.seconds : SECONDS_PER_PART;
    const range = { start, end: start + seconds };
    start = range.end;
    return range;
  });
}

/** "0–8 s". */
export function rangeLabel(range: SecondsRange): string {
  return `${range.start}–${range.end} s`;
}

/** "Part 2 · 8–16 s · Extend Part 1". */
export function shotHeading(shot: AiShortsShot, range: SecondsRange): string {
  return `Part ${shot.part} · ${rangeLabel(range)} · ${flowModeLabel(shot)}`;
}

/** Every prompt, labelled by part, for one paste into a notes file. */
export function allPromptsText(shots: AiShortsShot[]): string {
  const ranges = shotRanges(shots);
  return shots
    .map((shot, index) => `${shotHeading(shot, ranges[index]!).toUpperCase()}\n${shot.prompt}`)
    .join("\n\n");
}

/** The prompt's labelled pieces, or none when the plan predates them or sent them damaged. */
export function promptSections(shot: Pick<AiShortsShot, "sections">): AiShortsPromptSection[] {
  return asArray<Partial<AiShortsPromptSection> | null>(shot.sections)
    .map((section) => ({ label: String(section?.label ?? "").trim(), text: String(section?.text ?? "").trim() }))
    .filter((section) => section.label && section.text);
}

/**
 * A prompt without sections as short paragraphs: its own line breaks, else
 * about three sentences each. Only a full stop before a capital ends a
 * sentence, so "9:16" and "f/2.8" stay whole.
 */
export function promptParagraphs(prompt: string, perParagraph = 3): string[] {
  const text = String(prompt ?? "").trim();
  if (!text) return [];
  const lines = text.split(/\n+/).map((line) => line.trim()).filter(Boolean);
  if (lines.length > 1) return lines;
  const sentences = text.replace(/([.!?]["”’)]?)\s+(?=["“(]?[A-Z])/g, "$1\n").split("\n");
  const paragraphs: string[] = [];
  for (let index = 0; index < sentences.length; index += perParagraph) {
    paragraphs.push(sentences.slice(index, index + perParagraph).join(" "));
  }
  return paragraphs;
}

/** "0-8" → "0–8 s"; null when the overlay gave no time. */
export function overlaySecondsLabel(seconds: string | undefined): string | null {
  const text = String(seconds ?? "").trim();
  if (!text) return null;
  const range = text.replace(/\s*s$/i, "").replace(/\s*[-–]\s*/, "–");
  return `${range} s`;
}

/** The lines of the quote shown during one part, or null when the plan says nothing about that part. */
export function partOverlay(
  plan: Pick<AiShortsPlan, "text_overlay_plan">,
  part: number,
): { lines: string[]; seconds: string | null } | null {
  const overlay = asArray<AiShortsOverlay>(plan.text_overlay_plan).find((item) => item?.part === part);
  if (!overlay) return null;
  return {
    lines: asArray<string>(overlay.lines).map((line) => String(line ?? "").trim()).filter(Boolean),
    seconds: overlaySecondsLabel(overlay.seconds),
  };
}

const PART_PREFIX = /^Part (\d+):\s*/i;
/** Older plans listed the planner's own fixes among the warnings. */
const LEGACY_ADJUSTMENT = /^Part \d+: (?:added|trimmed from)\b/i;

function cleanList(items: unknown): string[] {
  return [...new Set(asArray<unknown>(items).map((item) => String(item ?? "").trim()).filter(Boolean))];
}

/** "prompt names no camera move" → "Prompt names no camera move." */
function asSentence(text: string): string {
  const capital = text.charAt(0).toLocaleUpperCase() + text.slice(1);
  return /[.!?…)]$/.test(capital) ? capital : `${capital}.`;
}

export interface PlanAdjustments {
  /** Each part's fixes, without the "Part N:" they started with. */
  byPart: Map<number, string[]>;
  /** Fixes that name no part. */
  general: string[];
}

/** What the planner fixed by itself, by part: shown as done, never as a warning. */
export function planAdjustments(checks: AiShortsChecks | undefined): PlanAdjustments {
  const byPart = new Map<number, string[]>();
  const general: string[] = [];
  const legacy = cleanList(checks?.warnings).filter((warning) => LEGACY_ADJUSTMENT.test(warning));
  for (const item of new Set([...cleanList(checks?.adjustments), ...legacy])) {
    const match = PART_PREFIX.exec(item);
    if (!match) {
      general.push(item);
      continue;
    }
    const part = Number(match[1]);
    byPart.set(part, [...(byPart.get(part) ?? []), item.slice(match[0].length)]);
  }
  return { byPart, general };
}

export interface CheckFinding {
  severity: "issue" | "warning";
  /** The part it is about, or null for the whole plan. */
  part: number | null;
  text: string;
}

/** The checks' real issues and warnings, the planner's own fixes left out, each as a sentence. */
export function checkFindings(checks: AiShortsChecks | undefined): CheckFinding[] {
  const fixed = new Set(cleanList(checks?.adjustments));
  const read = (items: unknown, severity: CheckFinding["severity"]): CheckFinding[] =>
    cleanList(items)
      .filter((text) => severity === "issue" || (!fixed.has(text) && !LEGACY_ADJUSTMENT.test(text)))
      .map((text) => {
        const match = PART_PREFIX.exec(text);
        const body = match ? text.slice(match[0].length) : text;
        return { severity, part: match ? Number(match[1]) : null, text: asSentence(body || text) };
      });
  return [...read(checks?.issues, "issue"), ...read(checks?.warnings, "warning")];
}

/** The package quality notes as findings. A YELLOW or RED verdict that lists none still counts once. */
export function packageFindings(quality: AiShortsGenerationQuality | undefined): CheckFinding[] {
  const findings: CheckFinding[] = [
    ...qualityNotes(quality?.issues).map((text) => ({ severity: "issue" as const, part: null, text: asSentence(text) })),
    ...qualityNotes(quality?.warnings).map((text) => ({ severity: "warning" as const, part: null, text: asSentence(text) })),
  ];
  const verdict = String(quality?.verdict ?? "").toUpperCase();
  if (!findings.length && verdict === "RED") {
    findings.push({ severity: "issue", part: null, text: "The package failed its quality check." });
  } else if (!findings.length && verdict === "YELLOW") {
    findings.push({ severity: "warning", part: null, text: "The quality check asks for a review before you upload." });
  }
  return findings;
}

/**
 * The plan's one status, over the prompts' checks and the package's quality
 * notes: ready only when both are clean, else how many things to check (a
 * failure if any is an issue).
 */
export function planStatus(
  checks: AiShortsChecks | undefined,
  quality?: AiShortsGenerationQuality,
): { label: string; tone: EvidenceTone; count: number } {
  const findings = [...checkFindings(checks), ...packageFindings(quality)];
  const count = findings.length;
  const failed = checks?.passed === false || findings.some((finding) => finding.severity === "issue");
  if (count) return { label: `${count} ${count === 1 ? "thing" : "things"} to check`, tone: failed ? "bad" : "warn", count };
  if (failed) return { label: "Checks failed", tone: "bad", count };
  if (!checks) return { label: "Checks unavailable", tone: "neutral", count };
  return { label: "Ready", tone: "ok", count };
}

/** A Flow step without the number the server puts in front of it: the checklist numbers it. */
export function stepText(step: string): string {
  return String(step ?? "").replace(/^\s*\d+[.)]\s+/, "").trim();
}

/** The part whose prompt a step pastes ("paste the Part 2 prompt"), or null. */
export function stepPromptPart(step: string): number | null {
  const match = /\bPart (\d+) prompt\b/i.exec(step);
  return match ? Number(match[1]) : null;
}

/** The result tabs, in order. The first is where a plan opens until the creator picks another. */
export const PLAN_TABS = [
  { value: "prompts", label: "Prompts" },
  { value: "package", label: "Upload package" },
  { value: "flow", label: "Make it in Flow" },
  { value: "notes", label: "Scene notes" },
] as const;

export type PlanTab = (typeof PLAN_TABS)[number]["value"];

const PLAN_TAB_KEY = "win-engine-ai-shorts-tab";

export function isPlanTab(value: unknown): value is PlanTab {
  return PLAN_TABS.some((tab) => tab.value === value);
}

/** The tab the creator last opened, so the next plan opens there too. */
export function readPlanTab(): PlanTab {
  try {
    const stored = localStorage.getItem(PLAN_TAB_KEY);
    if (isPlanTab(stored)) return stored;
  } catch {
    /* Private mode or blocked storage: start on the prompts. */
  }
  return "prompts";
}

export function rememberPlanTab(tab: PlanTab): void {
  try {
    localStorage.setItem(PLAN_TAB_KEY, tab);
  } catch {
    /* Remembering the tab is a convenience; the tabs work without it. */
  }
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

/** What the verdict means for the creator, in one sentence. */
export function verdictSummary(verdict: string | undefined): string {
  switch (String(verdict ?? "").toUpperCase()) {
    case "GREEN":
      return "The title, description and tags stay true to the quote.";
    case "YELLOW":
      return "Usable, with notes to read before you upload.";
    case "RED":
      return "Fix the notes below before you upload.";
    default:
      return "No quality check ran on this package.";
  }
}

/** The quality gate's notes as sentences, whatever shape the backend sent them in. */
export function qualityNotes(items: unknown): string[] {
  return [...new Set(asArray<QualityNote>(items)
    .map((item) => {
      if (typeof item === "string") return item.trim();
      if (item && typeof item === "object") {
        const text = item.message ?? item.reason ?? item.code;
        return text ? String(text).trim() : JSON.stringify(item);
      }
      return "";
    })
    .filter(Boolean))];
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
