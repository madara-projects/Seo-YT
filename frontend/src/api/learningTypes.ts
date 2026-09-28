/**
 * View models for outcome learning: YouTube Studio tests prepared and recorded
 * here, traffic sources per completed window, and the retention-curve probe.
 * As elsewhere, a value the backend could not evidence is null, never zero.
 */

/** One title/thumbnail variant, read from the saved package on the server. */
export interface StudioVariant {
  label: string;
  package_id: string;
  title: string;
  thumbnail_text: string;
}

export interface StudioCandidate {
  package_id: string;
  title: string;
  thumbnail_text: string;
}

/** Two titles too alike to tell apart; named by package ID (overview) or variant label (test). */
export interface SimilarPair {
  first: string;
  second: string;
  similarity: number;
  message: string;
}

export type StudioOutcome = "winner" | "no_clear_winner";

export interface StudioTest {
  id: number;
  analysis_run_id: number;
  linked_video: { link_id: number; youtube_video_id: string } | null;
  variants: StudioVariant[];
  status: "prepared" | "linked" | "completed" | string;
  winner_variant: string | null;
  result: {
    outcome?: StudioOutcome;
    watch_time_share?: Record<string, number>;
    recorded_at?: string;
  } | null;
  notes: string;
  created_at?: string;
  updated_at?: string;
  similar_pairs: SimilarPair[];
}

/** `GET /api/history/runs/{id}/studio-tests`. */
export interface StudioTestOverview {
  analysis_run_id: number;
  eligible: boolean;
  video_format: "short" | "long_form";
  /** Why no test can be prepared (a Short), else null. */
  reason: string | null;
  min_variants: number;
  max_variants: number;
  candidates: StudioCandidate[];
  similar_pairs: SimilarPair[];
  linked_video: { link_id: number; youtube_video_id: string } | null;
  tests: StudioTest[];
  note: string;
}

export interface StudioTestUpdate {
  link_video?: boolean;
  outcome?: StudioOutcome;
  winner_variant?: string | null;
  watch_time_share?: Record<string, number>;
  notes?: string;
}

/** A completed window's views by YouTube Analytics traffic source (insightTrafficSourceType). */
export interface TrafficSourceRow {
  source: string;
  views: number;
  watch_time_minutes: number | null;
  share_percent: number | null;
}

export interface TrafficSources {
  sources: TrafficSourceRow[];
  total_views: number;
  dominant_source: string | null;
  dominant_share_percent: number | null;
  window?: string | null;
  source_start_date?: string | null;
  source_end_date?: string | null;
}

/** Comparable videos (one format and language) led by the same traffic source; medians only past the evidence minimum. */
export interface TrafficSourceCohort {
  format?: string;
  language?: string;
  traffic_source: string;
  snapshot_window: string;
  sample_size: number;
  minimum_samples: number;
  more_needed: number;
  learning_allowed: boolean;
  confidence_label?: string;
  median_views: number | null;
  median_retention_percentage: number | null;
  message?: string;
}

/** The two traffic-source fields the linked report adds. */
export interface LinkedTrafficEvidence {
  traffic_sources?: TrafficSources | null;
  traffic_source_cohort?: TrafficSourceCohort | null;
}

/** `GET /api/learning/cohorts`, the parts the traffic-source panel reads. */
export interface TrafficCohortResponse {
  snapshot_window?: string;
  sample_size?: number;
  minimum_samples?: number;
  traffic_source_groups?: TrafficSourceCohort[];
  without_traffic_sources?: number;
}

export type RetentionReason = "not_connected" | "not_channel_video" | "missing_scope" | "no_data_yet" | "api_error";

export interface RetentionPoint {
  elapsed_ratio: number;
  audience_watch_ratio: number;
  relative_retention_performance: number | null;
}

export interface RetentionObservations {
  hook: {
    end_ratio: number;
    still_watching_percent: number | null;
    relative_retention_performance: number | null;
  } | null;
  biggest_drop: {
    from_ratio: number;
    at_ratio: number;
    at_seconds: number | null;
    drop_points: number;
    in_hook: boolean;
    chapter: string | null;
  } | null;
  chapters: { title: string; start_seconds: number; end_seconds: number; viewers_lost_points: number }[];
  observations: string[];
  note: string;
}

/** `POST /api/published-videos/{id}/retention-probe`: one YouTube Analytics request at most. */
export interface RetentionProbeResult {
  status: "available" | "unavailable";
  reason: RetentionReason | null;
  message: string;
  requests: number;
  video_id?: string;
  start_date?: string;
  end_date?: string;
  points: RetentionPoint[];
  duration_seconds?: number | null;
  observations: RetentionObservations | null;
}
