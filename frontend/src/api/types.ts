/**
 * Domain view models for the `/analyze` payload.
 *
 * `schema.d.ts` is generated from the live FastAPI OpenAPI document and is the
 * source of truth for the request contract and top-level scalars. The nested
 * structures arrive as bare `dict` in the Pydantic models, so openapi-typescript
 * renders them as `Record<string, never>` — which would make every real field
 * access a type error. These interfaces describe the shapes the UI actually
 * reads, and every field is optional because the backend's contract is to omit
 * what it cannot evidence rather than to invent a value.
 */
import type { components } from "./schema";

export type AnalyzeRequest = components["schemas"]["AnalyzeRequest"];

export type ProvenanceSource = "creator_supplied" | "inferred" | "unknown" | "unavailable";

export interface CreatorBrief {
  target_audience?: string;
  viewer_promise?: string;
  unique_angle?: string;
  proof?: string;
  video_format?: string;
  title_style?: string;
  thumbnail_idea?: string;
  exact_quote?: string;
  voice_over?: string;
  visual_requirements?: string;
  factual_claims?: string;
  claim_restrictions?: string;
  field_provenance?: Record<string, { source?: ProvenanceSource } | undefined>;
}

export interface ResearchQuery {
  type?: string;
  query?: string;
}

export interface RepeatedTitlePattern {
  pattern?: string;
  count?: number;
}

export interface SmallChannelWinner {
  title?: string;
  channel?: string;
  views?: number;
}

export interface ResearchDecision {
  recommended_angle?: string;
  reason?: string;
  confidence?: string;
  dominant_competitor_pattern?: string;
  repeated_title_patterns?: RepeatedTitlePattern[];
  small_channel_winners?: SmallChannelWinner[];
  avoid?: string[];
}

export interface YoutubeResult {
  video_id?: string;
  title?: string;
  channel_title?: string;
  published_at?: string;
  view_count?: number;
  outlier_score?: number;
}

export interface TopOpportunity {
  title?: string;
  outlier_score?: number;
  opportunity_reasons?: string[];
}

export interface KeywordSignal {
  keyword?: string;
  mentions?: number;
  strength?: number | string;
}

export interface EntitySignal {
  entity?: string;
  type?: string;
  mentions?: number;
}

export interface ThumbnailIntelligence {
  quality_counts?: { maxres?: number; high?: number; medium?: number; default?: number };
  low_resolution_count?: number;
  recommendation?: string;
}

export interface TitleOptimization {
  scored_variants?: { title?: string; score?: number }[];
}

export interface UploadTiming {
  recommended_day?: string;
  recommended_time?: string;
  timezone?: string;
  today_time?: string;
  today_timezone?: string;
  today_recommendation?: string;
  basis?: string;
  explanation?: string;
  confidence?: string;
}

export interface TitleThumbnailPackage {
  package_id?: string;
  title?: string;
  thumbnail_text?: string;
  thumbnail_visual?: string;
  viewer_promise?: string;
  why_click?: string;
  approach?: string;
  package_intent?: string;
  best_for?: string;
  misleading_risk?: string;
  quality_status?: string;
  mechanism?: string;
  reason?: string;
  evidence_used?: Record<string, unknown>;
  tradeoffs?: unknown[];
  quality_gate?: Record<string, unknown>;
}

export interface LanguagePackage {
  title?: string;
  description?: string;
  tags?: string[];
  hashtags?: string[];
  variants?: string[];
}

export interface RetentionRisk {
  stage?: string;
  risk_code?: string;
  severity?: "high" | "medium" | "low" | string;
  explanation?: string;
  evidence?: string;
  recommendation?: string;
}

export interface RetentionAssistant {
  risk_level?: string;
  disclaimer?: string;
  rule_version?: string;
  opening?: { score?: number | null; clarity?: string; specificity?: string; generic_setup?: boolean };
  first_frame?: {
    status?: string;
    readability?: string;
    text_word_count?: number;
    estimated_single_read_seconds?: number;
    visual_analysis_basis?: string;
  };
  pacing?: {
    format_assessment?: string;
    word_count?: number;
    estimated_spoken_seconds?: number;
    duration_seconds?: number;
    timing_confidence?: string;
  };
  quote_presentation?: {
    status?: string;
    reason?: string;
    word_count?: number;
    estimated_single_read_seconds?: number;
    exact_text_preserved_on_screen?: string;
    attribution?: string;
  };
  retention_learning?: {
    learning_allowed?: boolean;
    status?: string;
    message?: string;
    sample_size?: number;
    minimum_samples?: number;
    patterns?: { feature?: string; value?: string; observation?: string }[];
  };
  package_alignment?: { package_id?: string; status?: string; opening_similarity?: string }[];
  risk_map?: { stage?: string; risks?: RetentionRisk[] }[];
  recommendations?: { recommendation?: string; priority?: string }[];
  alternatives?: { alternative_code?: string; structure?: string; preserves_source?: string }[];
}

export interface GenerationQuality {
  status?: string;
  passed?: boolean;
  repairable?: boolean;
  issues?: unknown[];
  warnings?: unknown[];
  accepted_candidates?: { title?: string; mechanism?: string; source?: string }[];
  rejected_candidates?: unknown[];
}

/** The full `/analyze` response as the Creator workflow consumes it. */
export interface AnalyzeResponse {
  title: string;
  description: string;
  tags: string[];
  hashtags: string[];
  intent?: string;
  content_angle?: string;
  title_variants?: string[];
  cache_policy?: string;
  generation_source?: "gemini" | "fallback" | string;
  research_warnings?: string[];
  history_run_id?: number;

  creator_brief?: CreatorBrief;
  research_queries?: ResearchQuery[];
  research_decision?: ResearchDecision;
  youtube_results?: YoutubeResult[];
  top_opportunities?: TopOpportunity[];
  keyword_signals?: KeywordSignal[];
  entity_signals?: EntitySignal[];
  thumbnail_intelligence?: ThumbnailIntelligence;
  title_optimization?: TitleOptimization;
  title_thumbnail_packages?: TitleThumbnailPackage[];
  multilang?: Record<string, LanguagePackage>;
  upload_timing?: UploadTiming;
  retention_assistant?: RetentionAssistant;
  generation_quality?: GenerationQuality;
  ctr_prediction?: { title_quality_score?: number };
  opportunity_gap_analysis?: { opportunity_score?: { score?: number } };

  [key: string]: unknown;
}

/** A comparable package option derived from the analysis payload. */
export interface PackageOption {
  id: string;
  label: string;
  primary: boolean;
  title: string;
  description: string;
  tags: string[];
  hashtags: string[];
  language: string;
  thumbnailText: string;
  thumbnailVisual: string;
  viewerPromise: string;
  whySuggested: string;
  approach: string;
  packageIntent: string;
  bestFor: string;
  misleadingRisk: string;
  qualityStatus: string;
  titleQualityScore: number | null;
  source: string;
  mechanism: string;
  reason: string;
}

export type SelectionStatus = "unrecorded" | "saving" | "saved" | "error";
export type ResearchStatus = "loading" | "available" | "no-research" | "unavailable" | "error";
