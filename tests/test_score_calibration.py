"""Does the Opportunity Score track the creator's own published results?

Packages are compared only with comparable ones (same format and language),
only on verified videos with a completed snapshot at the same window, and the
answer is an association, never a cause or a prediction.
"""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from win_engine.api import routes
from win_engine.api.app import create_app
from win_engine.core.config import Settings
from win_engine.feedback.evidence_policy import EARLY_SIGNAL_MIN_SAMPLES
from win_engine.feedback.history_store import HistoryStore
from win_engine.feedback.score_calibration import (
    calibrate_opportunity_score,
    opportunity_score_calibration,
    spearman_rho,
)


def _samples(pairs, fmt="youtube_shorts", language="english", start=0):
    return [
        {"analysis_run_id": start + index + 1, "youtube_video_id": f"video{start + index:06d}",
         "opportunity_score": float(score), "views": float(views), "format": fmt, "language": language}
        for index, (score, views) in enumerate(pairs)
    ]


def _scores(count):
    return [30 + 5 * index for index in range(count)]


RISING = list(zip(_scores(10), [100, 150, 180, 260, 300, 420, 500, 610, 700, 900]))
FALLING = list(zip(_scores(10), [900, 700, 610, 500, 420, 300, 260, 180, 150, 100]))
# Alternating high and low outcomes: a Spearman correlation of about -0.15.
UNRELATED = list(zip(_scores(10), [1000, 100, 900, 200, 800, 300, 700, 400, 600, 500]))


class SpearmanTests(unittest.TestCase):
    def test_perfect_orders(self):
        self.assertEqual(spearman_rho([1, 2, 3, 4, 5], [10, 20, 30, 40, 50]), 1.0)
        self.assertEqual(spearman_rho([1, 2, 3, 4, 5], [50, 40, 30, 20, 10]), -1.0)

    def test_ties_use_average_ranks(self):
        self.assertAlmostEqual(spearman_rho([1, 1, 2, 3], [5, 6, 7, 8]), 0.9487, places=4)

    def test_no_variation_has_no_correlation(self):
        self.assertIsNone(spearman_rho([50, 50, 50], [1, 2, 3]))
        self.assertIsNone(spearman_rho([1, 2], [3, 4]))


class VerdictTests(unittest.TestCase):
    def assert_honest(self, result):
        self.assertEqual(result["interpretation"], "association_not_causation")
        text = " ".join([result["summary"], *result["caveats"]]).lower()
        self.assertIn("association", text)
        self.assertIn("not a prediction of views", text)
        for claim in ("predicts views", "will get", "caused by the score", "guarantee"):
            self.assertNotIn(claim, text)

    def test_three_completed_snapshots_are_insufficient(self):
        result = calibrate_opportunity_score(_samples([(70, 900), (40, 200), (55, 400)]), snapshot_window="7d")
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertIsNone(result["recommendation"])
        self.assertIsNone(result["spearman_rho"])
        self.assertEqual(result["sample_size"], 3)
        self.assertEqual(result["minimum_group_samples"], EARLY_SIGNAL_MIN_SAMPLES)
        self.assertEqual(result["groups"][0]["sample_size"], 3)
        self.assertIn(f"at least {EARLY_SIGNAL_MIN_SAMPLES}", result["needed"])
        self.assertIn("largest group has 3", result["needed"])
        self.assert_honest(result)

    def test_small_groups_are_never_pooled_across_formats(self):
        samples = _samples(RISING[:3]) + _samples(RISING[3:6], fmt="long_form", start=3)
        result = calibrate_opportunity_score(samples, snapshot_window="24h")
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertEqual(sorted(group["format"] for group in result["groups"]), ["long_form", "youtube_shorts"])

    def test_higher_scores_did_better(self):
        result = calibrate_opportunity_score(_samples(RISING), snapshot_window="7d")
        self.assertEqual(result["status"], "higher_scores_did_better")
        self.assertEqual(result["spearman_rho"], 1.0)
        group = result["groups"][0]
        self.assertEqual(group["higher_scoring"]["sample_size"], 5)
        self.assertEqual(group["lower_scoring"]["sample_size"], 5)
        self.assertGreater(group["higher_scoring"]["median_views"], group["lower_scoring"]["median_views"])
        self.assertEqual(result["recommendation"], "keep")
        self.assertEqual(result["evidence_level"], "moderate_evidence")
        self.assert_honest(result)

    def test_no_clear_relationship(self):
        result = calibrate_opportunity_score(_samples(UNRELATED), snapshot_window="7d")
        self.assertEqual(result["status"], "no_clear_relationship")
        self.assertLess(abs(result["spearman_rho"]), result["association_threshold"])
        self.assertEqual(result["recommendation"], "recalibrate")
        self.assert_honest(result)

    def test_lower_scores_did_better(self):
        result = calibrate_opportunity_score(_samples(FALLING), snapshot_window="7d")
        self.assertEqual(result["status"], "lower_scores_did_better")
        self.assertEqual(result["spearman_rho"], -1.0)
        self.assertEqual(result["recommendation"], "retire")
        self.assert_honest(result)

    def test_an_early_signal_makes_no_recommendation(self):
        result = calibrate_opportunity_score(_samples(RISING[:5]), snapshot_window="7d")
        self.assertEqual(result["status"], "higher_scores_did_better")
        self.assertEqual(result["evidence_level"], "early_signal")
        self.assertIsNone(result["recommendation"])

    def test_an_inconclusive_result_is_recalibrated_not_retired(self):
        # Rank correlation about -0.08 in 20 videos: too few to rule out a useful association.
        views = [value for pair in zip(range(20, 10, -1), range(1, 11)) for value in pair]
        result = calibrate_opportunity_score(_samples(list(zip(_scores(20), views))), snapshot_window="28d")
        self.assertEqual(result["status"], "no_clear_relationship")
        self.assertEqual(result["evidence_level"], "strong_evidence")
        self.assertEqual(result["recommendation"], "recalibrate")

    def test_a_score_the_results_rule_out_is_retired(self):
        # About -0.37 in 20 videos: even its margin of error stays below a useful association.
        views = [14, 20, 6, 17, 3, 19, 11, 16, 1, 13, 18, 2, 9, 15, 7, 12, 4, 10, 5, 8]
        result = calibrate_opportunity_score(_samples(list(zip(_scores(20), views))), snapshot_window="28d")
        self.assertEqual(result["status"], "no_clear_relationship")
        self.assertEqual(result["recommendation"], "retire")

    def test_groups_that_disagree_are_not_called_a_relationship(self):
        samples = _samples(RISING) + _samples(FALLING, language="tamil", start=10)
        result = calibrate_opportunity_score(samples, snapshot_window="7d")
        self.assertEqual(result["status"], "no_clear_relationship")
        self.assertEqual(result["compared_sample_size"], 20)
        self.assertEqual({group["language"]: group["spearman_rho"] for group in result["groups"]}, {"english": 1.0, "tamil": -1.0})

    def test_equal_scores_are_neither_higher_nor_lower(self):
        result = calibrate_opportunity_score(_samples([(50, 100 * index) for index in range(1, 7)]), snapshot_window="7d")
        group = result["groups"][0]
        self.assertEqual(group["higher_scoring"]["sample_size"], 0)
        self.assertIsNone(group["spearman_rho"])
        self.assertEqual(result["status"], "insufficient_evidence")


