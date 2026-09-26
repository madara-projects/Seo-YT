/**
 * View models for the Demand explorer.
 *
 * Mirrors `analyze_demand` in `win_engine/analysis/demand_explorer.py`. A
 * snapshot is saved once and never changed, so every field is read-only
 * evidence; all are optional because older snapshots may predate a field.
 */

export type DemandClassification =
  | "strong_observed_interest"
  | "active_topic"
  | "emerging_signal"
  | "insufficient_evidence";

export interface DemandSignal {
  name?: string;
  observed?: number | null;
  source?: "public_observation" | "heuristic" | "unavailable" | string;
  limitation?: string;
}

/**
 * A public YouTube video as research snapshots store it, with the counts it
 * had at capture. Idea research and demand research both save this shape.
 */
export interface PublicVideoResult {
  video_id?: string | null;
  title?: string | null;
  channel_title?: string | null;
  published_at?: string | null;
  // YouTube returns counts as strings; they are stored as received.
  view_count?: number | string | null;
}

export interface DemandPublicResult extends PublicVideoResult {
  like_count?: number | string | null;
  comment_count?: number | string | null;
}

export interface DemandWatchlistMatch {
  watchlist_video_id?: number;
  video_id?: string;
  title?: string;
  outlier_status?: string;
  relative_multiplier?: number | null;
  captured_at?: string | null;
}

export interface DemandPersonalEvidence {
  status?: string;
  learning_allowed?: boolean;
  sample_size?: number;
  confidence_label?: string;
  source?: string;
}

export interface DemandEvidence {
  classification?: string;
  reasons?: string[];
  captured_at?: string;
  signals?: DemandSignal[];
  public_results?: DemandPublicResult[];
  watchlist_evidence?: DemandWatchlistMatch[];
  personal_evidence?: DemandPersonalEvidence;
  limitations?: string[];
}

export interface DemandSnapshot {
  id: number;
  idea_id?: number | null;
  topic?: string;
  language?: string | null;
  format?: string | null;
  region?: string | null;
  audience_context?: string | null;
  classification?: DemandClassification | string;
  evidence?: DemandEvidence;
  captured_at?: string;
}

export interface DemandListResponse {
  research?: DemandSnapshot[];
  total?: number;
  limit?: number;
  offset?: number;
}

export interface DemandResearchResponse {
  status?: string;
  research?: DemandSnapshot;
}

export interface DemandGenerateResponse {
  status?: string;
  analysis?: { history_run_id?: number; title?: string };
  demand_research_id?: number;
  /** Present when the snapshot belongs to an idea, which now carries the package. */
  idea?: { id: number; status?: string } | null;
}
