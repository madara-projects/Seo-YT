/**
 * A comparison result produced by the real `compare_experiment` (offline): five
 * control and five variant videos with completed 24-hour windows.
 */
export const EXPERIMENT_RESULT_FIXTURE = {
  "id": 21,
  "captured_at": "2026-09-24T09:30:00+00:00",
  "rule_version": "phase8-experiment-v1",
  "state": "directional_variant",
  "mode": "controlled",
  "label": "PLANNED EXPERIMENT — DIRECTIONAL, NOT CAUSAL PROOF",
  "sample": {
    "assigned_control": 5,
    "assigned_variant": 5,
    "eligible_control": 5,
    "eligible_variant": 5,
    "mature_control": 5,
    "mature_variant": 5,
    "observational_references": 0,
    "minimum_per_group": 5,
    "missing_metrics": []
  },
  "metrics": [
    {
      "metric": "average_view_percentage",
      "control": {
        "sample_size": 5,
        "median": 60,
        "mean": 60
      },
      "variant": {
        "sample_size": 5,
        "median": 68,
        "mean": 68
      },
      "difference": 8,
      "relative_difference_percent": 13.33,
      "observed_direction": "variant",
      "provenance": "verified_completed_youtube_analytics_snapshot"
    },
    {
      "metric": "views",
      "control": {
        "sample_size": 5,
        "median": 980,
        "mean": 980
      },
      "variant": {
        "sample_size": 5,
        "median": 1060,
        "mean": 1060
      },
      "difference": 80,
      "relative_difference_percent": 8.16,
      "observed_direction": "variant",
      "provenance": "verified_completed_youtube_analytics_snapshot"
    }
  ],
  "evidence": {
    "evidence_level": "moderate_evidence",
    "confidence_label": "Moderate evidence",
    "learning_allowed": true,
    "next_threshold": 20,
    "observation_window": "24h",
    "status": "directional_evidence"
  },
  "interpretation": "The variant was associated with a higher observed primary metric in this sample.",
  "limitations": [
    "Assignment records intent but does not eliminate distribution, topic, audience, timing, or content confounders.",
    "No fake statistical significance or causal claim is calculated.",
    "Only verified completed snapshots in the selected window are eligible."
  ],
  "learning_candidate": {
    "variable": "title_mechanism",
    "observation": "directional_variant",
    "evidence_state": "directional",
    "sample_size": 10,
    "source_experiment": 3,
    "future_generation_allowed": true,
    "interpretation": "Associated with the observed result in this sample; not causal proof."
  },
  "next_recommendation": "Treat this as a candidate explanation and repeat the comparison before changing generation policy."
};