def _iso(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


class HistoryCalibrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = str(Path(self.dir.name) / "calibration.db")
        self.store = HistoryStore(self.path)

    def video(self, video_id, score, views, *, window="7d", label="WORKABLE", verified=True, language="english",
              fmt="Short"):
        run_id = self.store.record_analysis_run(video_id, "browse", "emotion", video_id, 7.0, "LOW", label, score, {})
        self.store.link_published_video(
            run_id, video_id, _iso(40), format_val=fmt, language=language,
            ownership_state="verified" if verified else "unverified", ownership_verified=verified,
            verified_channel_id="UC-owner" if verified else None, ownership_verified_at=_iso(39) if verified else None,
        )
        if views is not None:
            self.store.record_performance_snapshot(video_id, 168, views=views, snapshot_window=window)

    def test_only_eligible_packages_are_compared(self):
        self.video("eligible001", 70, 900)
        self.video("eligible002", 40, 200)
        self.video("eligible003", 55, 400)
        self.video("unverified1", 80, 5000, verified=False)
        self.video("nolanguage1", 80, 5000, language=None)
        self.video("nosnapshot1", 80, None)
        self.video("unmeasured1", 0, 5000, label="UNMEASURED")
        self.video("current0001", 80, 5000, window="current")

        result = opportunity_score_calibration(self.store)
        self.assertEqual(result["snapshot_window"], "7d")
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertEqual(result["sample_size"], 3)
        self.assertEqual(result["windows"], {"24h": 0, "7d": 3, "28d": 0})
        self.assertEqual(result["excluded"], {
            "not_ownership_verified": 1, "missing_format_or_language": 1,
            "no_completed_snapshot": 2, "score_not_measured": 1,
        })
        self.assertEqual(result["links_considered"], 8)

    def test_the_window_with_most_evidence_is_used_unless_one_is_asked_for(self):
        for index, (score, views) in enumerate(RISING[:6]):
            self.video(f"dailyvid{index:03d}", score, views, window="24h")
        self.video("weeklyvid01", 50, 300)
        self.assertEqual(opportunity_score_calibration(self.store)["snapshot_window"], "24h")
        self.assertEqual(opportunity_score_calibration(self.store)["status"], "higher_scores_did_better")
        weekly = opportunity_score_calibration(self.store, snapshot_window="7d")
        self.assertEqual((weekly["snapshot_window"], weekly["sample_size"]), ("7d", 1))
        with self.assertRaises(ValueError):
            opportunity_score_calibration(self.store, snapshot_window="current")

    def test_the_endpoint_reports_the_calibration(self):
        self.video("eligible001", 70, 900)
        settings = Settings(database_path=self.path, allowed_hosts="testserver", app_environment="development")
        with patch.object(routes, "get_settings", return_value=settings), \
             patch("win_engine.core.config.get_settings", return_value=settings):
            client = TestClient(create_app(), raise_server_exceptions=False)
            response = client.get("/api/opportunity-score/calibration")
            rejected = client.get("/api/opportunity-score/calibration?window=90d")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "insufficient_evidence")
        self.assertEqual(response.json()["sample_size"], 1)
        self.assertEqual(rejected.status_code, 422)


if __name__ == "__main__":
    unittest.main()
