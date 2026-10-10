/**
 * AI Shorts (`/api/ai-shorts`): a quote in, Google Flow (Veo 3.1) prompts and
 * an SEO package out. One plan is one Short; its parts are the 8-second clips
 * Flow generates, chained with Extend.
 *
 * Every nested field is optional for the same reason as `types.ts`: the
 * backend omits what it could not write rather than inventing a value, and
 * the UI shows that honestly.
 */
import type { AiShortsRunMarker, TitleThumbnailPackage } from "./types";

export type FlowMode = "text_to_video" | "extend";

export interface AiShortsMood {
  feeling?: string;
  keywords?: string[];
  visual_metaphor?: string;
  palette?: string;
  pace?: string;
}

/** One 8-second part: the prompt pasted into Flow for it. */
export interface AiShortsShot {
  part: number;
  seconds: number;
  title?: string;
  prompt: string;
  /** "text_to_video" starts the video; "extend" continues the previous part's clip. */
  flow_mode?: FlowMode | string;
  /** What must carry over from the previous part, for an extend. */
  continuity?: string | null;
}

export interface AiShortsAudio {
  style?: string;
  description?: string;
}

/** Which lines of the quote show during one part. The wording is never changed. */
export interface AiShortsOverlay {
  part: number;
  /** "0-8", "8-16"… */
  seconds?: string;
  lines?: string[];
}

export interface AiShortsChecks {
  passed?: boolean;
  issues?: string[];
  warnings?: string[];
}

/** Items the quality gate reports; the backend sends strings or small objects. */
export type QualityNote = string | { message?: string; reason?: string; code?: string; [key: string]: unknown };

export interface AiShortsGenerationQuality {
  verdict?: "GREEN" | "YELLOW" | "RED" | string;
  warnings?: QualityNote[];
  issues?: QualityNote[];
  final_seo_quality?: Record<string, unknown>;
}

export interface AiShortsPackage {
  title?: string;
  title_variants?: string[];
  description?: string;
  tags?: string[];
  hashtags?: string[];
  title_thumbnail_packages?: TitleThumbnailPackage[];
  generation_quality?: AiShortsGenerationQuality;
  generation_source?: string;
  /** The package is the History run's payload, marked as written here. */
  source_page?: string;
  ai_shorts?: AiShortsRunMarker | null;
}

/** `POST /api/ai-shorts/generate` and `GET /api/ai-shorts/plans/{id}`. */
export interface AiShortsPlan {
  id: number;
  /** The History run the package was saved under; null if that save failed. */
  analysis_run_id: number | null;
  created_at: string;
  quote: string;
  language: string;
  /** The creator's mood or scene wish the plan was written with; "" when none, absent on older plans. */
  mood_hint?: string;
  creative_direction?: {
    quote_meaning: string;
    scene: string;
    why_it_fits: string;
    opening: string;
    middle: string;
    ending: string;
    /** The feeling in a few words; absent on plans written before it was asked for. */
    emotion?: string | null;
    /** One word from the planner's fixed list (sad, hopeful, healing, ...); null when Gemini gave none. */
    tone?: string | null;
    /** How viewers search for this kind of quote; absent on older plans. */
    search_themes?: string[] | null;
  };
  /**
   * Gemini's reading of the quote, kept even when its scene was thrown away
   * (a symbol) and the plan has no creative direction; absent on older plans.
   */
  quote_understanding?: {
    quote_meaning: string;
    emotion?: string | null;
    tone?: string | null;
    search_themes?: string[] | null;
  };
  parts: number;
  /** Null when the stored plan could not be read. */
  total_seconds: number | null;
  mood?: AiShortsMood;
  shots: AiShortsShot[];
  negative_prompt?: string;
  audio?: AiShortsAudio;
  text_overlay_plan?: AiShortsOverlay[];
  flow_steps?: string[];
  cautions?: string[];
  checks?: AiShortsChecks;
  /** "fallback" is the built-in template, written when Gemini was unavailable. */
  generation_source?: "gemini" | "fallback" | string;
  provider?: Record<string, unknown>;
  package?: AiShortsPackage;
}

/** One row of `GET /api/ai-shorts/plans`. */
export interface AiShortsPlanSummary {
  id: number;
  analysis_run_id: number | null;
  quote: string;
  language: string;
  parts: number;
  /** Read from the stored plan: null when that could not be read. */
  total_seconds: number | null;
  generation_source?: string;
  package_title?: string | null;
  created_at: string;
}

export interface AiShortsPlansResponse {
  plans: AiShortsPlanSummary[];
}

/** The body of `POST /api/ai-shorts/generate`. */
export interface AiShortsGenerateRequest {
  quote: string;
  language: string;
  parts: number;
  mood_hint?: string;
  region: string;
}
