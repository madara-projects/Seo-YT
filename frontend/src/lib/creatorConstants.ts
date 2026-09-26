/** Workflow constants ported verbatim from the legacy Creator module. */

export const STAGES = [
  { key: "idea", label: "Idea", step: 1, hint: "Start with the script, topic, or raw video idea." },
  { key: "brief", label: "Creator Brief", step: 2, hint: "Confirm the audience, promise, angle, format, and thumbnail direction." },
  { key: "research", label: "Research", step: 3, hint: "Review returned public observations, local heuristics, and unavailable evidence." },
  { key: "angle", label: "Recommended Angle", step: 4, hint: "Review the suggested angle and the limited evidence behind it." },
  { key: "packaging", label: "Packaging", step: 5, hint: "Review and copy the generated metadata package." },
  { key: "compare", label: "Compare", step: 6, hint: "Compare title and thumbnail approaches, then choose one locally." },
  { key: "decision", label: "Decision", step: 7, hint: "Confirm what you selected, why it was suggested, and what remains unknown." },
  { key: "checklist", label: "Checklist", step: 8, hint: "Complete manual checks before publishing outside this tool." },
] as const;

export type StageKey = (typeof STAGES)[number]["key"];

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
  { value: "present", label: "Present" },
  { value: "none", label: "None" },
  { value: "unknown", label: "Unknown" },
];

export const FORMAT_OPTIONS = [
  { value: "", label: "Not specified" },
  // The backend's canonical Shorts key: brief inference, Ideas, Demand and
  // cohorts all group on it, so a differently spelled value would split them.
  { value: "youtube_shorts", label: "Short" },
  { value: "tutorial", label: "Tutorial" },
  { value: "vlog", label: "Vlog" },
  { value: "review", label: "Review" },
  { value: "story", label: "Story" },
  { value: "challenge", label: "Challenge" },
];
