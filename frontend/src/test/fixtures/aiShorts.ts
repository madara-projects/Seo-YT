import type { AiShortsPlan, AiShortsPlanSummary } from "../../api/aiShortsTypes";

/**
 * One AI Shorts plan as `POST /api/ai-shorts/generate` returns it: a two-part
 * (16 s) quote Short written with Gemini, with its Flow prompts and package.
 * Shared by the Vitest page test and the Playwright spec, so neither calls
 * Gemini.
 */
export const AI_SHORTS_PLAN: AiShortsPlan = {
  id: 31,
  analysis_run_id: 4201,
  created_at: "2026-09-28T09:12:44+00:00",
  quote: "The biggest betrayal is knowing that if you didn't find out, they would have never told you.",
  language: "english",
  mood_hint: "",
  parts: 2,
  total_seconds: 16,
  mood: {
    feeling: "quiet betrayal, the moment after",
    keywords: ["hollow", "still", "late night", "unsaid"],
    visual_metaphor: "A phone face-down on a kitchen table, its screen lighting the dark once and going out.",
    palette: "deep navy, sodium-orange street light, one cold white glow",
    pace: "slow, one movement per part",
  },
  shots: [
    {
      part: 1,
      seconds: 8,
      title: "The table, before",
      prompt:
        "Cinematic vertical 9:16 video, 8 seconds. A dim kitchen at night, a phone lying face-down on a wooden table. Slow push-in from across the room. Sodium-orange street light through rain-streaked blinds, deep navy shadows. Shallow depth of field, 35mm, slight film grain. No people, no text, no captions. Quiet, still, held breath.",
      flow_mode: "text_to_video",
      continuity: null,
    },
    {
      part: 2,
      seconds: 8,
      title: "The screen lights once",
      prompt:
        "Continue the same shot, 8 seconds. The phone screen lights up face-down, a cold white glow spilling across the wood grain for two seconds, then fades to black. The camera keeps its slow push-in and settles. Same kitchen, same rain light, same grain. No people, no text, no captions.",
      flow_mode: "extend",
      continuity: "Same table, same framing and light as Part 1; the camera is still moving in when the screen glows.",
    },
  ],
  negative_prompt: "people, faces, hands, text, captions, subtitles, logos, watermark, fast cuts, camera shake, daylight",
  audio: {
    style: "ambient, no music",
    description: "Rain on glass, a refrigerator hum, one faint phone vibration in Part 2. No voice, no music.",
  },
  text_overlay_plan: [
    { part: 1, seconds: "0-8", lines: ["The biggest betrayal is knowing"] },
    { part: 2, seconds: "8-16", lines: ["that if you didn't find out,", "they would have never told you."] },
  ],
  flow_steps: [
    "Open Google Flow and start a new project.",
    "Choose Text to Video, Veo 3.1, vertical 9:16, 8 seconds.",
    "Paste the Part 1 prompt and generate; pick the take with the steadiest push-in.",
    "Use Extend on that take and paste the Part 2 prompt.",
    "Download the 16-second clip and add the quote lines in your editor, word for word.",
    "Upload as a Short with the package below.",
  ],
  cautions: [
    "Flow renders what it reads literally: keep the negative prompt handy if people or text appear.",
    "Veo adds its own audio; mute it if you add music, so the rain and hum don't double.",
  ],
  checks: {
    passed: true,
    issues: [],
    warnings: ["Part 2 continues a face-down phone; an Extend may re-light the screen earlier than written."],
  },
  generation_source: "gemini",
  provider: { name: "gemini", model: "gemini-2.5-flash" },
  package: {
    title: "The betrayal you were never meant to find #shorts",
    title_variants: ["They would have never told you", "What silence hides"],
    description:
      "They would have never told you. A 16-second quote Short on the quiet kind of betrayal.\n\n#shorts #betrayal #quotes",
    tags: ["betrayal quotes", "quote shorts", "trust", "shorts"],
    hashtags: ["#shorts", "#betrayal", "#quotes"],
    title_thumbnail_packages: [
      { package_id: "package-a", title: "The betrayal you were never meant to find #shorts", thumbnail_text: "They never told you" },
      { package_id: "package-b", title: "They would have never told you", thumbnail_text: "If you hadn't found out" },
    ],
    generation_quality: {
      verdict: "GREEN",
      warnings: [],
      issues: [],
      final_seo_quality: { status: "pass" },
    },
    generation_source: "gemini",
  },
};

/** The same plan when Gemini was unavailable and the built-in template wrote it. */
export const AI_SHORTS_FALLBACK_PLAN: AiShortsPlan = {
  ...AI_SHORTS_PLAN,
  id: 32,
  analysis_run_id: 4202,
  mood_hint: "rain on a window",
  generation_source: "fallback",
  provider: { name: "fallback" },
  checks: { passed: true, issues: [], warnings: [] },
  package: {
    ...AI_SHORTS_PLAN.package,
    generation_source: "fallback",
    generation_quality: { verdict: "YELLOW", warnings: ["Built-in template; review the title before you upload."], issues: [] },
  },
};

/** `GET /api/ai-shorts/plans`: the newest plans, as the list shows them. */
export const AI_SHORTS_PLAN_SUMMARIES: AiShortsPlanSummary[] = [
  {
    id: 31,
    analysis_run_id: 4201,
    quote: AI_SHORTS_PLAN.quote,
    language: "english",
    parts: 2,
    total_seconds: 16,
    generation_source: "gemini",
    package_title: AI_SHORTS_PLAN.package?.title ?? null,
    created_at: AI_SHORTS_PLAN.created_at,
  },
  {
    id: 30,
    analysis_run_id: 4199,
    quote: "Some silences are louder than words.",
    language: "tamil",
    parts: 1,
    total_seconds: 8,
    generation_source: "fallback",
    package_title: "Some silences are louder than words #shorts",
    created_at: "2026-09-27T18:40:00+00:00",
  },
];
