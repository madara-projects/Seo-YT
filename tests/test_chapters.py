"""Regression tests: chapter timestamps come only from the creator.

Fixed times (00:00, 00:30, 02:00, 04:00) were paired with keyword signals for
any long script, and the publishing checklist then told the creator to add
those invented chapters.
"""

import time
import unittest
from unittest.mock import patch

from win_engine.analysis.creator_brief import build_creator_brief
from win_engine.analysis.generation_quality import evaluate_package_quality
from win_engine.analysis.topic_lock import restore_source_casing, source_casing_map
from win_engine.feedback.history_store import HistoryStore
from win_engine.generation.automation_engine import build_automation_workflow
from win_engine.generation.expansion_engine import build_chapters, chapter_block
from win_engine.generation.seo_generator import format_upload_ready_description, generate_seo_suggestions
from win_engine.generation.strategy_engine import _fallback_description
from win_engine.llm import gemini_client

LONG_SCRIPT = " ".join(["Cold brew coffee needs coarse grounds, cold water and a long steep."] * 20)

# The live tutorial: a long-form script with the creator's own timestamps.
OBS_SCRIPT = (
    "In this tutorial I show you how to set up OBS Studio for your first live stream, from download to "
    "going live. We pick the right scenes, get the microphone sounding clean and paste the stream key.\n\n"
    "0:00 Intro\n0:45 Download and install OBS\n2:10 Scenes and sources\n5:30 Microphone and audio setup\n"
    "8:15 Stream key and output settings\n11:00 Going-live checklist\n"
)
OBS_CHAPTERS = [
    {"timestamp": "0:00", "title": "Intro"},
    {"timestamp": "0:45", "title": "Download and install OBS"},
    {"timestamp": "2:10", "title": "Scenes and sources"},
    {"timestamp": "5:30", "title": "Microphone and audio setup"},
    {"timestamp": "8:15", "title": "Stream key and output settings"},
    {"timestamp": "11:00", "title": "Going-live checklist"},
]
OBS_BLOCK = (
    "0:00 Intro\n0:45 Download and install OBS\n2:10 Scenes and sources\n5:30 Microphone and audio setup\n"
    "8:15 Stream key and output settings\n11:00 Going-live checklist"
)
OBS_DESCRIPTION = (
    "Set up OBS Studio for your first live stream, from the download to going live.\n\n"
    "Learn how to download and install OBS, build your scenes and sources, get clean microphone audio "
    "and paste your stream key before you press Go Live."
)


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


