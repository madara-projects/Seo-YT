/**
 * Domain view models for the `/analyze` payload.
 *
 * The nested structures arrive as bare `dict` in the Pydantic models, so the
 * generated `schema.d.ts` types them as `Record<string, never>`, which would
 * make every real field access a type error. These interfaces describe the
 * shapes the UI actually reads, and every field is optional because the
 * backend's contract is to omit what it cannot evidence rather than to invent
 * a value. The request body is built by `toAnalyzePayload` in
 * `schemas/creator.ts`.
 */

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
  view_count?: number | string | null;
  /** Null when the result could not be scored; unscored rows come last. */
  outlier_score?: number | null;
  views_per_day?: number | null;
  views_per_subscriber?: number | null;
  engagement_density?: number | null;
  retention_proxy?: number | null;
  /** Null when the channel hides it. */
  subscriber_count?: number | null;
  /** When the statistics were fetched (ISO, UTC). */
  captured_at?: string | null;
}

export interface TopOpportunity {
  title?: string;
  outlier_score?: number | null;
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

/** The final quality gate's verdict on one title. */
export interface QualityGate {
  status?: "pass" | "fail" | "not_evaluated" | string;
  source?: "final_quality_gate" | "writer_quality_gate" | "package_builder_checks" | "none" | string;
  issues?: unknown[];
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
  /** "low", "high" or "not evaluated"; "not evaluated" is never a pass. */
  misleading_risk?: string;
  /** "approved", "rejected" or "not evaluated". */
  quality_status?: string;
  mechanism?: string;
  reason?: string;
  evidence_used?: Record<string, unknown>;
  tradeoffs?: unknown[];
  quality_gate?: QualityGate;
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
    /** "unavailable" when no on-screen text or first visual was supplied. */
    status?: string;
    /** Why it wasn't analysed, when it wasn't. */
    reason?: string;
    score?: number | null;
    readability?: string;
    text_word_count?: number;
    estimated_single_read_seconds?: number | null;
    visual_analysis_basis?: string;
    /** Where the first-frame text came from: the brief's field provenance. */
    provenance?: ProvenanceSource | string;
  };
  pacing?: {
    status?: string;
    format_assessment?: string;
    word_count?: number;
    estimated_spoken_seconds?: number;
    /** Null when the creator gave no duration. */
    duration_seconds?: number | null;
    timing_confidence?: string;
  };
  quote_presentation?: {
    status?: string;
    reason?: string;
    word_count?: number;
    estimated_single_read_seconds?: number;
    /** Null when no on-screen text was supplied to check against. */
    exact_text_preserved_on_screen?: boolean | null;
    attribution?: string;
    provenance?: ProvenanceSource | string;
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

/** One tag the keyword research selected, with how far public results back it. */
export interface SelectedKeyword {
  keyword?: string;
  /** "platform_format" marks the yt/shorts discovery tags, which are not subject tags. */
  classification?: string;
  /** Sampled public results whose metadata carries the phrase; never search volume. */
  evidence_count?: number | null;
  demand_validated?: boolean;
}

/** `keyword_research`: how the final tags were chosen. */
export interface KeywordResearch {
  /** "youtube_evidence" when sampled public results were available, else "semantic_only". */
  status?: string;
  confidence?: string;
  evidence_scope?: string;
  search_volume_available?: boolean;
  selected_keywords?: SelectedKeyword[];
  limitations?: string[];
}

/** `pacing_analysis`: a spoken script's pace, or a quote Short's readability. */
export interface PacingAnalysis {
  analysis_type?: "spoken_script" | "quote_short" | string;
  pace_label?: string | null;
  avg_sentence_length?: number | null;
  hook_density?: string | null;
  pattern_interrupts?: number | null;
  recommended_read_time_seconds?: number | null;
  recommendation?: string | null;
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
  keyword_research?: KeywordResearch;
  pacing_analysis?: PacingAnalysis;
  ctr_prediction?: { title_quality_score?: number | null };
  opportunity_gap_analysis?: { opportunity_score?: { score?: number | null; label?: string } };

  [key: string]: unknown;
}

/** A comparable package option derived from the analysis payload. */
export interface PackageOption {
  /** Unique among the options; the server's package ID when there is one. */
  id: string;
  /**
   * The ID the server knows this package by, or null for a title-only
   * alternative, which the server cannot record as a selection.
   */
  packageId: string | null;
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
