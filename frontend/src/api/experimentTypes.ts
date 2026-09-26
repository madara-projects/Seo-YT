/**
 * Structured experiments (`/api/experiment-center/experiments`). Shapes follow
 * `AuditExperimentStore.experiment` and `compare_experiment`.
 */

export type ExperimentStatus = "draft" | "planned" | "active" | "paused" | "completed" | "cancelled" | "inconclusive";
export type ExperimentMode = "controlled" | "observational";
export type ExperimentRole = "control" | "variant" | "observational_reference";
export type ExperimentMetric = "views" | "average_view_percentage" | "likes" | "comments" | "engagement_rate";
export type ObservationWindow = "24h" | "7d" | "28d";

export interface ExperimentAssignment {
  id: number;
  published_video_link_id: number;
  role: ExperimentRole | string;
  assigned_at?: string | null;
  notes?: string | null;
  youtube_video_id?: string | null;
  published_at?: string | null;
  title?: string | null;
}

export interface MetricGroup {
  sample_size?: number;
  median?: number | null;
  mean?: number | null;
}

export interface ExperimentMetricResult {
  metric: ExperimentMetric | string;
  control?: MetricGroup;
  variant?: MetricGroup;
  difference?: number | null;
  relative_difference_percent?: number | null;
  observed_direction?: "variant" | "control" | "even" | string;
}

/** An assigned video left out of the comparison, and why. */
export interface MissingMetric {
  link_id?: number | null;
  role?: ExperimentRole | string;
  reason?: string;
}

export interface ExperimentResult {
  id?: number;
  captured_at?: string | null;
  /** Includes "inconclusive": an observational run under 5% apart, or a primary metric without values. */
  state?: string;
  mode?: string;
  /** The backend's one-line framing, e.g. "PLANNED EXPERIMENT — DIRECTIONAL, NOT CAUSAL PROOF". */
  label?: string;
  sample?: {
    assigned_control?: number;
    assigned_variant?: number;
    eligible_control?: number;
    eligible_variant?: number;
    observational_references?: number;
    minimum_per_group?: number;
    missing_metrics?: MissingMetric[];
  };
  metrics?: ExperimentMetricResult[];
  interpretation?: string;
  limitations?: string[];
  learning_candidate?: {
    variable?: string;
    evidence_state?: string;
    /** The primary metric's control count plus variant count. */
    sample_size?: number;
    interpretation?: string;
  } | null;
  next_recommendation?: string;
}

export interface Experiment {
  id: number;
  name: string;
  description?: string | null;
  hypothesis: string;
  mode: ExperimentMode | string;
  status: ExperimentStatus | string;
  variable: string;
  control_definition: string;
  variant_definition: string;
  success_metric: ExperimentMetric | string;
  secondary_metrics?: string[];
  target_sample_size?: number | null;
  minimum_sample_size?: number | null;
  observation_window: ObservationWindow | string;
  notes?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  assignments?: ExperimentAssignment[];
  latest_result?: ExperimentResult | null;
  assignment_counts?: { control?: number; variant?: number; observational_reference?: number };
}

export interface ExperimentListResponse {
  experiments?: Experiment[];
  total?: number;
}

export interface ExperimentDetailResponse {
  experiment?: Experiment;
  result_versions?: { id: number; captured_at?: string | null; result_state?: string | null }[];
}

export interface ExperimentResponse {
  status?: string;
  experiment?: Experiment;
  result?: ExperimentResult;
}

/** Body of `POST /api/experiment-center/experiments`; limits mirror the Pydantic model. */
export interface ExperimentCreatePayload {
  name: string;
  hypothesis: string;
  mode: ExperimentMode;
  variable: string;
  control_definition: string;
  variant_definition: string;
  success_metric: ExperimentMetric;
  observation_window: ObservationWindow;
}
