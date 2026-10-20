"""Audit follow-ups for the research service's YouTube search cache.

Two identical requests that miss the cache at the same time make one search,
and a search short of some rows' statistics is never served later as a
complete, successful answer.
"""

import threading
import time
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from win_engine.core.config import Settings
from win_engine.ingestion import cache as cache_module
from win_engine.ingestion import research_service
from win_engine.ingestion.research_service import ResearchService


def _row(video_id, **overrides):
    row = {
        "video_id": video_id, "title": "Grief quotes", "description": "", "channel_title": "Channel",
        "view_count": "1000", "like_count": "10", "comment_count": "1", "subscriber_count": "100",
        "published_at": "2026-09-01T00:00:00Z", "duration": "PT30S",
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    return {**row, **overrides}


class CountingYouTube:
    """A client that counts its calls; a search can be held open until released."""

    def __init__(self, rows, *, statistics_complete=True):
        self.rows = rows
        self.statistics_complete = statistics_complete
        self.search_calls = 0
        self.statistics_calls = 0
        self.search_entered = threading.Event()
        self.release_search = threading.Event()
        self.release_search.set()
        self._lock = threading.Lock()

    def search_videos(self, query, max_results=5, raise_on_error=False, **locale):
        with self._lock:
            self.search_calls += 1
        self.search_entered.set()
        self.release_search.wait(timeout=5)
        return [dict(row) for row in self.rows]

    def attach_statistics(self, rows):
        with self._lock:
            self.statistics_calls += 1
        if not self.statistics_complete:
            return [dict(row) for row in rows]
        now = datetime.now(timezone.utc).isoformat()
        return [{**row, "view_count": "1000", "subscriber_count": "100", "captured_at": now} for row in rows]

    def runtime_state(self):
        return {"active_key_index": 1, "available_key_count": 1, "warning": None, "quota_date": "2026-10-20"}


class _AuditTestCase(unittest.TestCase):
    def setUp(self):
        # The cache is process-wide; each test starts from an empty registry.
        patcher = patch.dict(cache_module._SHARED_CACHES, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def service(youtube):
        # A service per request, as the routes build them; the cache is shared.
        service = ResearchService(Settings(database_path=":memory:"))
        service._youtube = youtube
        service._history = MagicMock()
        return service

    @staticmethod
    def search(service, query="grief quotes"):
        return service._search_research_queries([{"type": "primary", "query": query}])


class SingleFlightTests(_AuditTestCase):
    def test_concurrent_identical_requests_make_one_search(self):
        youtube = CountingYouTube([_row("v1")])
        youtube.release_search.clear()  # the first search stays open until the second request is waiting
        outcomes = {}

        def run(name):
            outcomes[name] = self.search(self.service(youtube))

        first = threading.Thread(target=run, args=("first",))
        second = threading.Thread(target=run, args=("second",))
        first.start()
        self.assertTrue(youtube.search_entered.wait(timeout=5))
        second.start()
        time.sleep(0.2)  # time for the second request to reach the cache while the first search is open
        youtube.release_search.set()
        first.join(timeout=5)
        second.join(timeout=5)

        self.assertEqual((youtube.search_calls, youtube.statistics_calls), (1, 0))
        rows = {name: [row["video_id"] for row in outcome[0]] for name, outcome in outcomes.items()}
        self.assertEqual(rows, {"first": ["v1"], "second": ["v1"]})
        caches = sorted(outcome[1]["query_attempts"][0]["cache"] for outcome in outcomes.values())
        self.assertEqual(caches, ["hit", "miss"])
        self.assertEqual(research_service._FLIGHTS, {})  # nothing is left behind once both are done


class PartialResultTests(_AuditTestCase):
    ROWS = [_row("known"), _row("gap", view_count=None, subscriber_count=None, captured_at=None)]

    def test_a_partial_result_is_not_served_later_as_a_complete_success(self):
        youtube = CountingYouTube(self.ROWS)
        rows, diagnostics = self.search(self.service(youtube))
        self.assertEqual(diagnostics["query_attempts"][0]["status"], "partial")
        self.assertEqual((diagnostics["queries_successful"], diagnostics["queries_partial"]), (0, 1))
        self.assertEqual([row["video_id"] for row in rows], ["known", "gap"])

        later_rows, later = self.search(self.service(youtube))

        # The missing statistics are asked for again (two 1-unit lookups), never another search.
        self.assertEqual((youtube.search_calls, youtube.statistics_calls), (1, 1))
        self.assertEqual(later["query_attempts"][0]["cache"], "search_page")
        self.assertEqual(later["query_attempts"][0]["status"], "success")
        self.assertEqual({row["video_id"]: row["view_count"] for row in later_rows}, {"known": "1000", "gap": "1000"})
        # Complete now, the answer is cached: a third run pays nothing.
        self.search(self.service(youtube))
        self.assertEqual((youtube.search_calls, youtube.statistics_calls), (1, 1))

    def test_statistics_still_missing_keep_the_result_partial(self):
        youtube = CountingYouTube(self.ROWS, statistics_complete=False)
        self.search(self.service(youtube))

        rows, diagnostics = self.search(self.service(youtube))

        self.assertEqual(diagnostics["query_attempts"][0]["status"], "partial")
        self.assertEqual(diagnostics["queries_successful"], 0)
        self.assertEqual([row["video_id"] for row in rows], ["known", "gap"])
        self.assertIsNone(rows[1]["view_count"])  # still unknown, not zero
        self.assertEqual((youtube.search_calls, youtube.statistics_calls), (1, 1))


if __name__ == "__main__":
    unittest.main()
