/**
 * A published-video audit produced by the real `build_published_audit`
 * (offline, from a representative context): two completed windows, a changed
 * description and hashtags, and no recorded package selection.
 */
export const AUDIT_FIXTURE = {
  "id": 9,
  "captured_at": "2026-09-24T09:00:01+00:00",
  "rule_version": "phase8-audit-v1",
  "summary": {
    "state": "mature_observation",
    "message": "Historical intent, actual published metadata, and available observations are separated. No finding establishes causality."
  },
  "video": {
    "link_id": 5,
    "analysis_run_id": 42,
    "youtube_video_id": "z4HKMfQ3nJc",
    "published_at": "2026-09-07T11:50:35Z",
    "format": "youtube_shorts",
    "language": "english",
    "duration": "PT21S",
    "ownership_state": "verified",
    "provenance": "verified_owned_video_link",
    "field_provenance": {
      "format": "package",
      "language": "package",
      "duration": "youtube_owned_metadata"
    }
  },
  "intent": {
    "original_query": "why silence hurts more than words",
    "generated_package": {
      "title": "Silence says everything 💔 #shorts",
      "description": "Some silences are louder than words.\n\n#shorts #tamilquotes #silence",
      "tags": [
        "silence quotes",
        "tamil quotes",
        "heartbreak",
        "shorts"
      ],
      "hashtags": [
        "#shorts",
        "#tamilquotes",
        "#silence"
      ]
    },
    "selected_package": null,
    "selection_attribution": "unknown",
    "selected_package_id": null
  },
  "published_reality": {
    "title": "Silence says everything 💔 #shorts",
    "description": "Some silences are louder than words.\n\n#shorts #tamilquotes #silence #mounam",
    "tags": [
      "silence quotes",
      "tamil quotes",
      "heartbreak",
      "shorts"
    ],
    "hashtags": [
      "#shorts",
      "#tamilquotes",
      "#silence",
      "#mounam"
    ],
    "available": true,
    "captured_at": "2026-09-24T09:00:00+00:00",
    "provenance": "youtube_owned_metadata"
  },
  "comparisons": [
    {
      "field": "title",
      "generated": "Silence says everything 💔 #shorts",
      "selected": null,
      "published": "Silence says everything 💔 #shorts",
      "provenance": {
        "generated": "saved_analysis_payload",
        "selected": "unavailable",
        "published": "youtube_owned_metadata"
      },
      "generated_to_selected": "unavailable",
      "selected_to_published": "unavailable",
      "generated_to_published": "exact_match"
    },
    {
      "field": "description",
      "generated": "Some silences are louder than words.\n\n#shorts #tamilquotes #silence",
      "selected": null,
      "published": "Some silences are louder than words.\n\n#shorts #tamilquotes #silence #mounam",
      "provenance": {
        "generated": "saved_analysis_payload",
        "selected": "unavailable",
        "published": "youtube_owned_metadata"
      },
      "generated_to_selected": "unavailable",
      "selected_to_published": "unavailable",
      "generated_to_published": "changed"
    },
    {
      "field": "tags",
      "generated": [
        "silence quotes",
        "tamil quotes",
        "heartbreak",
        "shorts"
      ],
      "selected": null,
      "published": [
        "silence quotes",
        "tamil quotes",
        "heartbreak",
        "shorts"
      ],
      "provenance": {
        "generated": "saved_analysis_payload",
        "selected": "unavailable",
        "published": "youtube_owned_metadata"
      },
      "generated_to_selected": "unavailable",
      "selected_to_published": "unavailable",
      "generated_to_published": "exact_match"
    },
    {
      "field": "hashtags",
      "generated": [
        "#shorts",
        "#tamilquotes",
        "#silence"
      ],
      "selected": null,
      "published": [
        "#shorts",
        "#tamilquotes",
        "#silence",
        "#mounam"
      ],
      "provenance": {
        "generated": "saved_analysis_payload",
        "selected": "unavailable",
        "published": "youtube_owned_metadata"
      },
      "generated_to_selected": "unavailable",
      "selected_to_published": "unavailable",
      "generated_to_published": "changed"
    }
  ],
  "before_publication": {
    "generation_quality": {
      "status": "pass"
    },
    "retention_assistant": {
      "risk_level": "medium",
      "status": "available"
    },
    "selected_package_trace": null,
    "idea": {
      "id": 7,
      "topic": "Why silence hurts more than words"
    },
    "idea_research": null,
    "demand_research": {
      "id": 12,
      "classification": "active_topic",
      "captured_at": "2026-09-06T10:00:00+00:00",
      "evidence": {}
    },
    "watchlist_context": null,
    "personal_evidence": {
      "status": "unavailable"
    },
    "provenance": "saved_historical_payloads_only"
  },
  "observed_performance": {
    "current": {
      "snapshot_window": "current",
      "views": 3105,
      "likes": 214,
      "comments": 15,
      "shares": 7,
      "avg_view_percentage": 63.2,
      "captured_at": "2026-09-24T09:00:00+00:00",
      "snapshot_status": "complete"
    },
    "completed_windows": [
      {
        "snapshot_window": "24h",
        "views": 812,
        "likes": 64,
        "comments": 5,
        "shares": 2,
        "avg_view_percentage": 71.4,
        "captured_at": "2026-09-08T12:00:00+00:00",
        "snapshot_status": "complete",
        "completed_at": "2026-09-08T12:00:00+00:00"
      },
      {
        "snapshot_window": "7d",
        "views": 2410,
        "likes": 171,
        "comments": 12,
        "shares": 6,
        "avg_view_percentage": 64.9,
        "captured_at": "2026-09-14T12:00:00+00:00",
        "snapshot_status": "complete",
        "completed_at": "2026-09-14T12:00:00+00:00"
      }
    ],
    "latest_observation": {
      "snapshot_window": "current",
      "views": 3105,
      "likes": 214,
      "comments": 15,
      "shares": 7,
      "avg_view_percentage": 63.2,
      "captured_at": "2026-09-24T09:00:00+00:00",
      "snapshot_status": "complete"
    },
    "linked_report_performance": null,
    "maturity": "mature_observation",
    "causality": "not_established"
  },
  "findings": [
    {
      "code": "selection_unknown",
      "severity": "review",
      "category": "attribution",
      "explanation": "No explicit generated-package selection was recorded.",
      "evidence": "analysis_package_selections: unavailable",
      "evidence_state": "unknown",
      "recommended_interpretation": "Do not infer that the primary generated package was published."
    },
    {
      "code": "generated_vs_published_only",
      "severity": "info",
      "category": "metadata",
      "explanation": "Generated and published metadata can be compared, but selected-package attribution is unknown.",
      "evidence": "saved generation + owned YouTube metadata",
      "evidence_state": "observed",
      "recommended_interpretation": "A difference is observable but the creator's intended package cannot be inferred."
    },
    {
      "code": "published_metadata_changed",
      "severity": "review",
      "category": "metadata",
      "explanation": "Published metadata differed from the primary generated package: description, hashtags.",
      "evidence": "saved generation + owned YouTube metadata",
      "evidence_state": "observed",
      "recommended_interpretation": "Use the actual published values for post-publication learning."
    },
    {
      "code": "opening_risk_recorded",
      "severity": "review",
      "category": "pre_publish",
      "explanation": "The saved retention assistant recorded medium structural risk.",
      "evidence": "historical retention_assistant payload",
      "evidence_state": "heuristic",
      "recommended_interpretation": "This was pre-publish guidance, not measured retention."
    },
    {
      "code": "generation_quality_trace",
      "severity": "info",
      "category": "pre_publish",
      "explanation": "The saved generation-quality state was pass.",
      "evidence": "historical generation_quality payload",
      "evidence_state": "heuristic",
      "recommended_interpretation": "Quality checks describe package consistency, not expected reach."
    },
    {
      "code": "mature_observation_available",
      "severity": "info",
      "category": "performance",
      "explanation": "2 completed observation window(s) are available.",
      "evidence": "verified completed YouTube Analytics snapshots",
      "evidence_state": "mature_observation",
      "recommended_interpretation": "The observations support comparison, not causality."
    }
  ],
  "learning_candidates": [
    {
      "variable": "format",
      "value": "youtube_shorts",
      "evidence_state": "hypothesis_only",
      "sample_size": 2,
      "interpretation": "Observed association candidate; never causal proof.",
      "provenance": "saved_package_and_shared_evidence_policy"
    },
    {
      "variable": "language",
      "value": "english",
      "evidence_state": "hypothesis_only",
      "sample_size": 2,
      "interpretation": "Observed association candidate; never causal proof.",
      "provenance": "saved_package_and_shared_evidence_policy"
    },
    {
      "variable": "topic",
      "value": "why silence hurts more than words",
      "evidence_state": "hypothesis_only",
      "sample_size": 2,
      "interpretation": "Observed association candidate; never causal proof.",
      "provenance": "saved_package_and_shared_evidence_policy"
    }
  ],
  "evidence": {
    "snapshot_count": 3,
    "mature_window_count": 2,
    "cohort": {
      "sample_size": 2,
      "learning_allowed": false,
      "confidence_label": "Collecting evidence"
    },
    "retention_learning": null,
    "provenance": [
      "saved_analysis_payload",
      "creator_selection_or_unknown",
      "youtube_owned_metadata",
      "youtube_performance_snapshots",
      "shared_evidence_policy"
    ]
  },
  "limitations": [
    "YouTube video-level metrics do not isolate the effect of title, tags, thumbnail, hook, or timing.",
    "Unavailable fields remain unavailable; retention curves and competitor private analytics are not inferred.",
    "A mature observation can support comparison but does not prove causation."
  ]
};
