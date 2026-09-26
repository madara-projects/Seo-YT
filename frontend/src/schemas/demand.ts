import { z } from "zod";

/**
 * Demand research form. Limits mirror the Pydantic `DemandResearchRequest`,
 * so a value the backend would reject with a 422 is caught in the field.
 */
export const demandFormSchema = z.object({
  topic: z
    .string()
    .trim()
    .min(1, "Enter a topic or phrase to research.")
    .max(300, "Topics are limited to 300 characters."),
  language: z.string().max(40).default(""),
  format: z.string().max(40).default(""),
  region: z.string().max(40).default(""),
  audience_context: z.string().trim().max(500, "Limited to 500 characters.").default(""),
});

export type DemandFormValues = z.infer<typeof demandFormSchema>;

export const demandFormDefaults: DemandFormValues = {
  topic: "",
  language: "",
  format: "",
  region: "",
  audience_context: "",
};

/**
 * An empty option leaves the choice to the backend, which does not mean
 * "any": a blank language is researched in English, a blank region as global,
 * and a blank format adds no format to the queries. The labels say so.
 *
 * The legacy form took free text, but the research engine only acts on the
 * values listed here: `tamil` and `tanglish` add Tamil queries, and each
 * region changes query planning, keyword priorities or search suggestions.
 * Anything else was saved and then ignored, so these are choices instead.
 */
export const DEMAND_LANGUAGE_OPTIONS = [
  { value: "", label: "English (default)" },
  { value: "english", label: "English" },
  { value: "tamil", label: "Tamil" },
  { value: "tanglish", label: "Tanglish" },
  { value: "hindi", label: "Hindi" },
];

export const DEMAND_FORMAT_OPTIONS = [
  { value: "", label: "Any format" },
  { value: "youtube_shorts", label: "YouTube Short" },
  { value: "long_form", label: "Long form" },
];

export const DEMAND_REGION_OPTIONS = [
  { value: "", label: "Any region" },
  { value: "india", label: "India" },
  { value: "tamil nadu", label: "Tamil Nadu" },
  { value: "sri lanka", label: "Sri Lanka" },
  { value: "gulf", label: "Gulf countries" },
  { value: "us", label: "United States" },
  { value: "uk", label: "United Kingdom" },
];
