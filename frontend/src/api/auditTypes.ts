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

/** The newest snapshot as the audit list carries it: a subset of `PerformanceSnapshot`. */
export interface CandidatePerformance {
  views?: number | null;
  avg_view_percentage?: number | null;
  impressions_ctr?: number | null;
  snapshot_window?: string | null;
  captured_at?: string | null;
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
  latest_performance?: CandidatePerformance | null;
  ownership_verified?: boolean;
  verified_channel_id?: string | null;
  audit_id?: number | null;
  audit_captured_at?: string | null;
  audit_state: AuditState | string;
  /** "mature" once any 24h/7d/28d window completed; "observed" when only counts exist. */
  evidence_state: AuditEvidenceState | string;
  /** Whether the creator recorded a package choice before linking. */
  selection_state?: "selected" | "unknown" | string;
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

/**
 * Something the audit suggests testing next. Only format and language are
 * compared across your videos; the rest are hypotheses with a sample of 0.
 */
export interface LearningCandidate {
  variable?: string;
  value?: unknown;
  evidence_state?: "mature_comparable_evidence" | "hypothesis_only" | "insufficient_evidence" | string;
  sample_size?: number;
  interpretation?: string;
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
    /** The idea's last research before publishing; null when none, or the publish time was unreadable. */
    idea_research?: {
      id?: number;
      captured_at?: string | null;
      evidence?: { opportunity_explanation?: string | null } | null;
    } | null;
    demand_research?: { id?: number; classification?: string | null; captured_at?: string | null } | null;
  };
  observed_performance?: {
    current?: PerformanceSnapshot | null;
    completed_windows?: PerformanceSnapshot[];
    latest_observation?: PerformanceSnapshot | null;
    maturity?: "mature_observation" | "collecting_evidence" | "unavailable" | string;
  };
  findings?: AuditFinding[];
  learning_candidates?: LearningCandidate[];
  evidence?: {
    snapshot_count?: number;
    mature_window_count?: number;
    /** Peers only: the audited video is not counted toward its own comparison. */
    cohort?: { sample_size?: number; learning_allowed?: boolean; confidence_label?: string } | null;
  };
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
