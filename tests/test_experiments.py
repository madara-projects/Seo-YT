"""Regression tests for experiment comparisons and audit learning candidates.

Confidence came from both groups added together, the primary metric was not
checked for its own values, observational runs always claimed a pattern,
missing engagement counts read as zero, and every audit candidate borrowed a
format/language cohort that never compared its variable.
"""

import unittest

from win_engine.analysis.audit_experiment import _metric_value, build_published_audit, compare_experiment

_COMPLETED = "2026-09-01T00:00:00+00:00"


def _assignment(role, *, retention=None, views=100, **counts):
    snapshot = {"snapshot_window": "24h", "snapshot_status": "complete", "completed_at": _COMPLETED,
                "views": views, "avg_view_percentage": retention, **counts}
    return {"role": role, "published_video_link_id": 1, "evidence_snapshot": snapshot}


def _experiment(**overrides):
    return {"id": 1, "mode": "controlled", "success_metric": "average_view_percentage", "secondary_metrics": [],
            "minimum_sample_size": 5, "observation_window": "24h", "variable": "title_mechanism", **overrides}


def _groups(control, variant, *, control_count=5, variant_count=5):
    return (
        [_assignment("control", retention=control + index) for index in range(control_count)]
        + [_assignment("variant", retention=variant + index) for index in range(variant_count)]
    )


class ExperimentEvidenceTests(unittest.TestCase):
    def test_one_empty_group_allows_no_learning(self):
        result = compare_experiment(_experiment(), _groups(60, 75, variant_count=0))
        self.assertEqual(result["state"], "insufficient_evidence")
        self.assertFalse(result["evidence"]["learning_allowed"])
        self.assertEqual(result["evidence"]["evidence_level"], "display_only")

    def test_primary_metric_needs_its_own_values_per_group(self):
        assignments = [_assignment("control") for _ in range(5)] + [_assignment("variant") for _ in range(5)]
        assignments[0]["evidence_snapshot"]["avg_view_percentage"] = 50
        assignments[5]["evidence_snapshot"]["avg_view_percentage"] = 80
        result = compare_experiment(_experiment(), assignments)
        self.assertEqual(result["state"], "insufficient_evidence")
        self.assertIsNone(result["learning_candidate"])
        self.assertEqual(result["sample"]["eligible_control"], 5)

    def test_confidence_follows_the_smaller_group(self):
        result = compare_experiment(_experiment(), _groups(60, 75, variant_count=10))
        self.assertEqual(result["state"], "directional_variant")
        self.assertEqual(result["evidence"]["evidence_level"], "early_signal")
        self.assertEqual(result["learning_candidate"]["sample_size"], 15)

    def test_minimum_above_the_floor_blocks_learning(self):
        result = compare_experiment(_experiment(minimum_sample_size=8), _groups(60, 75, control_count=6, variant_count=6))
        self.assertEqual(result["state"], "insufficient_evidence")
        self.assertFalse(result["evidence"]["learning_allowed"])
        self.assertEqual(result["sample"]["minimum_per_group"], 8)

    def test_secondary_metric_without_enough_values_does_not_make_results_mixed(self):
        assignments = _groups(60, 75)
        assignments[0]["evidence_snapshot"]["likes"] = 500
        assignments[5]["evidence_snapshot"]["likes"] = 5
        result = compare_experiment(_experiment(secondary_metrics=["likes"]), assignments)
        self.assertEqual(result["state"], "directional_variant")

    def test_observational_run_without_a_difference_claims_no_pattern(self):
        result = compare_experiment(_experiment(mode="observational"), _groups(60, 60))
        self.assertEqual(result["state"], "inconclusive")
        self.assertIsNone(result["learning_candidate"])

    def test_observational_run_with_a_difference_is_a_pattern(self):
        result = compare_experiment(_experiment(mode="observational"), _groups(60, 75))
        self.assertEqual(result["state"], "observational_pattern")
        self.assertEqual(result["learning_candidate"]["evidence_state"], "observed_association")


class EngagementRateTests(unittest.TestCase):
    def test_missing_components_make_the_rate_unavailable(self):
        self.assertIsNone(_metric_value({"views": 100}, "engagement_rate"))
        self.assertIsNone(_metric_value({"views": 100, "likes": 5, "comments": 1}, "engagement_rate"))
        self.assertEqual(_metric_value({"views": 100, "likes": 5, "comments": 1, "shares": 0}, "engagement_rate"), 6.0)


class AuditCandidateTests(unittest.TestCase):
    def context(self, cohort, snapshots=None):
        package = {"title": "Title", "description": "Description", "tags": [], "hashtags": [], "creator_brief": {"topic": "camera"}}
        selected = {"generated_package_id": "a", "package": {"title": "Title", "mechanism": "specific_curiosity", "surface": "browse"}}
        link = {"id": 1, "youtube_video_id": "video", "format": "youtube_shorts", "language": "english",
                "youtube_metadata": {"title": "Title", "description": "Description", "tags": []}, "metadata_synced_at": _COMPLETED}
        completed = [{"snapshot_window": "24h", "snapshot_status": "complete", "completed_at": _COMPLETED, "views": 100}]
        return {"run": {"id": 1, "query": "camera", "package": package, "selected_package": selected}, "link": link,
                "snapshots": completed if snapshots is None else snapshots, "linked_report": {}, "cohort": cohort,
                "comparable": {"format": "youtube_shorts", "language": "english"}}

    def test_only_format_and_language_are_backed_by_the_cohort(self):
        audit = build_published_audit(self.context({"sample_size": 5, "learning_allowed": True}))
        candidates = {item["variable"]: item for item in audit["learning_candidates"]}
        self.assertEqual(audit["summary"]["state"], "actionable_observation")
        for variable in ("format", "language"):
            self.assertEqual((candidates[variable]["evidence_state"], candidates[variable]["sample_size"]), ("mature_comparable_evidence", 5))
        for variable in ("topic", "title_mechanism", "discovery_surface"):
            self.assertEqual((candidates[variable]["evidence_state"], candidates[variable]["sample_size"]), ("hypothesis_only", 0))
            self.assertIn("causal proof", candidates[variable]["interpretation"])

    def test_small_peer_cohort_is_not_actionable(self):
        audit = build_published_audit(self.context({"sample_size": 4, "learning_allowed": False}))
        self.assertEqual(audit["summary"]["state"], "mature_observation")
        self.assertEqual({item["evidence_state"] for item in audit["learning_candidates"]}, {"hypothesis_only"})

    def test_no_completed_window_leaves_every_candidate_insufficient(self):
        audit = build_published_audit(self.context({"sample_size": 5, "learning_allowed": True}, snapshots=[]))
        self.assertEqual({item["evidence_state"] for item in audit["learning_candidates"]}, {"insufficient_evidence"})


if __name__ == "__main__":
    unittest.main()
