"""Outlier scores never treat a missing statistic as a real zero."""

import unittest
from datetime import datetime, timedelta, timezone

from win_engine.scoring.outlier_engine import score_outliers


def _published(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def _row(video_id, **overrides):
    row = {
        "video_id": video_id, "view_count": "1000000", "like_count": "20000", "comment_count": "1000",
        "subscriber_count": "2000000", "published_at": _published(100), "duration": "PT8M",
    }
    return {**row, **overrides}


class MissingStatisticsTests(unittest.TestCase):
    def test_hidden_subscriber_count_gets_no_score_instead_of_a_huge_one(self):
        # Two identical videos: zero-filled subscribers once scored the hidden
        # one 6 billion against 3 thousand and called it a classic outlier.
        known, hidden = score_outliers([_row("hidden", subscriber_count=None), _row("known")])

        self.assertEqual(known["video_id"], "known")
        self.assertEqual(known["views_per_subscriber"], 0.5)
        self.assertIsNotNone(known["outlier_score"])
        self.assertEqual(hidden["video_id"], "hidden")
        self.assertIsNone(hidden["outlier_score"])
        self.assertIsNone(hidden["views_per_subscriber"])
        self.assertEqual(hidden["views_per_day"], 10000.0)
        self.assertIn("unavailable", hidden["opportunity_reasons"][0])
        self.assertIn("subscriber count", hidden["opportunity_reasons"][0])
        self.assertFalse(any("far above channel size" in reason for reason in hidden["opportunity_reasons"]))
        self.assertFalse(hidden["small_channel_outlier"])

    def test_missing_publish_date_is_not_a_year_old_video(self):
        (row,) = score_outliers([_row("undated", published_at=None, view_count="3650")])

        self.assertIsNone(row["views_per_day"])
        self.assertIsNone(row["outlier_score"])
        self.assertIn("publish date", row["opportunity_reasons"][0])

    def test_zero_subscribers_give_no_ratio(self):
        (row,) = score_outliers([_row("empty", subscriber_count="0")])

        self.assertIsNone(row["views_per_subscriber"])
        self.assertIsNone(row["outlier_score"])

    def test_unscored_rows_sort_after_scored_rows_in_search_order(self):
        rows = score_outliers([
            _row("missing-a", view_count=None),
            _row("low", view_count="1000"),
            _row("missing-b", subscriber_count=None),
            _row("high"),
        ])

        self.assertEqual([row["video_id"] for row in rows], ["high", "low", "missing-a", "missing-b"])

    def test_hidden_likes_and_comments_leave_engagement_unknown_but_keep_the_score(self):
        (row,) = score_outliers([_row("quiet", like_count=None, comment_count=None)])

        self.assertIsNone(row["engagement_density"])
        self.assertIsNone(row["retention_proxy"])
        self.assertIsNotNone(row["outlier_score"])


class ScoreFormulaTests(unittest.TestCase):
    def test_region_no_longer_scales_the_score(self):
        # 100 views/day x 10 views/subscriber x engagement 6.06 (5 comments per
        # thousand views + 0.05 likes per view, x1.2 for a 2-minute video) x
        # 1.5 recency x 1.25 small channel. No regional multiplier on top.
        (row,) = score_outliers([_row(
            "exact", view_count="1000", like_count="50", comment_count="5", subscriber_count="100",
            published_at=_published(10), duration="PT2M",
        )])

        self.assertAlmostEqual(row["outlier_score"], 11362.5, delta=1)
        self.assertEqual(row["regional_weight"], 1.0)

    def test_durations_with_days_are_parsed(self):
        # The old parser read "P1DT2H" as 0 seconds, i.e. an unknown length.
        rows = {row["video_id"]: row for row in score_outliers([_row("long", duration="P1DT2H"),
                                                                 _row("live", duration="P0D")])}

        self.assertEqual(rows["long"]["length_normalization"], 0.95)
        self.assertEqual(rows["live"]["length_normalization"], 1.0)


if __name__ == "__main__":
    unittest.main()
