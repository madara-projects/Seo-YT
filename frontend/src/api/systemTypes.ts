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
}

export interface CloudSyncRunResult {
  state?: string;
  counts?: CloudSyncCounts;
}

export interface SettingsStatus {
  app?: { name?: string; version?: string; environment?: string };
  database?: {
    healthy?: boolean;
    name?: string;
    schema_version?: number;
    size_bytes?: number | null;
    counts?: {
      packages?: number;
      ideas?: number;
      published_links?: number;
      performance_snapshots?: number;
    };
    last_backup_at?: string | null;
  };
  providers?: {
    gemini?: GeminiDiagnostics;
    youtube_data_api?: { configured?: boolean; key_count?: number };
    local_fallback?: { available?: boolean };
    redis?: { configured?: boolean };
  };
  youtube_oauth?: {
    configured?: boolean;
    connected?: boolean;
    channel_title?: string | null;
    last_synced_at?: string | null;
  };
  collector?: CollectorStatus;
  cloud_sync?: CloudSyncStatus;
}

/** `GET /diagnostics` — runs one live YouTube search, so it is on demand only. */
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
  views?: number;
  likes?: number;
  comments?: number;
  averageViewPercentage?: number | null;
}

export interface LearningVideo {
  video_id?: string;
  title?: string;
  published_at?: string;
  views?: number;
  views_per_day?: number;
  average_view_percentage?: number | null;
  likes?: number;
  comments?: number;
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
  best_videos?: LearningVideo[];
  recommendation?: string;
}

export interface ChannelSyncData {
  channel?: {
    id?: string;
    title?: string;
    subscribers?: number;
    video_count?: number;
    real_total_views?: number;
  };
  period?: { start?: string; end?: string };
  current_28_days?: ChannelMetrics;
  previous_28_days?: ChannelMetrics;
  recent_videos?: { sort?: string; rows?: ChannelVideo[] };
  video_learning?: VideoLearning;
}

export interface ChannelStatus {
  configured?: boolean;
  connected?: boolean;
  channel?: { id?: string; title?: string; connected_at?: string } | null;
  latest_sync?: { synced_at?: string; data?: ChannelSyncData } | null;
  setup_message?: string | null;
}
