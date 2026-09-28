/** A stored Opportunity Score breakdown and calibration results, as the backend returns them. */

export const BREAKDOWN = {
  version: "opportunity-heuristic-v1",
  kind: "local_heuristic",
  statement:
    "A local heuristic that weighs five signals from this idea's YouTube research. It is not a prediction of views, reach or click-through rate.",
  score: 48.34,
  inputs: [
    { key: "demand_velocity", name: "Demand (view velocity)", value: 75.01, weight: 0.35, contribution: 26.2535, source: "youtube_measured", basis: "Average of 25 × log10(1 + views per day) for 1 of the top 2 research video(s)." },
    { key: "competition_room", name: "Competition room", value: 75, weight: 0.25, contribution: 18.75, source: "local_heuristic", basis: "100 minus the competition heuristic." },
    { key: "keyword_gap", name: "Keyword gaps", value: 0, weight: 0.2, contribution: 0, source: "missing_default", basis: "No keywords were extracted from your script, so this counted as 0." },
    { key: "small_channel_breakout", name: "Small-channel breakouts", value: 0, weight: 0.1, contribution: 0, source: "youtube_measured", basis: "0 of the top 2 research video(s) came from small channels." },
    { key: "research_relevance", name: "Research relevance", value: 33.33, weight: 0.1, contribution: 3.3333, source: "local_heuristic", basis: "How many research queries found each top video." },
  ],
  warnings: [
    "Only 2 top research video(s) were available; the score uses up to 3.",
    "No keywords were extracted from your script, so keyword gaps counted as 0.",
  ],
  confidence: "medium",
  confidence_reason:
    "4 of 5 inputs had data, backed by 2 top research video(s) from 12 sampled result(s). Confidence describes how complete the inputs were, not how likely the video is to get views.",
  inputs_with_data: 4,
  top_videos_used: 2,
  research_results: 12,
};

const CAVEATS = [
  "This is an association in your own past videos, not causation: topics, timing and packaging also differ between videos.",
  "The Opportunity Score is a local heuristic, not a prediction of views.",
  "Only packages in the same format and language, measured at the same completed window, are compared.",
];

export const INSUFFICIENT_CALIBRATION = {
  status: "insufficient_evidence",
  verdict_label: "Not enough comparable videos yet",
  interpretation: "association_not_causation",
  snapshot_window: "24h",
  outcome: "views_at_completed_window",
  outcome_label: "Views at the completed 24h window",
  sample_size: 3,
  compared_sample_size: 0,
  minimum_group_samples: 5,
  evidence_level: "display_only",
  confidence_label: "Collecting evidence",
  spearman_rho: null,
  association_threshold: null,
  groups: [
    {
      format: "youtube_shorts", language: "english", sample_size: 3, enough_samples: false, median_score: 55,
      higher_scoring: { sample_size: 1, median_views: 900 }, lower_scoring: { sample_size: 1, median_views: 200 },
      spearman_rho: null, direction: null,
    },
  ],
  recommendation: null,
  recommendation_text: null,
  summary:
    "There are not yet enough comparable published videos to tell whether higher Opportunity Scores went with more views, so no association is claimed.",
  needed:
    "Needs at least 5 published videos with different scores in one format and language group, each linked to its saved package, ownership-verified, and with a completed 24h snapshot. The largest group has 3.",
  caveats: CAVEATS,
  windows: { "24h": 3, "7d": 0, "28d": 0 },
  excluded: { not_ownership_verified: 1, missing_format_or_language: 0, score_not_measured: 0, no_completed_snapshot: 2 },
  links_considered: 6,
  breakdown_stored_count: 0,
};

export const POSITIVE_CALIBRATION = {
  ...INSUFFICIENT_CALIBRATION,
  status: "higher_scores_did_better",
  verdict_label: "Higher scores did better",
  snapshot_window: "7d",
  outcome_label: "Views at the completed 7d window",
  sample_size: 10,
  compared_sample_size: 10,
  evidence_level: "moderate_evidence",
  confidence_label: "Moderate evidence",
  spearman_rho: 0.82,
  association_threshold: 0.653,
  groups: [
    {
      format: "youtube_shorts", language: "english", sample_size: 10, enough_samples: true, median_score: 52.5,
      higher_scoring: { sample_size: 5, median_views: 610 }, lower_scoring: { sample_size: 5, median_views: 180 },
      spearman_rho: 0.82, direction: "higher",
    },
  ],
  recommendation: "keep",
  recommendation_text: "Keep the score as a rough guide, and keep checking it as more videos mature.",
  summary:
    "In 10 comparable video(s) measured at the completed 7d window, higher-scoring packages went with more views (rank correlation +0.82). This is an association, not causation.",
  needed: null,
  windows: { "24h": 10, "7d": 10, "28d": 0 },
};

export const NO_RELATIONSHIP_CALIBRATION = {
  ...POSITIVE_CALIBRATION,
  status: "no_clear_relationship",
  verdict_label: "No clear relationship",
  spearman_rho: -0.15,
  recommendation: "recalibrate",
  recommendation_text:
    "Recalibrate the score: its weights did not separate your better and worse results. Treat it as a checklist of inputs rather than a ranking until it is reweighted.",
  summary:
    "In 10 comparable video(s) measured at the completed 7d window, the score did not consistently separate videos with more and fewer views (rank correlation -0.15). This is an association, not causation.",
};

export const NEGATIVE_CALIBRATION = {
  ...POSITIVE_CALIBRATION,
  status: "lower_scores_did_better",
  verdict_label: "Lower scores did better",
  spearman_rho: -0.9,
  recommendation: "retire",
  recommendation_text: "Retire the score as a ranking: in your own results it did not point to the videos that did better.",
  summary:
    "In 10 comparable video(s) measured at the completed 7d window, lower-scoring packages went with more views (rank correlation -0.90). This is an association, not causation.",
};
