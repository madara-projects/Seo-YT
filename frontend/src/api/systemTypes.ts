/**
 * View models for the Settings and Channel pages.
 *
 * Like `historyTypes.ts`, these describe what the backend actually returns
 * from plain dicts. Every field is optional: several are absent until a
 * service has run once, and the UI must say "not run yet" rather than show 0.
 */

export interface HealthStatus {
  status?: "ok" | "degraded" | string;
  app_name?: string;
  version?: string;
  environment?: string;
  uptime_seconds?: number;
  database_ok?: boolean;
  /** null when no Redis is configured, which is a supported setup. */
  cache_ok?: boolean | null;
}

export interface ProviderHealth {
  transient_failure_count?: number;
  cooldown_active?: boolean;
  cooldown_remaining_seconds?: number;
  last_failure_category?: string | null;
}

export interface GeminiDiagnostics {
  configured?: boolean;
  model?: string | null;
  provider_health?: ProviderHealth;
  /** The research calls' own health, tracked apart from package writing. */
  research_provider_health?: ProviderHealth;
}

export interface CollectorCounts {
  links?: number;
  windows?: number;
  captured?: number;
  failed?: number;
}

export interface CollectorStatus {
  state?: string;
  enabled?: boolean;
  dry_run?: boolean;
  running?: boolean;
  last_started_at?: string | null;
  last_finished_at?: string | null;
  next_run_at?: string | null;
  last_error?: string | null;
  last_counts?: CollectorCounts;
}

export interface CloudSyncCounts {
  queued?: number;
  pushed?: number;
  pulled?: number;
  failed?: number;
  conflicts?: number;
  /** Remote rows this version could not apply. */
  skipped?: number;
}

export interface CloudSyncStatus {
  state?: string;
  enabled?: boolean;
  configured?: boolean;
  running?: boolean;
  device_id?: string;
  last_started_at?: string | null;
  last_finished_at?: string | null;
  next_run_at?: string | null;
  last_error?: string | null;
  last_counts?: CloudSyncCounts;
  last_activity_at?: string | null;
  remote_packages?: number | null;
  pending_uploads?: number | null;
  pending_deletions?: number | null;
  local_packages?: number | null;
  mapped_packages?: number | null;
  synced_packages?: number | null;
  conflicts_detected?: number | null;
  /** Runs in a row that could not reach the cloud; the retry wait doubles with each. */
  consecutive_failures?: number;
  retry_delay_seconds?: number | null;
}

export interface CloudSyncRunResult {
  state?: string;
  counts?: CloudSyncCounts;
}

/**
 * What a package deletion reports about cloud sync: the status at the moment
 * of the delete. Its `state` is the last finished run's, so it cannot prove
 * the deletion reached the cloud.
 */
export interface DeletionCloudSync extends CloudSyncStatus {
  /** True when the background sync was woken to push the deletion soon. */
  run_requested?: boolean;
}

export interface SettingsStatus {
  app?: { name?: string; version?: string; environment?: string };
  database?: {
    /** The real state of the database, not a constant. */
    healthy?: boolean;
    /** An exception type name, or null. */
    error?: string | null;
    name?: string;
    /** Null when the database is unhealthy. */
    schema_version?: number | null;
    size_bytes?: number | null;
    counts?: {
      packages?: number;
      ideas?: number;
      published_links?: number;
      performance_snapshots?: number;
    } | null;
    last_backup_at?: string | null;
  };
  providers?: {
    gemini?: GeminiDiagnostics;
    youtube_data_api?: { configured?: boolean; key_count?: number };
    local_fallback?: { available?: boolean };
    redis?: { configured?: boolean };
  };
  collector?: CollectorStatus;
  // `youtube_oauth` and `cloud_sync` are also sent, but Settings reads the
  // channel and cloud sync from their own status endpoints, so they aren't typed.
}

/** `POST /diagnostics`: one live YouTube request (1 quota unit), so it runs on demand only. */
export interface LiveDiagnostics {
  youtube?: {
    status?: "ok" | "missing_api_key" | "error" | string;
    error?: string | null;
    active_key_index?: number | null;
    available_key_count?: number;
    warning?: string | null;
    quota_date?: string;
  };
  gemini?: GeminiDiagnostics;
}

/* ----------------------------- Channel ------------------------------------ */

/** YouTube Analytics totals for one 28-day window. Absent when the query failed. */
export interface ChannelMetrics {
  views?: number;
  estimatedMinutesWatched?: number;
  /** Seconds. */
  averageViewDuration?: number;
  subscribersGained?: number;
  likes?: number;
  comments?: number;
}

export interface ChannelVideo {
  video_id?: string;
  title?: string;
  published_at?: string;
  /** Null when YouTube did not report the count (hidden likes, a failed lookup). */
  views?: number | null;
  likes?: number | null;
  comments?: number | null;
  averageViewPercentage?: number | null;
}

export interface LearningVideo {
  video_id?: string;
  title?: string;
  published_at?: string;
  views?: number | null;
  views_per_day?: number | null;
  average_view_percentage?: number | null;
  likes?: number | null;
  comments?: number | null;
  age_hours?: number;
  snapshot_window?: string;
}

export interface VideoLearning {
  sample_size?: number;
  connected_video_count?: number;
  linked_video_count?: number;
  confidence?: string;
  confidence_label?: string;
  learning_allowed?: boolean;
  snapshot_window?: string;
  /** Empty until the sample reaches five and learning is allowed. */
  best_videos?: LearningVideo[];
  weakest_videos?: LearningVideo[];
  recommendation?: string;
}

export interface ChannelSyncData {
  channel?: {
    id?: string;
    title?: string;
    /** Null when the channel hides it, or YouTube did not report it. */
    subscribers?: number | null;
    video_count?: number | null;
    real_total_views?: number | null;
  };
  period?: { start?: string; end?: string };
  current_28_days?: ChannelMetrics;
  previous_28_days?: ChannelMetrics;
  recent_videos?: { sort?: string; rows?: ChannelVideo[] };
  video_learning?: VideoLearning;
  /** Parts YouTube refused or never answered during this sync: "uploads", "analytics". */
  partial_failures?: string[];
}

export interface ChannelStatus {
  configured?: boolean;
  connected?: boolean;
  channel?: { id?: string; title?: string; connected_at?: string } | null;
  latest_sync?: { synced_at?: string; data?: ChannelSyncData } | null;
  setup_message?: string | null;
}
