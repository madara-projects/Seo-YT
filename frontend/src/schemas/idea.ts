import { z } from "zod";
import type { IdeaCreatePayload } from "@/api/ideaTypes";
import type { LabelledOption } from "@/lib/labels";

/**
 * The new-idea form. Limits mirror the Pydantic `CreateIdeaRequest`, so a
 * value the backend would reject with a 422 is caught in the field instead.
 */
const text = (max: number, message: string) => z.string().trim().max(max, message);

export const ideaFormSchema = z.object({
  topic: z
    .string()
    .trim()
    .min(1, "Enter what the video is about.")
    .max(300, "Topics are limited to 300 characters."),
  notes: text(5000, "Notes are limited to 5,000 characters."),
  format: z.string().max(40),
  language: z.string().max(40),
  region: z.string().max(40),
  // Kept as text so an empty field means "not specified" rather than 0.
  target_duration_seconds: z
    .string()
    .trim()
    .refine(
      (value) => value === "" || (Number.isFinite(Number(value)) && Number(value) >= 1 && Number(value) <= 86400),
      "Enter a duration from 1 to 86,400 seconds, or leave it empty.",
    ),
  visual_or_background: text(1000, "Limited to 1,000 characters."),
  on_screen_text: text(2000, "Limited to 2,000 characters."),
  emotion_or_intent: text(300, "Limited to 300 characters."),
  search_angle: text(500, "Limited to 500 characters."),
  browse_angle: text(500, "Limited to 500 characters."),
  audience_angle: text(500, "Limited to 500 characters."),
});

export type IdeaFormValues = z.infer<typeof ideaFormSchema>;

export const ideaFormDefaults: IdeaFormValues = {
  topic: "",
  notes: "",
  format: "youtube_shorts",
  language: "english",
  region: "global",
  target_duration_seconds: "",
  visual_or_background: "",
  on_screen_text: "",
  emotion_or_intent: "",
  search_angle: "",
  browse_angle: "",
  audience_angle: "",
};

export function ideaPayload(values: IdeaFormValues): IdeaCreatePayload {
  const duration = values.target_duration_seconds.trim();
  return {
    topic: values.topic.trim(),
    notes: values.notes.trim(),
    format: values.format,
    language: values.language,
    region: values.region,
    visual_or_background: values.visual_or_background.trim(),
    on_screen_text: values.on_screen_text.trim(),
    target_duration_seconds: duration ? Number(duration) : null,
    emotion_or_intent: values.emotion_or_intent.trim(),
    search_angle: values.search_angle.trim(),
    browse_angle: values.browse_angle.trim(),
    audience_angle: values.audience_angle.trim(),
    status: "idea",
  };
}

/** The legacy Ideas form's formats, unchanged. */
export const IDEA_FORMAT_OPTIONS: LabelledOption[] = [
  { value: "youtube_shorts", label: "YouTube Short" },
  { value: "tutorial", label: "Tutorial" },
  { value: "vlog", label: "Vlog" },
  { value: "review", label: "Review" },
  { value: "story", label: "Story" },
  { value: "other", label: "Other" },
];

/**
 * Research reads an idea's language and region, so these are the values the
 * engine acts on (the same as Demand's), with "global" for no region.
 */
export const IDEA_LANGUAGE_OPTIONS: LabelledOption[] = [
  { value: "english", label: "English" },
  { value: "tamil", label: "Tamil" },
  { value: "tanglish", label: "Tanglish" },
  { value: "hindi", label: "Hindi" },
];

export const IDEA_REGION_OPTIONS: LabelledOption[] = [
  { value: "global", label: "Global" },
  { value: "india", label: "India" },
  { value: "tamil nadu", label: "Tamil Nadu" },
  { value: "sri lanka", label: "Sri Lanka" },
  { value: "gulf", label: "Gulf countries" },
  { value: "us", label: "United States" },
  { value: "uk", label: "United Kingdom" },
];

export const IDEA_STATUS_FILTERS: LabelledOption[] = [
  { value: "", label: "All statuses" },
  { value: "idea", label: "Idea" },
  { value: "scripted", label: "Scripted" },
  { value: "package_generated", label: "Package generated" },
  { value: "published", label: "Published" },
  { value: "archived", label: "Archived" },
];