class ChaptersInDescriptionTests(unittest.TestCase):
    """A live tutorial had correct chapters, but no description the creator could copy carried them."""

    def test_the_block_lists_one_chapter_per_line(self):
        self.assertEqual(build_chapters(OBS_SCRIPT), OBS_CHAPTERS)
        self.assertEqual(chapter_block(OBS_CHAPTERS), OBS_BLOCK)

    def test_chapters_youtube_would_reject_are_never_inserted(self):
        valid = [{"timestamp": "0:00", "title": "Intro"}, {"timestamp": "1:30", "title": "Grinding"},
                 {"timestamp": "5:00", "title": "Steeping"}]
        for chapters in (
            [],
            valid[:2],                                                      # fewer than three
            [{"timestamp": "0:30", "title": "Intro"}, *valid[1:]],          # does not start at 0:00
            [valid[0], {"timestamp": "0:05", "title": "Grinding"}, valid[2]],  # a chapter under ten seconds
            [valid[0], valid[2], valid[1]],                                 # out of order
            [valid[0], {"timestamp": "0:75", "title": "Grinding"}, valid[2]],  # not a time
            [valid[0], {"timestamp": "1:30", "title": "  "}, valid[2]],     # no title
            [valid[0], "1:30 Grinding", valid[2]],                          # not a chapter
        ):
            with self.subTest(chapters=chapters):
                self.assertEqual(chapter_block(chapters), "")
        self.assertEqual(chapter_block([{"timestamp": "00:00", "title": "Intro"}, *valid[1:]]),
                         "00:00 Intro\n1:30 Grinding\n5:00 Steeping")

    def test_the_block_goes_after_the_prose_and_before_the_hashtags(self):
        description = format_upload_ready_description(
            OBS_DESCRIPTION, ["#OBSStudio", "#LiveStreaming"], category="tech", topic="obs studio",
            chapters=OBS_CHAPTERS,
        )
        self.assertTrue(description.endswith(f"\n\n{OBS_BLOCK}\n\n#OBSStudio #LiveStreaming"), description)
        self.assertIn("Learn how to download and install OBS", description)

    def test_timestamps_already_in_the_description_are_not_repeated(self):
        # A writer that pasted (part of) the list itself, and a second formatting pass.
        written = f"{OBS_DESCRIPTION}\n\nChapters:\n0:00 Intro\n0:45 Download and install OBS\n\n#OBSStudio"
        once = format_upload_ready_description(written, ["#OBSStudio"], chapters=OBS_CHAPTERS)
        twice = format_upload_ready_description(once, ["#OBSStudio"], chapters=OBS_CHAPTERS)
        self.assertEqual(once, twice)
        for chapter in OBS_CHAPTERS:
            with self.subTest(timestamp=chapter["timestamp"]):
                self.assertEqual(once.count(f"{chapter['timestamp']} "), 1)
        self.assertIn(f"\n\n{OBS_BLOCK}\n\n#OBSStudio", once)

    def test_without_valid_chapters_the_description_is_unchanged(self):
        for chapters in (None, [], OBS_CHAPTERS[:2]):
            with self.subTest(chapters=chapters):
                self.assertEqual(
                    format_upload_ready_description(OBS_DESCRIPTION, ["#OBSStudio"], chapters=chapters),
                    f"{OBS_DESCRIPTION}\n\n#OBSStudio",
                )

    def test_timestamps_the_creator_did_not_give_never_reach_the_description(self):
        # YouTube would turn a writer's invented list into chapters; a Short, a
        # video without timestamps and an invalid creator list get none.
        written = f"{OBS_DESCRIPTION}\n\nChapters:\n0:00 Intro\n0:30 Install\n1:10 Scenes\n\n#obs"
        invalid = [{"timestamp": "0:05", "title": "Intro"}, *OBS_CHAPTERS[1:]]
        for chapters in (None, [], invalid):
            with self.subTest(chapters=chapters):
                self.assertEqual(
                    format_upload_ready_description(written, ["#obs"], chapters=chapters), f"{OBS_DESCRIPTION}\n\n#obs"
                )

    def test_the_quality_gate_does_not_judge_the_block(self):
        brief = build_creator_brief(script=OBS_SCRIPT, video_format="tutorial")
        # A full description near the 120-word band: the block's words must not
        # push it out, nor count as a repeated keyword list.
        prose = OBS_DESCRIPTION + "\n\n" + " ".join(
            ["Every setting is shown on screen, so you can pause and copy it into OBS Studio as you go."] * 4
        )
        package = {"title": "How to set up OBS Studio for your first live stream", "variants": [],
                   "tags": ["obs studio"], "hashtags": ["#OBSStudio"]}

        def judged(description):
            gate = evaluate_package_quality({**package, "description": description}, script=OBS_SCRIPT,
                                            creator_brief=brief)
            quality = gate["final_seo_quality"]
            return ([item["code"] for item in gate["issues"]], [item["code"] for item in gate["warnings"]],
                    quality["description_score"])

        with_block = format_upload_ready_description(prose, ["#OBSStudio"], chapters=OBS_CHAPTERS)
        self.assertIn(OBS_BLOCK, with_block)
        self.assertEqual(judged(with_block), judged(format_upload_ready_description(prose, ["#OBSStudio"])))

    def test_the_hashtag_line_is_judged_as_hashtags_not_prose(self):
        # Read as a word, "#LiveStream" called this tutorial a livestream (RED).
        brief = build_creator_brief(script=OBS_SCRIPT, video_format="tutorial")
        description = format_upload_ready_description(OBS_DESCRIPTION, ["#OBSStudio", "#LiveStream"],
                                                       chapters=OBS_CHAPTERS)
        gate = evaluate_package_quality(
            {"title": "How to set up OBS Studio for your first live stream", "variants": [],
             "description": description, "tags": ["obs studio"], "hashtags": ["#OBSStudio", "#LiveStream"]},
            script=OBS_SCRIPT, creator_brief=brief,
        )
        self.assertNotIn("invented_format", [item["code"] for item in gate["issues"]])

    def test_a_chapter_title_does_not_lend_its_capital_to_prose(self):
        # "0:45 Download and install OBS" opens a chapter title; it is not a name
        # the creator always capitalises, so "how to download" stays lowercase.
        casing = source_casing_map(OBS_SCRIPT)
        self.assertEqual(restore_source_casing("how to download and install obs", casing),
                         "how to download and install OBS")
        for word in ("download", "scenes", "microphone", "stream", "going"):
            with self.subTest(word=word):
                self.assertNotIn(word, casing)

    def test_a_labelled_quote_does_not_lend_its_first_capital_to_titles(self):
        # "the quote is- Stop explaining…" opens the quote: a live title read
        # "Why you should Stop explaining yourself".
        for script in (
            "the quote is- Stop explaining yourself to people who already decided to misunderstand you.",
            "the quote is -Stop explaining yourself to people who misunderstand you.",
            "Quote: Stop explaining yourself. Video – Stop motion rain",
        ):
            with self.subTest(script=script):
                casing = source_casing_map(script)
                self.assertNotIn("stop", casing)
                self.assertEqual(restore_source_casing("Why you should stop explaining yourself", casing),
                                 "Why you should stop explaining yourself")
        # A name the creator capitalises mid-sentence still keeps its capital.
        self.assertEqual(source_casing_map("the quote is- ask Priya why we stop")["priya"], "Priya")

    def test_the_local_description_does_not_flatten_the_list_into_prose(self):
        description = _fallback_description(OBS_SCRIPT)
        self.assertIn("set up OBS Studio for your first live stream", description)
        self.assertNotIn("0:45", description)
        self.assertNotIn("Intro", description)


