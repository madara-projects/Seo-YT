import { z } from "zod";
import type { ExperimentCreatePayload } from "@/api/experimentTypes";
import type { LabelledOption } from "@/lib/labels";

/**
 * The new-experiment form. Limits mirror `CreateStructuredExperimentRequest`;
 * new experiments start as drafts, as the backend requires.
 */
export const experimentFormSchema = z.object({
  name: z.string().trim().min(1, "Name the comparison.").max(160, "Names are limited to 160 characters."),
  hypothesis: z
    .string()
    .trim()
    .min(1, "State what you expect to see.")
    .max(1000, "Limited to 1,000 characters."),
  mode: z.enum(["controlled", "observational"]),
  variable: z.string().min(1).max(100),
  control_definition: z
    .string()
    .trim()
    .min(1, "Describe the usual approach.")
    .max(1000, "Limited to 1,000 characters."),
  variant_definition: z
    .string()
    .trim()
    .min(1, "Describe the one thing you change.")
    .max(1000, "Limited to 1,000 characters."),
  success_metric: z.enum(["views", "average_view_percentage", "likes", "comments", "engagement_rate"]),
  observation_window: z.enum(["24h", "7d", "28d"]),
});

export type ExperimentFormValues = z.infer<typeof experimentFormSchema>;

/** The legacy form's defaults: its first option in each list. */
export const experimentFormDefaults: ExperimentFormValues = {
  name: "",
  hypothesis: "",
  mode: "controlled",
  variable: "title_mechanism",
  control_definition: "",
  variant_definition: "",
  success_metric: "average_view_percentage",
  observation_window: "24h",
};

export function experimentPayload(values: ExperimentFormValues): ExperimentCreatePayload {
  return {
    name: values.name.trim(),
    hypothesis: values.hypothesis.trim(),
    mode: values.mode,
    variable: values.variable,
    control_definition: values.control_definition.trim(),
    variant_definition: values.variant_definition.trim(),
    success_metric: values.success_metric,
    observation_window: values.observation_window,
  };
}

export const EXPERIMENT_MODE_OPTIONS: LabelledOption[] = [
  { value: "controlled", label: "Planned experiment" },
  { value: "observational", label: "Observational comparison" },
];

export const EXPERIMENT_VARIABLE_OPTIONS: LabelledOption[] = [
  { value: "title_mechanism", label: "Title mechanism" },
  { value: "hook_structure", label: "Hook structure" },
  { value: "opening_wording", label: "Opening wording" },
  { value: "quote_presentation", label: "Quote presentation" },
  { value: "thumbnail_concept", label: "Thumbnail concept" },
  { value: "first_frame_text", label: "First-frame text" },
  { value: "description_structure", label: "Description structure" },
  { value: "hashtag_strategy", label: "Hashtag strategy" },
  { value: "tag_strategy", label: "Tag strategy" },
  { value: "content_format", label: "Content format" },
  { value: "duration_bucket", label: "Duration bucket" },
  { value: "language", label: "Language" },
  { value: "discovery_surface", label: "Discovery surface" },
];

export const EXPERIMENT_METRIC_OPTIONS: LabelledOption[] = [
  { value: "average_view_percentage", label: "Average view percentage" },
  { value: "views", label: "Views" },
  { value: "engagement_rate", label: "Engagement rate" },
  { value: "likes", label: "Likes" },
  { value: "comments", label: "Comments" },
];

export const EXPERIMENT_WINDOW_OPTIONS: LabelledOption[] = [
  { value: "24h", label: "24 hours" },
  { value: "7d", label: "7 days" },
  { value: "28d", label: "28 days" },
];

export const EXPERIMENT_STATUS_FILTERS: LabelledOption[] = [
  { value: "", label: "All statuses" },
  { value: "draft", label: "Draft" },
  { value: "planned", label: "Planned" },
  { value: "active", label: "Active" },
  { value: "paused", label: "Paused" },
  { value: "completed", label: "Completed" },
  { value: "inconclusive", label: "Inconclusive" },
  { value: "cancelled", label: "Cancelled" },
];

export const EXPERIMENT_MODE_FILTERS: LabelledOption[] = [
  { value: "", label: "All types" },
  { value: "controlled", label: "Planned experiments" },
  { value: "observational", label: "Observational" },
];
