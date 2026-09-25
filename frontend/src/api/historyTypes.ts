/**
 * View models for the History and Dashboard payloads.
 *
 * Same reasoning as `types.ts`: the generated OpenAPI schema types these
 * endpoints as bare objects because the Pydantic models return plain dicts.
 * Every field is optional or explicitly nullable — the backend omits or nulls
 * what it cannot evidence, and the UI must render that as "Unavailable"
 * rather than as a zero.
 */

export interface RecentRun {
  id: number;
  title?: string;
  title_score?: number | null;
  opportunity_score?: number | null;
  created_at?: string;
}

export interface AngleEffectiveness {
  content_angle?: string;
  run_count?: number;
  avg_title_score?: number | null;
}

export interface WinningTitle {
  title?: string;
  title_score?: number | null;
  opportunity_label?: string;
}

export interface RetentionPattern {
  retention_risk?: string;
  count?: number;
}

export interface LearningSummary {
  angle_effectiveness?: AngleEffectiveness[];
  winning_titles?: WinningTitle[];
  retention_pattern?: RetentionPattern[];
  recent_runs?: RecentRun[];
}

export interface Scorecard {
  total_runs?: number;
  avg_title_score?: number | null;
  avg_opportunity_score?: number | null;
  recent_title_score_avg?: number | null;
  recent_opportunity_score_avg?: number | null;
  title_score_delta_vs_previous_window?: number | null;
  opportunity_delta_vs_previous_window?: number | null;
  dominant_opportunity_label?: string | null;
  dominant_retention_risk?: string | null;
  score_trend?: string;
}

export interface OwnedChannel {
  id?: string;
  title?: string;
}

export interface LatestSync {
  synced_at?: string | null;
  channel?: OwnedChannel;
  period?: { start?: string; end?: string };
  current_28_days?: { views?: number | null; estimatedMinutesWatched?: number | null };
}

export interface OwnedPerformance {
  channel?: OwnedChannel | null;
  latest_sync?: LatestSync | null;
  total_views?: number | null;
  total_likes?: number | null;
  views_28_days?: number | null;
  likes_28_days?: number | null;
  lifetime_views?: number | null;
  subscribers?: number | null;
  video_count?: number | null;
  max_views?: number | null;
  estimated_watch_minutes?: number | null;
  linked_videos_count?: number | null;
  videos?: unknown[];
}

export interface SystemStatus {
  database_path?: string;
  database_ok?: boolean;
  snapshot_count?: number;
  analysis_count?: number;
}

export interface HistorySummary {
  learning?: LearningSummary;
  scorecard?: Scorecard;
  owned_performance?: OwnedPerformance;
  status?: SystemStatus;
}

export interface HistoryRun {
  id: number;
  created_at?: string;
  title?: string;
  opportunity_score?: number | null;
  title_score?: number | null;
  query?: string;
  has_full_package?: boolean;
  linked_video_link_id?: number | null;
  linked_youtube_video_id?: string | null;
  selected_package_id?: string | null;
  package_selected_at?: string | null;

  /**
   * Shown on each row and matched by search. Older records may have neither,
   * and the list then falls back to "General".
   */
  content_angle?: string | null;
  intent?: string | null;
}

export interface HistoryRunsResponse {
  runs?: HistoryRun[];
  limit?: number;
  offset?: number;
}

export interface HistoryRunDetail {
  id: number;
  created_at?: string;
  query?: string;
  intent?: string;
  content_angle?: string;
  title?: string;
  title_score?: number | null;
  retention_risk?: string | null;
  opportunity_label?: string | null;
  opportunity_score?: number | null;
  package?: Record<string, unknown> | null;
  linked_video?: Record<string, unknown> | null;
  [key: string]: unknown;
}

export interface PublishedVideoLink {
  id?: number;
  analysis_run_id?: number | null;
  youtube_video_id?: string;
  title?: string;
  verified?: boolean;
  published_at?: string | null;
  latest_snapshot?: Record<string, unknown> | null;
  /** The title recorded when linking, and the saved package's own title. */
  selected_title?: string | null;
  package_topic?: string | null;
  ownership_verified?: boolean;
  youtube_metadata?: { title?: string } | null;
  latest_performance?: {
    views?: number | null;
    avg_view_percentage?: number | null;
    snapshot_window?: string | null;
    captured_at?: string | null;
  } | null;
  [key: string]: unknown;
}

export interface PublishedVideosResponse {
  links?: PublishedVideoLink[];
  total?: number;
}

export interface CohortLearning {
  format?: string;
  language?: string;
  duration_bucket?: string;
  topic_category?: string;
  snapshot_window?: string;
  sample_size?: number;
  confidence_label?: string;
  confidence_level?: string;
  learning_allowed?: boolean;
  next_threshold?: number | null;
  median_views?: number | null;
  median_retention_percentage?: number | null;
  median_likes?: number | null;
  total_linked?: number;
  total_links_considered?: number;
  excluded_count?: number;
  metadata_sources?: Record<string, unknown>;
  recommendation?: string;
}
