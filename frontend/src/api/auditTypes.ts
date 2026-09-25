/**
 * Published-video audits (`/api/audits`). Shapes follow
 * `AuditExperimentStore.audit_candidates` and `build_published_audit`.
 */

export type AuditState =
  | "not_run"
  | "not_enough_data"
  | "collecting_evidence"
  | "observable"
  | "mature_observation"
  | "actionable_observation"
  | "inconclusive";

export type AuditEvidenceState = "unavailable" | "observed" | "mature";

/** How two versions of one metadata field compare. */
export type FieldState = "exact_match" | "changed" | "missing" | "unknown" | "unavailable";

export interface PerformanceSnapshot {
  snapshot_window?: string | null;
  views?: number | null;
  likes?: number | null;
  comments?: number | null;
  shares?: number | null;
  avg_view_percentage?: number | null;
  watch_time_minutes?: number | null;
  impressions_ctr?: number | null;
  captured_at?: string | null;
  snapshot_status?: string | null;
}

/** One row of `GET /api/audits`: a package linked to a published video. */
export interface AuditCandidate {
  id: number;
  analysis_run_id: number;
  youtube_video_id: string;
  published_at?: string | null;
  selected_title?: string | null;
  package_topic?: string | null;
  youtube_metadata?: { title?: string | null } | null;
  metadata_synced_at?: string | null;
  latest_performance?: PerformanceSnapshot | null;
  ownership_verified?: boolean;
  verified_channel_id?: string | null;
  audit_id?: number | null;
  audit_captured_at?: string | null;
  audit_state: AuditState | string;
  evidence_state: AuditEvidenceState | string;
  idea?: { id: number; topic?: string | null } | null;
}

export interface AuditComparison {
  field: string;
  generated?: string | string[] | null;
  selected?: string | string[] | null;
  published?: string | string[] | null;
  generated_to_selected?: FieldState | string;
  selected_to_published?: FieldState | string;
  generated_to_published?: FieldState | string;
}

export interface AuditFinding {
  code: string;
  severity?: "review" | "info" | string;
  category?: string;
  explanation?: string;
  evidence?: string;
  evidence_state?: string;
  recommended_interpretation?: string;
}

export interface Audit {
  id: number;
  captured_at?: string | null;
  rule_version?: string;
  summary?: { state?: AuditState | string; message?: string };
  video?: {
    link_id?: number;
    analysis_run_id?: number;
    youtube_video_id?: string;
    published_at?: string | null;
    duration?: string | null;
  };
  intent?: {
    generated_package?: { title?: string | null };
    selection_attribution?: "creator_selected" | "unknown" | string;
  };
  published_reality?: { title?: string | null; available?: boolean; captured_at?: string | null };
  comparisons?: AuditComparison[];
  before_publication?: {
    generation_quality?: { status?: string | null } | null;
    retention_assistant?: { status?: string | null; risk_level?: string | null } | null;
    idea?: { id?: number; topic?: string | null } | null;
    demand_research?: { id?: number; classification?: string | null; captured_at?: string | null } | null;
  };
  observed_performance?: {
    current?: PerformanceSnapshot | null;
    completed_windows?: PerformanceSnapshot[];
    latest_observation?: PerformanceSnapshot | null;
    maturity?: "mature_observation" | "collecting_evidence" | "unavailable" | string;
  };
  findings?: AuditFinding[];
  evidence?: { snapshot_count?: number; mature_window_count?: number };
  limitations?: string[];
}

export interface AuditVersion {
  id: number;
  captured_at?: string | null;
  summary_state?: string | null;
}

export interface AuditListResponse {
  candidates?: AuditCandidate[];
  total?: number;
}

export interface AuditDetailResponse {
  audit?: Audit | null;
  versions?: AuditVersion[];
  status?: "available" | "not_run" | string;
}

export interface AuditRefreshResponse extends AuditDetailResponse {
  video_refresh?: { captured?: { snapshot_window?: string }[]; message?: string };
}
