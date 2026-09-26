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
  current_28_days?: { views?: number | null; estimatedMinutesWatched?: number | null } | null;
  /** Parts YouTube refused or never answered during this sync: "uploads", "analytics". */
  partial_failures?: string[];
}

export interface OwnedPerformance {
  /**
   * Present exactly when a channel is connected, even while its id and title
   * are still empty (a connection whose first lookup failed).
   */
  channel?: OwnedChannel | null;
  /** Null unless the sync belongs to the connected channel. */
  latest_sync?: LatestSync | null;
  /** Null when Analytics has no 28-day figure; never a sum of lifetime views. */
  total_views?: number | null;
  total_likes?: number | null;
  views_28_days?: number | null;
  likes_28_days?: number | null;
  lifetime_views?: number | null;
  subscribers?: number | null;
  video_count?: number | null;
  max_views?: number | null;
  /** The 28-day Analytics total, else the sum over linked videos with watch time, else null. */
  estimated_watch_minutes?: number | null;
  /** Every linked video. */
  linked_videos_count?: number | null;
  /** The linked videos that contribute to `estimated_watch_minutes`. */
  linked_videos_with_watch_time?: number | null;
  videos?: unknown[];
}

export interface SystemStatus {
  database_ok?: boolean;
  /** Null when the database could not be read. */
  snapshot_count?: number | null;
  analysis_count?: number | null;
  /** An exception type name only. */
  error?: string | null;
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
  /** Every saved package, not just this page. */
  total?: number;
  limit?: number;
  offset?: number;
}

/** The creator's recorded choice (`analysis_package_selections`). */
export interface PackageSelection {
  generated_package_id?: string | null;
  package?: {
    package_id?: string;
    title?: string;
    description?: string;
    tags?: string[];
    hashtags?: string[];
  } | null;
  selected_at?: string | null;
}

/** Measured numbers for a linked video; each is null when unknown, never 0. */
export interface LinkedPerformance {
  views?: number | null;
  likes?: number | null;
  comments?: number | null;
  shares?: number | null;
  like_rate_percent?: number | null;
  comment_rate_percent?: number | null;
  average_view_percentage?: number | null;
  average_view_duration_seconds?: number | null;
  snapshot_window?: string | null;
  captured_at?: string | null;
}

/** `linked_package_report`: the package joined to what was published and measured. */
export interface LinkedVideoReport {
  linked?: boolean;
  link_id?: number;
  /** The linked video's id. There is no `youtube_video_id` key here. */
  video_id?: string;
  ownership_verified?: boolean;
  published_at?: string | null;
  /** Public or owned metadata; any field may be null when only partial data exists. */
  youtube?: { title?: string | null; description?: string | null; tags?: string[] | null } | null;
  package_usage?: {
    attribution_status?: "creator_selected" | "unknown" | string;
    attribution_note?: string;
    generated_title?: string;
    uploaded_title?: string;
    title_match?: boolean;
    description_match_percent?: number | null;
    generated_tags?: string[];
    matching_tags?: string[];
  };
  performance?: LinkedPerformance;
  diagnosis?: {
    /** Compares completed windows only. */
    verdict?: string;
    what_worked?: string[];
    needs_improvement?: string[];
    confidence?: string;
    learning_eligible?: boolean;
    attribution_note?: string;
  };
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
  /** Null when unmeasured ("UNMEASURED"), never 0. */
  opportunity_score?: number | null;
  package?: Record<string, unknown> | null;
  selected_package?: PackageSelection | null;
  linked_video_report?: LinkedVideoReport | null;
}

/** `POST /api/history/runs/{id}/link-video`. */
export interface LinkVideoResult {
  status?: string;
  link_id?: number;
  analysis_run_id?: number;
  youtube_video_id?: string;
  /** The package this video was linked to before; the link and its evidence moved here. */
  moved_from_run_id?: number | null;
  ownership_verified?: boolean;
  ownership_state?: string;
  ownership_message?: string;
  /** Set when the link was saved but its first analytics refresh failed. */
  refresh_warning?: string | null;
}

/** `error.details` of the 409 a relink returns when it would delete collected evidence. */
export interface RelinkConflict {
  youtube_video_id?: string;
  evidence?: Record<string, number>;
}

/** One row of `GET /api/published-videos`. */
export interface PublishedVideoLink {
  id?: number;
  analysis_run_id?: number | null;
  youtube_video_id?: string;
  published_at?: string | null;
  /** The title recorded when linking, and the saved package's own title. */
  selected_title?: string | null;
  package_topic?: string | null;
  ownership_verified?: boolean;
  youtube_metadata?: { title?: string | null } | null;
  latest_performance?: {
    views?: number | null;
    avg_view_percentage?: number | null;
    snapshot_window?: string | null;
    captured_at?: string | null;
  } | null;
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
