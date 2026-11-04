"""Only tags observed by a window's end are credited, and the writer states how each example's title is known."""

from __future__ import annotations

import json
from datetime import timedelta

from tests import test_channel_learning as base
from win_engine.feedback.channel_learning import learning_summary
from win_engine.llm import seo_writer


class LearningAttributionProvenanceTests(base.ChannelLearningFixture):
    """The fixture connects the "owner" channel its links are verified for."""

    def store_metadata(self, video_id: str, metadata: dict) -> None:
        link = next(item for item in self.store.published_video_links_list() if item["youtube_video_id"] == video_id)
        with self.store._connect() as connection:
            connection.execute(
                "UPDATE published_video_links SET youtube_metadata_json = ? WHERE id = ?",
                (json.dumps(metadata), int(link["id"])),
            )

    def leader(self, title: str) -> str:
        for views in base.PatternGateTests.SPLIT[:-1]:
            self.linked(views=views)
        return self.linked(views=900, title=title)

    @staticmethod
    def line_after(block: str, title: str) -> str:
        lines = block.splitlines()
        index = next(i for i, line in enumerate(lines) if f'"{title}"' in line)
        return lines[index + 1]

    def test_an_assumed_unchanged_leader_contributes_no_tags_and_none_are_called_actual(self):
        video_id = self.leader("Confirmed original title")
        # The reviewer's probe: no observation from the window, and today's
        # lookup shows the confirmed title with a tag edited after the window.
        self.store_metadata(video_id, {"title": "Confirmed original title", "tags": ["new tag edited after old window"]})
        summary = learning_summary(self.path)
        # The video's numbers still count and still lead.
        self.assertEqual(summary["sample_size"], 10)
        leader = summary["best_videos"][0]
        self.assertEqual((leader["video_id"], leader["views"]), (video_id, 900))
        self.assertEqual((leader["title"], leader["actual_tags"], leader["title_attribution"]),
                         ("Confirmed original title", None, "assumed_unchanged"))
        block = self.prompt_block(summary)
        self.assertIn('"Confirmed original title"', block)
        self.assertNotIn("new tag edited after old window", block)
        self.assertNotIn("Actual uploaded tags", block)

    def test_the_title_provenance_is_stated_for_each_example(self):
        video_id = self.leader("Confirmed original title")
        self.store_metadata(video_id, {"title": "Confirmed original title", "tags": ["new tag edited after old window"]})
        block = self.prompt_block(learning_summary(self.path))
        self.assertIn("Title provenance: assumed unchanged since linking (not observed during the measured window)",
                      self.line_after(block, "Confirmed original title"))
        self.assertNotIn("observed live", block)

    def test_observed_tags_still_appear_as_actual_uploaded_tags(self):
        video_id = self.leader("Original title")
        original = {"observed_at": (base.PUBLISHED + timedelta(hours=1)).isoformat(), "title": "Original title",
                    "tags": ["original tag"], "description": None}
        edited = {"observed_at": base.NOW.isoformat(), "title": "Edited later", "tags": ["edited tag"], "description": None}
        self.store_metadata(video_id, {"title": "Edited later", "tags": ["edited tag"], "observations": [original, edited]})
        summary = learning_summary(self.path)
        leader = summary["best_videos"][0]
        self.assertEqual((leader["video_id"], leader["title"], leader["actual_tags"], leader["title_attribution"]),
                         (video_id, "Original title", ["original tag"], "observed"))
        block = self.prompt_block(summary)
        self.assertEqual(self.line_after(block, "Original title").strip(),
                         "Title provenance: observed live during the measured window.")
        self.assertIn("  Actual uploaded tags: original tag", block)
        self.assertNotIn("edited tag", block)
        self.assertNotIn("Edited later", block)

    def test_the_snapshots_own_metadata_seen_by_the_windows_end_supplies_observed_tags(self):
        video_id = self.leader("Confirmed title")
        recorded = {"observed_at": (base.PUBLISHED + timedelta(hours=2)).isoformat(), "title": "Live at the time",
                    "tags": ["then"], "description": None}
        self.set_snapshot(video_id, metadata_json=json.dumps(recorded))
        self.store_metadata(video_id, {"title": "Confirmed title", "tags": ["now"]})
        summary = learning_summary(self.path)
        leader = summary["best_videos"][0]
        self.assertEqual((leader["title"], leader["actual_tags"], leader["title_attribution"]),
                         ("Live at the time", ["then"], "observed"))
        block = self.prompt_block(summary)
        self.assertIn("  Actual uploaded tags: then", block)
        self.assertNotIn("now", block.split("Actual uploaded tags:")[1].splitlines()[0])

    def test_the_writer_never_calls_unobserved_tags_actual(self):
        # A caller passing tags without an observed attribution: shown nowhere.
        for attribution in ("assumed_unchanged", None):
            video = {"title": "Example title", "views": 900, "actual_tags": ["stale tag"]}
            if attribution:
                video["title_attribution"] = attribution
            block = seo_writer._build_channel_learning_block({
                "confidence": "moderate", "confidence_label": "Moderate", "learning_allowed": True,
                "best_videos": [video], "cohort": {"learning_allowed": True, "sample_size": 10},
            })
            self.assertIn('"Example title"', block)
            self.assertNotIn("stale tag", block)
            self.assertNotIn("Actual uploaded tags", block)
            self.assertIn("Title provenance:", self.line_after(block, "Example title"))
