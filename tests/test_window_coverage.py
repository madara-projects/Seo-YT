"""How many hours a named performance window really covers.

YouTube Analytics reports whole Pacific days, so a nominal 24-hour window is a
range of Pacific dates whose coverage depends on the hour of publication.
"""

import unittest

from win_engine.feedback.history_store import SNAPSHOT_WINDOWS, reportable_window, window_covered_hours
from datetime import datetime, timedelta, timezone


def _range_covered(published_at: str, hours: float) -> float:
    published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    start, end = reportable_window(published, hours, published + timedelta(days=60))
    return window_covered_hours(published_at, end.isoformat())


class WindowCoverageTests(unittest.TestCase):
    def test_publication_hour_decides_how_much_a_24h_window_covers(self):
        # 00:05 and 23:55 Pacific daylight time on 1 August 2026.
        self.assertEqual(_range_covered("2026-08-01T07:05:00Z", 24.0), 47.92)
        self.assertEqual(_range_covered("2026-08-02T06:55:00Z", 24.0), 24.08)

    def test_every_named_window_covers_at_least_its_nominal_hours(self):
        for hour in range(24):
            published = f"2026-08-01T{hour:02d}:30:00Z"
            for name, hours in SNAPSHOT_WINDOWS:
                with self.subTest(published=published, window=name):
                    covered = _range_covered(published, hours)
                    self.assertGreaterEqual(covered, hours)
                    self.assertLess(covered, hours + 24)

    def test_a_daylight_saving_day_is_one_hour_shorter_or_longer(self):
        # Fall back: 1 November 2026 has 25 hours in Pacific time.
        self.assertEqual(window_covered_hours("2026-11-01T07:30:00Z", "2026-11-01"), 24.5)
        # Spring forward: 8 March 2026 has 23 hours.
        self.assertEqual(window_covered_hours("2026-03-08T08:30:00Z", "2026-03-08"), 22.5)

    def test_missing_or_unreadable_values_are_unknown(self):
        self.assertIsNone(window_covered_hours(None, "2026-08-02"))
        self.assertIsNone(window_covered_hours("2026-08-01T07:05:00Z", None))
        self.assertIsNone(window_covered_hours("not a date", "2026-08-02"))
        # A range that ends before publication covers nothing.
        self.assertIsNone(window_covered_hours("2026-08-05T07:05:00Z", "2026-08-01"))


if __name__ == "__main__":
    unittest.main()
