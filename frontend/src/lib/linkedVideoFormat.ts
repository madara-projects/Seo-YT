import type { ComparableLabels, ComparableMetadataUpdate, LinkedSnapshot, LinkedVideoReport } from "@/api/historyTypes";
import { windowLabel } from "./auditFormat";
import { optionLabel, type LabelledOption } from "./labels";
import { IDEA_LANGUAGE_OPTIONS } from "@/schemas/idea";

/**
 * Wording and rules for a linked video's learning labels. The rules restate
 * the backend's: learning (evidence_policy.comparable_metadata) needs the
 * format and language; the diagnosis' peer baseline matches all four labels;
 * `update_comparable_metadata` accepts only these formats and durations, and
 * stores a null label as "unknown".
 */

export type LabelField = keyof ComparableLabels;

export const LABEL_FIELDS: readonly LabelField[] = ["language", "format", "duration_bucket", "topic_category"];
/** The labels without which a video is left out of learning entirely. */
const LEARNING_FIELDS: readonly LabelField[] = ["format", "language"];

export const LABEL_NAMES: Record<LabelField, string> = {
  language: "language",
  format: "format",
  duration_bucket: "duration",
  topic_category: "topic",
};

/** ComparableMetadataRequest's max_length per field. */
export const LABEL_MAX_LENGTH: Record<LabelField, number> = {
  language: 40,
  format: 40,
  duration_bucket: 30,
  topic_category: 80,
};

/** The spellings packages store, so a label set here joins the same cohort. */
export const LABEL_LANGUAGE_OPTIONS: readonly LabelledOption[] = [{ value: "", label: "Unknown" }, ...IDEA_LANGUAGE_OPTIONS];

/** history_store.FORMAT_VALUES. */
export const LABEL_FORMAT_OPTIONS: readonly LabelledOption[] = [
  { value: "", label: "Unknown" },
  { value: "youtube_shorts", label: "YouTube Short" },
  { value: "long_form", label: "Long-form" },
  { value: "talking_head", label: "Talking head" },
  { value: "tutorial", label: "Tutorial" },
  { value: "vlog", label: "Vlog" },
  { value: "review", label: "Review" },
  { value: "quote", label: "Quote" },
  { value: "story", label: "Story" },
  { value: "challenge", label: "Challenge" },
  { value: "other", label: "Other" },
];

/** history_store.DURATION_VALUES. */
export const LABEL_DURATION_OPTIONS: readonly LabelledOption[] = [
  { value: "", label: "Unknown" },
  { value: "under_60s", label: "Under 60 seconds" },
  { value: "60_to_180s", label: "1 to 3 minutes" },
  { value: "3_to_10m", label: "3 to 10 minutes" },
  { value: "over_10m", label: "Over 10 minutes" },
];

const OPTIONS: Partial<Record<LabelField, readonly LabelledOption[]>> = {
  language: LABEL_LANGUAGE_OPTIONS,
  format: LABEL_FORMAT_OPTIONS,
  duration_bucket: LABEL_DURATION_OPTIONS,
};

/**
 * A stored label, with "unknown" and blanks as "". Spaces are squeezed the way
 * a saved edit is, so a label stored with a double space does not count as
 * changed before anyone touches it. "unknown" is matched exactly, as the
 * server does: any other spelling is a real label that learning counts.
 */
export function storedLabel(labels: ComparableLabels | null | undefined, field: LabelField): string {
  const value = normaliseLabel(String(labels?.[field] ?? ""));
  return value === "unknown" ? "" : value;
}

function normaliseLabel(value: string): string {
  return value.trim().replace(/\s+/g, " ");
}

export function labelText(field: LabelField, value: string): string {
  const options = OPTIONS[field];
  if (!value) return "Unknown";
  return options ? optionLabel(options, value, "Unknown") : value;
}

/**
 * The options for one select. A value stored outside the list (an older
 * spelling) is kept as a choice, so opening the editor never changes it.
 */
export function labelOptions(field: Exclude<LabelField, "topic_category">, current: string): readonly LabelledOption[] {
  const options = OPTIONS[field] ?? [];
  return !current || options.some((option) => option.value === current)
    ? options
    : [...options, { value: current, label: labelText(field, current) }];
}

