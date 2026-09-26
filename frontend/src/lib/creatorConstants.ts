/** Creator workflow constants: the result tabs, format choices and form options. */

/**
 * The results screen's tabs, in order. The tab lives in the URL (`?tab=`), so
 * a reload or a shared link opens the same view.
 */
export const RESULT_TABS = [
  { key: "package", label: "Package" },
  { key: "compare", label: "Compare options" },
  { key: "research", label: "Research and insights" },
  { key: "publish", label: "Before you publish" },
] as const;

export type ResultTab = (typeof RESULT_TABS)[number]["key"];

/** Where each stage of the old eight-step flow now lives, for old `?stage=` links. */
export const STAGE_TO_TAB: Record<string, ResultTab | "setup"> = {
  idea: "setup",
  brief: "research",
  research: "research",
  angle: "research",
  packaging: "package",
  compare: "compare",
  decision: "publish",
  checklist: "publish",
};

export const PROVENANCE_FIELDS: [string, string][] = [
  ["target_audience", "Target audience"],
  ["viewer_promise", "Viewer promise"],
  ["unique_angle", "Unique angle"],
  ["proof", "Proof / footage"],
  ["video_format", "Video format"],
  ["title_style", "Title style"],
  ["thumbnail_idea", "Thumbnail direction"],
  ["exact_quote", "Exact quote"],
  ["voice_over", "Voice-over"],
  ["visual_requirements", "Visual requirements"],
  ["factual_claims", "Factual claims"],
  ["claim_restrictions", "Claim restrictions"],
];

export const CHECKLIST_ITEMS = [
  { key: "title", source: "Generated suggestion", label: "The selected title accurately matches the finished video." },
  { key: "description", source: "Generated suggestion", label: "The description is factual, readable, and contains no unsupported promise." },
  { key: "tags", source: "Generated suggestion", label: "Every tag is relevant; required Shorts tags are included only for Shorts." },
  { key: "hashtags", source: "Generated suggestion", label: "The hashtags describe this exact video and are not presented as a growth guarantee." },
  { key: "thumbnail", source: "Manual check", label: "The final thumbnail or Short cover matches the selected direction and remains readable." },
  { key: "promise", source: "Creator-confirmed", label: "The opening seconds deliver the viewer promise shown in this package." },
  { key: "claims", source: "Manual check", label: "I reviewed names, facts, rights, spelling, and misleading or guaranteed-performance claims." },
  { key: "manualPublish", source: "Creator-confirmed", label: "I understand this tool does not upload, publish, or guarantee views, CTR, reach, or growth." },
] as const;

export type ChecklistKey = (typeof CHECKLIST_ITEMS)[number]["key"];
export type ChecklistState = Record<ChecklistKey, boolean>;

export function freshChecklist(): ChecklistState {
  return Object.fromEntries(CHECKLIST_ITEMS.map((item) => [item.key, false])) as ChecklistState;
}

export const TEMPLATE_TEXT: Record<string, { label: string; text: string }> = {
  tech: {
    label: "Tech build",
    text: "How to build a full YouTube SEO automation app in Python and Tamil using Gemini AI and FastAPI.",
  },
  quote: {
    label: "Quote short",
    text: "The biggest betrayal is knowing that if you didn't find out, they would have never told you.",
  },
  growth: {
    label: "Growth story",
    text: "How I grew my YouTube channel from 0 to 10,000 subscribers in 30 days using stronger title and topic choices.",
  },
  review: {
    label: "Review list",
    text: "Top 5 AI productivity tools in 2026 that will improve coding and video creation workflows.",
  },
};

export const LANGUAGE_OPTIONS = [
  { value: "english", label: "English" },
  { value: "tamil", label: "Tamil" },
  { value: "tanglish", label: "Tanglish" },
  { value: "hindi", label: "Hindi" },
  { value: "auto", label: "Match the video language" },
];

export const VIDEO_LANGUAGE_OPTIONS = [
  { value: "english", label: "English" },
  { value: "tamil", label: "Tamil" },
  { value: "hindi", label: "Hindi" },
];

export const REGION_OPTIONS = [
  { value: "global", label: "Global" },
  { value: "india", label: "India" },
  { value: "us", label: "United States" },
  { value: "uk", label: "United Kingdom" },
];

export const TITLE_STYLE_OPTIONS = [
  { value: "balanced", label: "Balanced" },
  { value: "searchable", label: "Searchable" },
  { value: "curiosity", label: "Curiosity-led" },
];

export const VOICE_OVER_OPTIONS = [
  { value: "", label: "Not specified" },
  { value: "present", label: "Yes, someone speaks" },
  { value: "none", label: "No voice-over" },
  { value: "unknown", label: "Not decided" },
];

/** What the creator is making. "auto" sends no format and lets the backend detect it. */
export type FormatChoice = "short" | "long" | "auto";

export const FORMAT_CHOICES: { value: FormatChoice; label: string; detail: string; consequence: string }[] = [
  {
    value: "short",
    label: "Short",
    detail: "Vertical, up to 3 minutes. Quotes, quick tips, one idea.",
    consequence: "#shorts in the title, a focused tag set, no chapters.",
  },
  {
    value: "long",
    label: "Long video",
    detail: "A regular video, over 3 minutes.",
    consequence: "No #shorts; chapters only from your own timestamps.",
  },
  {
    value: "auto",
    label: "Not sure — detect it for me",
    detail: "Read from your script and details.",
    consequence: "The format is inferred from your script and labelled as inferred.",
  },
];

/**
 * Kinds of long video, as the backend spells them: each is one of its known
 * long-form formats, so choosing one also settles the length. "Other" (and
 * no choice) sends "long_form", which says long without naming a kind.
 */
export const LONG_TYPES = [
  { value: "tutorial", label: "Tutorial" },
  { value: "vlog", label: "Vlog" },
  { value: "review", label: "Review" },
  { value: "story", label: "Story" },
  { value: "challenge", label: "Challenge" },
  { value: "talking_head", label: "Talking head" },
  { value: "other", label: "Other" },
] as const;
