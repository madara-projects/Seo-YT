import { z } from "zod";

/**
 * Creator form contract.
 *
 * The text limits mirror the Pydantic `AnalyzeRequest` model, so a value the
 * backend would reject with a 422 is caught in the field instead. The 40-
 * character caps on the language and region choices are this form's own:
 * the backend sets none, and the selects only produce short keys.
 *
 * Note: the API also accepts `on_screen_text` and `audience_type`, but the
 * legacy form never wired them up. They are left out here to keep strict
 * parity with the interface being replaced; wiring them in is a deliberate
 * product decision, not a migration detail.
 */
export const creatorFormSchema = z.object({
  script: z
    .string()
    .trim()
    .min(1, "Enter a script or video idea first.")
    .max(12000, "Scripts are limited to 12,000 characters."),
  video_language: z.string().max(40).default("english"),
  language: z.string().max(40).default("english"),
  region: z.string().max(40).default("global"),
  target_audience: z.string().trim().max(200, "Limited to 200 characters.").default(""),
  viewer_promise: z.string().trim().max(300, "Limited to 300 characters.").default(""),
  unique_angle: z.string().trim().max(300, "Limited to 300 characters.").default(""),
  proof: z.string().trim().max(300, "Limited to 300 characters.").default(""),
  video_format: z.string().trim().max(80, "Limited to 80 characters.").default(""),
  title_style: z.string().trim().max(80).default("balanced"),
  thumbnail_idea: z.string().trim().max(200, "Limited to 200 characters.").default(""),
  duration_seconds: z
    .string()
    .trim()
    .default("")
    .refine(
      (value) => {
        if (!value) return true;
        const parsed = Number(value);
        return Number.isFinite(parsed) && parsed >= 1 && parsed <= 86400;
      },
      { message: "Enter a duration between 1 and 86400 seconds." },
    ),
  exact_quote: z.string().trim().max(2000, "Limited to 2,000 characters.").default(""),
  voice_over: z.string().trim().max(20).default(""),
  visual_requirements: z.string().trim().max(500, "Limited to 500 characters.").default(""),
  factual_claims: z.string().trim().max(1000, "Limited to 1,000 characters.").default(""),
  claim_restrictions: z.string().trim().max(1000, "Limited to 1,000 characters.").default(""),
  creator_intent: z.string().trim().max(500, "Limited to 500 characters.").default(""),
  content_constraints: z.string().trim().max(1000, "Limited to 1,000 characters.").default(""),
});

export type CreatorFormValues = z.infer<typeof creatorFormSchema>;

export const creatorFormDefaults: CreatorFormValues = {
  script: "",
  video_language: "english",
  language: "english",
  region: "global",
  target_audience: "",
  viewer_promise: "",
  unique_angle: "",
  proof: "",
  video_format: "",
  title_style: "balanced",
  thumbnail_idea: "",
  duration_seconds: "",
  exact_quote: "",
  voice_over: "",
  visual_requirements: "",
  factual_claims: "",
  claim_restrictions: "",
  creator_intent: "",
  content_constraints: "",
};

/** Optional fields are only sent when filled, matching the legacy payload. */
const OPTIONAL_PAYLOAD_FIELDS = [
  "target_audience",
  "viewer_promise",
  "unique_angle",
  "proof",
  "video_format",
  "title_style",
  "thumbnail_idea",
  "duration_seconds",
  "exact_quote",
  "voice_over",
  "visual_requirements",
  "factual_claims",
  "claim_restrictions",
  "creator_intent",
  "content_constraints",
] as const;

export function toAnalyzePayload(values: CreatorFormValues): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    script: values.script,
    video_language: values.video_language || "english",
    language: values.language || "english",
    region: values.region || "global",
  };

  for (const field of OPTIONAL_PAYLOAD_FIELDS) {
    const value = values[field];
    if (!value) continue;
    // The backend types this one as a number; everything else is a string.
    payload[field] = field === "duration_seconds" ? Number(value) : value;
  }

  return payload;
}