def _obs_writer_package():
    title = "How to Set Up OBS Studio for Your First Live Stream"
    return {"title": title, "variants": [title, "OBS Studio Setup for Your First Live Stream"],
            "description": OBS_DESCRIPTION, "tags": ["obs studio", "obs studio setup"],
            "hashtags": ["#OBSStudio"]}


class ChaptersReachEveryCopyTests(unittest.TestCase):
    def generate(self, script, writer_output, **brief_fields):
        store = HistoryStore(":memory:")
        brief = build_creator_brief(script=script, **brief_fields)
        research = {"history_store": store, "youtube_results": [], "entity_signals": [], "top_opportunities": [],
                    "upload_timing": {}, "thumbnail_intelligence": {}, "keyword_signals": []}
        with patch("win_engine.generation.strategy_engine.write_multilang_packages_with_source",
                   return_value=({"english": writer_output}, "gemini" if writer_output else "fallback")), \
             patch("win_engine.generation.strategy_engine.last_generation_diagnostics", return_value={}), \
             patch.object(gemini_client, "is_available", return_value=False):
            response = generate_seo_suggestions(script, research, context={
                "language": "english", "region": "global", "creator_brief": brief,
            })
        return response, store

    def test_the_description_history_and_every_package_option_carry_the_chapters(self):
        for writer_output in (_obs_writer_package(), None):  # Gemini's package and the local fallback
            with self.subTest(source="gemini" if writer_output else "fallback"):
                response, store = self.generate(OBS_SCRIPT, writer_output, video_format="tutorial")
                self.assertEqual(response["chapters"], OBS_CHAPTERS)
                descriptions = {
                    "top level": response["description"],
                    **{f"multilang {lang}": pkg["description"] for lang, pkg in response["multilang"].items()},
                    "history": store.history_run(response["history_run_id"])["package"]["description"],
                }
                self.assertTrue(response["title_thumbnail_packages"])
                chosen = store.select_generated_package(response["history_run_id"], "package-a")
                descriptions["selected package"] = chosen["package"]["description"]
                for where, description in descriptions.items():
                    with self.subTest(where=where):
                        self.assertEqual(description.count(OBS_BLOCK), 1, description)
                        hashtags = description.rsplit("\n\n", 1)[-1]
                        self.assertTrue(hashtags.startswith("#"), description)
                        self.assertTrue(description.split(OBS_BLOCK)[1].startswith("\n\n#"), description)
                        self.assertNotIn("how to Download", description)

    def test_a_short_never_gets_a_chapters_block(self):
        script = "0:00 Intro\n0:20 Middle\n0:40 End\nA quick look at a rainy street #shorts"
        response, _ = self.generate(script, None, video_format="youtube_shorts")
        self.assertEqual(response["chapters"], [])
        self.assertNotIn("0:20", response["description"])


if __name__ == "__main__":
    unittest.main()