/** "language", "format and language", "duration, topic and language". */
export function joinNames(fields: readonly LabelField[]): string {
  const names = fields.map((field) => LABEL_NAMES[field]);
  if (names.length <= 1) return names.join("");
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

export interface LearningStatus {
  /** True when the video is known to be left out of learning, false when known to count, null when not said. */
  excluded: boolean | null;
  title: string;
  body: string;
}

/**
 * evidence_policy.verified_ownership as far as the report shows it: the flag,
 * the "verified" state and the channel it was verified against. A payload
 * without the state or channel is judged on the flag alone.
 */
function ownershipVerified(report: LinkedVideoReport): boolean {
  if (report.ownership_verified !== true) return false;
  if (report.ownership_state !== undefined && report.ownership_state !== "verified") return false;
  return report.verified_channel_id === undefined || String(report.verified_channel_id ?? "").trim() !== "";
}

/**
 * Why a linked video is or is not used for learning. Unknown labels are the
 * reason the creator can repair here, so they come first; the server's own
 * verdict (`counts_toward_generation`) is used when it sends one.
 */
export function learningStatus(report: LinkedVideoReport): LearningStatus {
  const labels = report.comparable_metadata ?? {};
  const missing = LEARNING_FIELDS.filter((field) => !storedLabel(labels, field));
  const baselineMissing = LABEL_FIELDS.filter((field) => !LEARNING_FIELDS.includes(field) && !storedLabel(labels, field));
  const peerNote = baselineMissing.length
    ? ` The diagnosis compares it with similar videos only once its ${joinNames(baselineMissing)} ${baselineMissing.length === 1 ? "is" : "are"} set too.`
    : "";
  if (missing.length) {
    return {
      excluded: true,
      title: "Not used for learning",
      body: `Its ${joinNames(missing)} ${missing.length === 1 ? "is" : "are"} unknown. Learning compares only videos of the same format and language, so this video is left out until ${missing.length === 1 ? "it is" : "they are"} set.${peerNote}`,
    };
  }
  const counts = report.diagnosis?.counts_toward_generation;
  if (counts === false) {
    return {
      excluded: true,
      title: "Not used for learning yet",
      body: ownershipVerified(report)
        ? `Its labels are set. It counts once its 24-hour window has been collected.${peerNote}`
        : `Its labels are set, but only videos verified as your connected channel's own are used.${peerNote}`,
    };
  }
  return {
    excluded: counts === true ? false : null,
    title: counts === true ? "Used for learning" : "Learning labels",
    body: `Its format and language are set${counts === true ? ", and it counts toward what packages learn from" : ""}.${peerNote}`,
  };
}

/**
 * The window and the peer comparison behind the verdict, or null when the
 * server sent neither (an older version). The server counts comparable videos
 * only once this video's window is complete and all four labels are set
 * (history_store._comparable_snapshot_baseline); before that it reports a size
 * of 0 without looking. A 0 or missing size therefore never means that no
 * comparable videos exist, and is worded as "not compared".
 */
export function diagnosisBasis(
  diagnosis: LinkedVideoReport["diagnosis"],
  labels?: ComparableLabels | null,
): string | null {
  if (!diagnosis) return null;
  const hasWindow = "window" in diagnosis;
  const size = diagnosis.baseline_sample_size;
  const hasPeers = typeof size === "number" || typeof diagnosis.peer_baseline_available === "boolean";
  if (!hasWindow && !hasPeers) return null;
  const window = diagnosis.window && diagnosis.window !== "none" ? windowLabel(diagnosis.window) : null;
  const parts = [window ? `From the ${window}` : "No completed window yet"];
  if (diagnosis.peer_baseline_available && typeof size === "number") {
    parts.push(`compared with ${size.toLocaleString()} comparable ${size === 1 ? "video" : "videos"}`);
  } else if (diagnosis.peer_baseline_available === true) {
    // A baseline was used but its size was not sent; say so without a number.
    parts.push("compared with similar videos");
  } else if (typeof size === "number" && size > 0) {
    // A positive count exists only when the server ran the comparison, so it is real.
    parts.push(`${size.toLocaleString()} comparable ${size === 1 ? "video" : "videos"} so far, too few to compare with`);
  } else if (hasPeers && window) {
    // Unknown labels stop the comparison outright, so they are named when the
    // report shows them. Otherwise the cause is not in the payload.
    const unknown = labels ? LABEL_FIELDS.filter((field) => !storedLabel(labels, field)) : [];
    parts.push(
      unknown.length
        ? `not compared with other videos while its ${joinNames(unknown)} ${unknown.length === 1 ? "is" : "are"} unknown`
        : "not compared with other videos",
    );
  }
  // Without a completed window there is nothing of this video's to compare yet,
  // so no peer clause is added.
  return `${parts.join(" · ")}.`;
}

export interface UploadedMetadataView {
  /** The title read from YouTube, or null when it is unknown. */
  title: string | null;
  /** The package title comparison, or null when there is no uploaded title to compare. */
  titleMatch: boolean | null;
  tagsKnown: boolean;
  descriptionKnown: boolean;
}

function nonBlank(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

/**
 * What the lookup read of the uploaded video, so an unread field is shown as
 * unknown rather than as empty. A server that sends `uploaded_metadata_known`
 * says so per field and nulls the comparisons it cannot make. An older one
 * filled the uploaded title from the selected title and the tag lists with []
 * when the lookup read nothing (oEmbed reads no tags or description), so for
 * it only the metadata actually stored under `youtube` counts as read.
 */
export function uploadedMetadataView(report: LinkedVideoReport): UploadedMetadataView {
  const usage = report.package_usage ?? {};
  const known = usage.uploaded_metadata_known ?? null;
  const youtube = report.youtube ?? {};
  const fetchedTitle = nonBlank(youtube.title);
  const title =
    typeof known?.title === "boolean" ? (known.title ? nonBlank(usage.uploaded_title) ?? fetchedTitle : null) : fetchedTitle;
  const tagsRead = typeof known?.tags === "boolean" ? known.tags : Array.isArray(youtube.tags);
  const descriptionRead = typeof known?.description === "boolean" ? known.description : typeof youtube.description === "string";
  return {
    title,
    titleMatch: title !== null && typeof usage.title_match === "boolean" ? usage.title_match : null,
    tagsKnown: tagsRead && Array.isArray(usage.matching_tags),
    descriptionKnown: descriptionRead && typeof usage.description_match_percent === "number",
  };
}

/** Whether a window ran out of attempts, which only "Retry failed windows" collects again. */
export function hasExhaustedWindows(snapshots: readonly LinkedSnapshot[] | null | undefined): boolean {
  return (snapshots ?? []).some((snapshot) => snapshot?.retry_exhausted === true);
}

export type LabelDraft = Record<LabelField, string>;

export function labelDraft(labels: ComparableLabels | null | undefined): LabelDraft {
  return {
    language: storedLabel(labels, "language"),
    format: storedLabel(labels, "format"),
    duration_bucket: storedLabel(labels, "duration_bucket"),
    topic_category: storedLabel(labels, "topic_category"),
  };
}

/**
 * The field errors the PATCH route would answer with a 422, caught before
 * sending. Given the stored labels, only changed labels are checked: an
 * unchanged one is not sent, so an older stored value never blocks the others.
 */
export function labelErrors(draft: LabelDraft, stored?: ComparableLabels | null): Partial<Record<LabelField, string>> {
  const errors: Partial<Record<LabelField, string>> = {};
  const sent = stored === undefined ? null : labelChanges(draft, stored);
  for (const field of LABEL_FIELDS) {
    if (sent && !(field in sent)) continue;
    const value = normaliseLabel(draft[field]);
    if (value.length > LABEL_MAX_LENGTH[field]) {
      errors[field] = `Limited to ${LABEL_MAX_LENGTH[field]} characters.`;
    } else if (field === "duration_bucket" && value && !LABEL_DURATION_OPTIONS.some((option) => option.value === value)) {
      errors.duration_bucket = "Choose one of the listed durations.";
    }
  }
  return errors;
}

/**
 * Only the labels that changed, so a creator's edit to one never rewrites the
 * source of the others. A cleared label is sent as null, which stores "unknown".
 */
export function labelChanges(draft: LabelDraft, stored: ComparableLabels | null | undefined): ComparableMetadataUpdate {
  const before = labelDraft(stored);
  const changes: ComparableMetadataUpdate = {};
  for (const field of LABEL_FIELDS) {
    const next = normaliseLabel(draft[field]);
    if (next !== before[field]) changes[field] = next || null;
  }
  return changes;
}
