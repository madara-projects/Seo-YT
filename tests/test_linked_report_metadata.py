"""The linked report compares only the uploaded fields YouTube reported.

oEmbed and the bare-id fallback report no tags or description, and sometimes
no title. Those must read as unknown, never as "used none of the tags" or as
a title match borrowed from the package's own title.
"""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from win_engine.core.config import Settings
from win_engine.feedback.history_store import HistoryStore
from win_engine.integrations.youtube_channel import YouTubeChannelService

TITLE = "Budget Phone Camera Test"
TAGS = ["budget phone", "camera test", "battery life", "gaming test"]
DESCRIPTION = "Budget phone camera test with battery life and gaming results."
UNKNOWN_TAGS = "YouTube has not reported this video's tags, so whether the generated tags were used is unknown."
UNKNOWN_TITLE = "YouTube has not reported the uploaded title, so whether the generated title was used is unknown."


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _oembed(*_args, **_kwargs):
    return _Response(json.dumps({"title": TITLE, "author_name": "Some Channel"}).encode())


def _data_api(**fields):
    """Metadata shaped as the Data API lookup stores it."""
    return {
        "video_id": "datavideo01", "title": TITLE, "description": DESCRIPTION, "tags": TAGS,
        "published_at": "2026-10-01T00:00:00Z", "ownership_verified": False,
        "metadata_source": "youtube_data_api", "fetched_at": "2026-10-02T00:00:00+00:00",
        **fields,
    }


class LinkedReportMetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.path = str(Path(self.dir.name) / "history.db")
        self.store = HistoryStore(self.path)

    def tearDown(self) -> None:
        self.dir.cleanup()

    def linked_run(self, video_id: str, tags: list[str] = TAGS) -> tuple[int, int]:
        with self.store._connect() as connection:
            run_id = int(connection.execute(
                "INSERT INTO analysis_runs (query, created_at, title, payload_json) VALUES (?, ?, ?, ?)",
                ("phone", datetime.now(timezone.utc).isoformat(), TITLE,
                 json.dumps({"title": TITLE, "tags": tags, "description": DESCRIPTION})),
            ).lastrowid)
        # The link's selected title defaults to the generated one, as the link route stores it.
        link_id = self.store.link_published_video(
            run_id, video_id, (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(),
            selected_title=TITLE, selected_tags_json=json.dumps(tags),
        )
        return run_id, link_id

    def public_lookup(self, video_id: str, urlopen) -> dict:
        service = YouTubeChannelService(Settings(database_path=self.path, youtube_api_key="", youtube_api_keys=""))
        with patch("urllib.request.urlopen", side_effect=urlopen):
            return service.verify_public_video(video_id)

    def test_oembed_metadata_leaves_tags_and_description_unknown(self):
        run_id, link_id = self.linked_run("publicvid01")
        metadata = self.public_lookup("publicvid01", _oembed)
        self.assertEqual(metadata["metadata_source"], "oembed")
        self.store.update_linked_video_metadata(link_id, metadata)

        report = self.store.linked_package_report(run_id)
        usage = report["package_usage"]
        self.assertEqual(usage["uploaded_metadata_known"], {"title": True, "tags": False, "description": False})
        for field in ("uploaded_tags", "matching_tags", "missing_generated_tags", "extra_uploaded_tags",
                      "description_match_percent", "uploaded_hashtags", "matching_hashtags"):
            self.assertIsNone(usage[field], field)
        # oEmbed does report the title, so that comparison stands.
        self.assertEqual(usage["uploaded_title"], TITLE)
        self.assertTrue(usage["title_match"])
        diagnosis = report["diagnosis"]
        self.assertIn(UNKNOWN_TAGS, diagnosis["needs_improvement"])
        self.assertFalse([line for line in diagnosis["what_worked"] + diagnosis["needs_improvement"]
                          if "generated tags are on" in line or line.startswith("You used")])

    def test_data_api_zero_is_a_real_zero(self):
        run_id, link_id = self.linked_run("notagsvid01")
        self.store.update_linked_video_metadata(link_id, _data_api(video_id="notagsvid01", tags=[], description=""))

        report = self.store.linked_package_report(run_id)
        usage = report["package_usage"]
        self.assertEqual(usage["uploaded_metadata_known"], {"title": True, "tags": True, "description": True})
        self.assertEqual(usage["uploaded_tags"], [])
        self.assertEqual(usage["matching_tags"], [])
        self.assertEqual(usage["missing_generated_tags"], TAGS)
        self.assertEqual(usage["description_match_percent"], 0.0)
        improve = report["diagnosis"]["needs_improvement"]
        self.assertIn(
            "None of the 4 generated tags are on the uploaded video, so their effect cannot be evaluated.", improve,
        )
        self.assertNotIn(UNKNOWN_TAGS, improve)

        # A single generated tag reads in the singular.
        run_id, link_id = self.linked_run("notagsvid03", tags=TAGS[:1])
        self.store.update_linked_video_metadata(link_id, _data_api(video_id="notagsvid03", tags=[]))
        self.assertIn(
            "The generated tag is not on the uploaded video, so its effect cannot be evaluated.",
            self.store.linked_package_report(run_id)["diagnosis"]["needs_improvement"],
        )

    def test_blank_data_api_title_is_unknown(self):
        # YouTube does not allow an untitled public video, so a blank title is
        # a lookup that saw nothing, not a mismatch with the generated title.
        run_id, link_id = self.linked_run("blankvid001")
        self.store.update_linked_video_metadata(link_id, _data_api(video_id="blankvid001", title="   "))
        usage = self.store.linked_package_report(run_id)["package_usage"]
        self.assertEqual(usage["uploaded_metadata_known"], {"title": False, "tags": True, "description": True})
        self.assertIsNone(usage["uploaded_title"])
        self.assertIsNone(usage["title_match"])

    def test_unfetched_title_is_not_borrowed_from_the_package(self):
        # Nothing fetched at all, then the bare-id fallback when YouTube is unreachable.
        run_id, link_id = self.linked_run("offlinevid1")
        for step in ("never fetched", "bare id"):
            if step == "bare id":
                metadata = self.public_lookup("offlinevid1", OSError("offline"))
                self.assertEqual(metadata["metadata_source"], "unverified_id")
                self.store.update_linked_video_metadata(link_id, metadata)
            report = self.store.linked_package_report(run_id)
            usage = report["package_usage"]
            self.assertIsNone(usage["uploaded_title"], step)
            self.assertIsNone(usage["title_match"], step)
            self.assertEqual(usage["uploaded_metadata_known"], {"title": False, "tags": False, "description": False}, step)
            self.assertIn(UNKNOWN_TITLE, report["diagnosis"]["needs_improvement"], step)
            self.assertFalse([line for line in report["diagnosis"]["what_worked"] if "title" in line], step)

    def test_oembed_refresh_keeps_tags_the_data_api_reported(self):
        # With and without the lookup's fetched_at stamp: real values are never placeholders.
        for index, data_api in enumerate((_data_api(tags=TAGS[:2]), {
            key: value for key, value in _data_api(tags=TAGS[:2]).items() if key != "fetched_at"
        })):
            video_id = f"datavideo0{index}"
            run_id, link_id = self.linked_run(video_id)
            self.store.update_linked_video_metadata(link_id, {**data_api, "video_id": video_id})
            self.store.update_linked_video_metadata(link_id, self.public_lookup(video_id, _oembed))

            report = self.store.linked_package_report(run_id)
            usage = report["package_usage"]
            self.assertEqual(usage["uploaded_metadata_known"], {"title": True, "tags": True, "description": True})
            self.assertEqual(usage["matching_tags"], TAGS[:2])
            self.assertEqual(usage["missing_generated_tags"], TAGS[2:])
            self.assertEqual(usage["description_match_percent"], 100.0)
            self.assertIn("You used 2 of 4 generated tags.", report["diagnosis"]["what_worked"])

    def test_data_api_zero_survives_a_later_oembed_refresh(self):
        run_id, link_id = self.linked_run("notagsvid02")
        self.store.update_linked_video_metadata(link_id, _data_api(video_id="notagsvid02", tags=[], description=""))
        self.store.update_linked_video_metadata(link_id, self.public_lookup("notagsvid02", _oembed))

        usage = self.store.linked_package_report(run_id)["package_usage"]
        self.assertEqual(usage["uploaded_metadata_known"], {"title": True, "tags": True, "description": True})
        self.assertEqual(usage["matching_tags"], [])
        self.assertEqual(usage["description_match_percent"], 0.0)

    def test_placeholders_saved_by_the_old_fallbacks_are_unknown(self):
        # Before the merge kept unknown fields out, the fallbacks stored "" and []
        # for what they cannot see, and "YouTube Video" when they had no title.
        run_id, link_id = self.linked_run("legacyvid01")
        self.store.update_linked_video_metadata(link_id, {
            "video_id": "legacyvid01", "title": "YouTube Video", "description": "", "tags": [],
            "published_at": None, "ownership_verified": False, "metadata_source": "unverified_id",
        })
        usage = self.store.linked_package_report(run_id)["package_usage"]
        self.assertEqual(usage["uploaded_metadata_known"], {"title": False, "tags": False, "description": False})
        self.assertIsNone(usage["title_match"])
        self.assertIsNone(usage["matching_tags"])
        self.assertIsNone(usage["description_match_percent"])

        # An old oEmbed row still holds a real title.
        run_id, link_id = self.linked_run("legacyvid02")
        self.store.update_linked_video_metadata(link_id, {
            "video_id": "legacyvid02", "title": "Another Upload", "description": "", "tags": [],
            "published_at": None, "ownership_verified": False, "metadata_source": "oembed",
        })
        usage = self.store.linked_package_report(run_id)["package_usage"]
        self.assertEqual(usage["uploaded_metadata_known"], {"title": True, "tags": False, "description": False})
        self.assertEqual(usage["uploaded_title"], "Another Upload")
        self.assertFalse(usage["title_match"])
        self.assertIsNone(usage["missing_generated_tags"])

        # The first fallbacks stored only the placeholder title and published_at,
        # with no metadata_source: neither a match nor a mismatch is known.
        run_id, link_id = self.linked_run("legacyvid03")
        self.store.update_linked_video_metadata(link_id, {"title": "YouTube Video", "published_at": None})
        report = self.store.linked_package_report(run_id)
        usage = report["package_usage"]
        self.assertEqual(usage["uploaded_metadata_known"], {"title": False, "tags": False, "description": False})
        self.assertIsNone(usage["uploaded_title"])
        self.assertIsNone(usage["title_match"])
        self.assertIn(UNKNOWN_TITLE, report["diagnosis"]["needs_improvement"])

        # A Data API record keeps even that exact title as the real one.
        run_id, link_id = self.linked_run("datavideo02")
        self.store.update_linked_video_metadata(link_id, _data_api(video_id="datavideo02", title="YouTube Video"))
        usage = self.store.linked_package_report(run_id)["package_usage"]
        self.assertEqual(usage["uploaded_title"], "YouTube Video")
        self.assertFalse(usage["title_match"])


if __name__ == "__main__":
    unittest.main()
