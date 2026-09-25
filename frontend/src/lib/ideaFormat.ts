import type { EvidenceTone } from "@/components/common/EvidenceChip";
import type { Step } from "@/components/research/StepFlow";
import { humanize, optionLabel } from "@/lib/labels";
import { IDEA_FORMAT_OPTIONS, IDEA_LANGUAGE_OPTIONS, IDEA_REGION_OPTIONS } from "@/schemas/idea";
import type { Idea, IdeaStatus } from "@/api/ideaTypes";

/**
 * Wording and rules for the idea backlog. The status rules restate the checks
 * in `HistoryStore.update_content_idea` and the generate route, so a button is
 * never offered for a change the backend would refuse.
 */

const STATUSES: Record<IdeaStatus, { label: string; tone: EvidenceTone }> = {
  idea: { label: "Idea", tone: "neutral" },
  scripted: { label: "Scripted", tone: "info" },
  package_generated: { label: "Package generated", tone: "info" },
  published: { label: "Published", tone: "ok" },
  archived: { label: "Archived", tone: "neutral" },
};

export function ideaStatusLabel(status: unknown): { label: string; tone: EvidenceTone } {
  const key = String(status ?? "").trim();
  return STATUSES[key as IdeaStatus] ?? { label: key ? humanize(key) : "Unknown", tone: "neutral" };
}

/** Older ideas were saved with the legacy form's `in` for India. */
const REGION_ALIASES = new Map([
  ["in", "india"],
  ["usa", "us"],
  ["gb", "uk"],
]);

export const ideaFormatLabel = (value: unknown) => optionLabel(IDEA_FORMAT_OPTIONS, value, "Not specified", new Map([["unknown", ""]]));
export const ideaLanguageLabel = (value: unknown) => optionLabel(IDEA_LANGUAGE_OPTIONS, value, "Not specified");
export const ideaRegionLabel = (value: unknown) => optionLabel(IDEA_REGION_OPTIONS, value, "Global", REGION_ALIASES);

/** 45 → "45 sec", 90 → "1 min 30 sec", 3900 → "1 hr 5 min". */
export function durationLabel(seconds: unknown): string {
  const total = typeof seconds === "number" && Number.isFinite(seconds) ? Math.round(seconds) : null;
  if (total === null || total <= 0) return "Not specified";
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const rest = total % 60;
  if (hours) return minutes ? `${hours} hr ${minutes} min` : `${hours} hr`;
  if (minutes) return rest ? `${minutes} min ${rest} sec` : `${minutes} min`;
  return `${rest} sec`;
}

/** How far an idea has come, as the Idea → Script → Package → Published steps. */
export function ideaLifecycle(idea: Pick<Idea, "status" | "analysis_run_id" | "published_video_link_id">): Step[] {
  const linked = Boolean(idea.published_video_link_id);
  const packaged = Boolean(idea.analysis_run_id);
  const published = idea.status === "published";
  const scripted = idea.status === "scripted" || packaged || linked || published;

  const reached = [true, scripted, packaged, published || linked];
  const current = idea.status === "archived" ? -1 : reached.indexOf(false);
  const state = (index: number): Step["state"] =>
    reached[index] ? "done" : index === current ? "current" : "pending";

  return [
    { label: "Idea", value: "Saved", state: state(0) },
    { label: "Script", value: scripted ? "Scripted" : "Not yet", state: state(1) },
    { label: "Package", value: packaged ? `Run #${idea.analysis_run_id}` : "Not yet", state: state(2) },
    {
      label: "Published",
      value: published ? "Published" : linked ? "Linked to YouTube" : "Not yet",
      state: state(3),
    },
  ];
}

export interface IdeaActions {
  canResearch: boolean;
  canGenerate: boolean;
  canMarkScripted: boolean;
  /** Offered while the idea is live; enabled only once a video is linked. */
  showMarkPublished: boolean;
  canMarkPublished: boolean;
  isArchived: boolean;
  /** Archiving forgets the earlier status, so restore to the furthest one the record still proves. */
  restoreTo: "package_generated" | "idea";
}

export function ideaActions(idea: Pick<Idea, "status" | "analysis_run_id" | "published_video_link_id">): IdeaActions {
  const status = String(idea.status);
  const isArchived = status === "archived";
  const isPublished = status === "published";
  return {
    canResearch: !isArchived,
    canGenerate: !isArchived && !isPublished,
    canMarkScripted: status === "idea",
    showMarkPublished: !isArchived && !isPublished,
    canMarkPublished: Boolean(idea.published_video_link_id),
    isArchived,
    restoreTo: idea.analysis_run_id ? "package_generated" : "idea",
  };
}
