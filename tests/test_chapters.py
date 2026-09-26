"""Regression tests: chapter timestamps come only from the creator.

Fixed times (00:00, 00:30, 02:00, 04:00) were paired with keyword signals for
any long script, and the publishing checklist then told the creator to add
those invented chapters.
"""

import time
import unittest

from win_engine.generation.automation_engine import build_automation_workflow
from win_engine.generation.expansion_engine import build_chapters

LONG_SCRIPT = " ".join(["Cold brew coffee needs coarse grounds, cold water and a long steep."] * 20)


class ChapterTests(unittest.TestCase):
    def test_no_times_are_invented(self):
        self.assertEqual(build_chapters(LONG_SCRIPT, {"duration_seconds": 600}), [])

    def test_the_creators_own_chapter_list_is_kept_verbatim(self):
        script = "0:00 Intro\n00:45 - Grinding the beans\n3:10 Steeping overnight\n1:02:15 Taste test\n" + LONG_SCRIPT
        self.assertEqual(build_chapters(script, {"content": script}), [
            {"timestamp": "0:00", "title": "Intro"},
            {"timestamp": "00:45", "title": "Grinding the beans"},
            {"timestamp": "3:10", "title": "Steeping overnight"},
            {"timestamp": "1:02:15", "title": "Taste test"},
        ])

    def test_lists_youtube_would_not_turn_into_chapters_are_ignored(self):
        for script in (
            "0:00 Intro\n2:00 Brewing",                           # fewer than three
            "0:30 Intro\n2:00 Brewing\n4:00 Tasting",             # does not start at 0:00
            "0:00 Intro\n0:05 Brewing\n4:00 Tasting",             # a chapter under ten seconds
            "0:00 Intro\n4:00 Brewing\n2:00 Tasting",             # out of order
            "We left at 10:30 and reached the hotel by 12:15.",   # times inside prose
        ):
            with self.subTest(script=script):
                self.assertEqual(build_chapters(script + "\n" + LONG_SCRIPT), [])

    def test_shorts_never_have_chapters(self):
        script = "0:00 Intro\n0:20 Middle\n0:40 End"
        self.assertEqual(build_chapters(script, {"video_format": "youtube_shorts", "content": script}), [])

    def test_times_past_59_are_not_timestamps(self):
        for script in ("0:00 Intro\n0:75 Grinding\n3:00 Steeping", "0:00 Intro\n75:00 Grinding\n80:00 Steeping"):
            with self.subTest(script=script):
                self.assertEqual(build_chapters(script + "\n" + LONG_SCRIPT), [])

    def test_the_list_is_one_block_of_timestamp_lines(self):
        chapters = "0:00 Intro\n1:30 Grinding the beans\n5:00 Steeping overnight"
        expected = [
            {"timestamp": "0:00", "title": "Intro"},
            {"timestamp": "1:30", "title": "Grinding the beans"},
            {"timestamp": "5:00", "title": "Steeping overnight"},
        ]
        for script in (
            # A later narration line in order is not appended as a chapter.
            f"{chapters}\n{LONG_SCRIPT}\n7:45 the flight took off late",
            # A later stray time out of order does not void the creator's list.
            f"{chapters}\n{LONG_SCRIPT}\n2:00 we reached the hotel",
            # A stray time line before the list is not the list.
            f"7:45 the flight took off late\n{LONG_SCRIPT}\n{chapters}",
            # Blank lines inside the list are allowed.
            chapters.replace("\n", "\n\n") + "\n" + LONG_SCRIPT,
        ):
            with self.subTest(script=script[:40]):
                self.assertEqual(build_chapters(script), expected)

    def test_a_long_line_is_parsed_in_linear_time(self):
        line = "0:00 a" + " " * 20000 + "b"
        started = time.perf_counter()
        self.assertEqual(build_chapters(line + "\n" + LONG_SCRIPT), [])
        self.assertLess(time.perf_counter() - started, 0.5)

    def test_checklist_only_mentions_chapters_the_creator_supplied(self):
        graph = {"supporting_topics": []}
        with_chapters = build_automation_workflow("Cold brew at home", ["#ColdBrew"], [{"timestamp": "0:00", "title": "Intro"}], graph)
        without = build_automation_workflow("Cold brew at home", ["#ColdBrew"], [], graph)
        self.assertIn("your chapter timestamps", " ".join(with_chapters["publish_workflow"]))
        self.assertIn("Add manual timestamps once the cut is final.", without["publish_workflow"])


if __name__ == "__main__":
    unittest.main()
