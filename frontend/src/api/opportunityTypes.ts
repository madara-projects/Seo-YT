/**
 * The Opportunity Score's breakdown (`opportunity_gap_analysis.opportunity_score.breakdown`)
 * and its calibration against published results (`GET /api/opportunity-score/calibration`).
 *
 * The score is a local heuristic, never a prediction of views, and the
 * calibration is an association in the creator's own videos, never a cause.
 */

/** Where an input came from: YouTube's own counts, a local rule, or a stand-in because data was missing. */
export type OpportunityInputSource = "youtube_measured" | "local_heuristic" | "missing_default";

export interface OpportunityInput {
  key: string;
  name: string;
  /** 0–100, as the score used it. */
  value: number;
  /** A fraction of 1; the five weights add to 1. */
  weight: number;
  /** value × weight: the points this input added to the score. */
  contribution: number;
  source: OpportunityInputSource | string;
  basis: string;
}

export type OpportunityConfidence = "high" | "medium" | "low" | "none";

export interface OpportunityBreakdown {
  version?: string;
  statement: string;
  /** Null when the score could not be calculated (UNMEASURED). */
  score: number | null;
  inputs: OpportunityInput[];
  warnings: string[];
  /** How complete the inputs were, not how likely the video is to get views. */
  confidence: OpportunityConfidence | string;
  confidence_reason?: string;
  inputs_with_data?: number;
  top_videos_used?: number;
  research_results?: number | null;
}

export type CalibrationStatus =
  | "insufficient_evidence"
  | "no_clear_relationship"
  | "higher_scores_did_better"
  | "lower_scores_did_better";

export interface CalibrationHalf {
  sample_size?: number;
  median_views?: number | null;
}

export interface CalibrationGroup {
  format?: string;
  language?: string;
  sample_size?: number;
  enough_samples?: boolean;
  median_score?: number | null;
  higher_scoring?: CalibrationHalf;
  lower_scoring?: CalibrationHalf;
  spearman_rho?: number | null;
  direction?: "higher" | "lower" | "tie" | null;
}

export interface ScoreCalibration {
  status?: CalibrationStatus | string;
  verdict_label?: string;
  interpretation?: string;
  snapshot_window?: string;
  outcome_label?: string;
  sample_size?: number;
  compared_sample_size?: number;
  minimum_group_samples?: number;
  evidence_level?: string;
  confidence_label?: string;
  spearman_rho?: number | null;
  association_threshold?: number | null;
  groups?: CalibrationGroup[];
  recommendation?: "keep" | "recalibrate" | "retire" | null;
  recommendation_text?: string | null;
  summary?: string;
  needed?: string | null;
  caveats?: string[];
  windows?: Record<string, number>;
  excluded?: Record<string, number>;
  links_considered?: number;
  breakdown_stored_count?: number;
}
