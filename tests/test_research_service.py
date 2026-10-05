"""Research runs: caching, warnings, snapshot recording and the results-only mode."""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import requests

from win_engine.analysis.creator_brief import build_creator_brief
from win_engine.core.config import Settings
from win_engine.ingestion import cache as cache_module
from win_engine.ingestion import research_service, youtube_client
from win_engine.ingestion.research_service import ResearchService


FETCH_TIME = "stamped when fetched"


def _row(video_id, title, **overrides):
    row = {
        "video_id": video_id, "title": title, "description": "", "channel_title": "Channel",
        "view_count": "1000", "like_count": "10", "comment_count": "1", "subscriber_count": "100",
        "published_at": "2026-09-01T00:00:00Z", "duration": "PT30S", "captured_at": FETCH_TIME,
    }
    return {**row, **overrides}


class FakeYouTube:
    """search_videos answers from a table of query -> (rows, warning).

    attach_statistics completes every row, or fails with ``statistics_warning``.
    """

    def __init__(self, answers):
        self.answers = answers
        self.calls = []
        self.statistics_calls = []
        self.statistics_warning = None
        self._warning = None

    def search_videos(self, query, max_results=5, raise_on_error=False, **locale):
        self.calls.append({"query": query, "max_results": max_results, **locale})
        rows, self._warning = self.answers.get(query, ([], None))
        # Like the real client, complete rows are stamped at fetch time.
        now = datetime.now(timezone.utc).isoformat()
        return [{**row, "captured_at": now if row["captured_at"] == FETCH_TIME else row["captured_at"]}
                for row in rows]

    def attach_statistics(self, rows):
        self.statistics_calls.append([row["video_id"] for row in rows])
        self._warning = self.statistics_warning
        if self._warning:
            return [dict(row) for row in rows]
        now = datetime.now(timezone.utc).isoformat()
        return [{**row, "view_count": "1000", "subscriber_count": "100", "captured_at": now} for row in rows]

    def runtime_state(self):
        return {"active_key_index": 1, "available_key_count": 1, "warning": self._warning, "quota_date": "2026-09-25"}


class _ServiceTestCase(unittest.TestCase):
    def setUp(self):
        # The cache is process-wide; each test starts from an empty registry.
        patcher = patch.dict(cache_module._SHARED_CACHES, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def service(self, answers, **settings):
        service = ResearchService(Settings(database_path=":memory:", **settings))
        service._youtube = FakeYouTube(answers)
        service._history = MagicMock()
        return service

    @staticmethod
    def search(service, *queries, **locale):
        planned = [{"type": "primary", "query": query} for query in queries]
        return service._search_research_queries(planned, **locale)


class CacheTests(_ServiceTestCase):
    def test_rows_without_statistics_are_not_cached_as_an_answer(self):
        answers = {"grief quotes": ([_row("v1", "Grief", captured_at=None, view_count=None)],
                                    "YouTube API request failed: quotaExceeded")}
        first = self.service(answers)
        _, diagnostics = self.search(first, "grief quotes")
        second = self.service(answers)
        second._youtube.statistics_warning = "YouTube API request failed: quotaExceeded"
        rows, again = self.search(second, "grief quotes")
        third = self.service(answers)
        self.search(third, "grief quotes")

        self.assertEqual(diagnostics["query_attempts"][0]["status"], "partial")
        self.assertEqual(diagnostics["queries_partial"], 1)
        # Only the statistics are asked for again, never another search call.
        self.assertEqual((second._youtube.calls, second._youtube.statistics_calls), ([], [["v1"]]))
        self.assertEqual(again["query_attempts"][0]["status"], "partial")
        self.assertIsNone(rows[0]["view_count"])  # still unknown, not zero
        self.assertEqual((third._youtube.calls, third._youtube.statistics_calls), ([], [["v1"]]))

    def test_statistics_found_later_complete_the_cached_answer(self):
        answers = {"grief quotes": ([_row("v1", "Grief", captured_at=None, view_count=None)],
                                    "YouTube API request failed: quotaExceeded")}
        self.search(self.service(answers), "grief quotes")
        second = self.service(answers)
        rows, diagnostics = self.search(second, "grief quotes")
        third = self.service(answers)
        self.search(third, "grief quotes")

        self.assertEqual(rows[0]["view_count"], "1000")
        self.assertEqual(diagnostics["query_attempts"][0]["status"], "success")
        self.assertEqual((third._youtube.calls, third._youtube.statistics_calls), ([], []))

    def test_complete_results_are_shared_by_later_services(self):
        answers = {"grief quotes": ([_row("v1", "Grief")], None)}
        self.search(self.service(answers), "grief quotes")
        later = self.service(answers)

        rows, diagnostics = self.search(later, "grief quotes")

        self.assertEqual(later._youtube.calls, [])
        self.assertEqual(diagnostics["query_attempts"][0]["cache"], "hit")
        self.assertEqual([row["video_id"] for row in rows], ["v1"])

    def test_an_empty_answer_is_cached_as_an_answer(self):
        self.search(self.service({}), "grief quotes")
        later = self.service({})

        _, diagnostics = self.search(later, "grief quotes")

        self.assertEqual(later._youtube.calls, [])
        self.assertEqual(diagnostics["query_attempts"][0]["status"], "success")

    def test_region_language_and_page_size_are_part_of_the_cache_key(self):
        answers = {"grief quotes": ([_row("v1", "Grief")], None)}
        self.search(self.service(answers), "grief quotes", region="india", primary_language="tamil")
        other_region = self.service(answers)
        self.search(other_region, "grief quotes", region="us", primary_language="tamil")
        other_size = self.service(answers, youtube_max_results=10)
        self.search(other_size, "grief quotes", region="india", primary_language="tamil")

        self.assertEqual(other_region._youtube.calls[0]["region_code"], "US")
        self.assertEqual(other_region._youtube.calls[0]["relevance_language"], "ta")
        self.assertEqual(len(other_size._youtube.calls), 1)

    def test_cached_rows_are_not_decoded_twice(self):
        # The client decoded "Tom &amp;amp; Jerry" once; a second decode on the
        # way out of the cache turned it into "Tom & Jerry".
        answers = {"tom jerry": ([_row("v1", "Tom &amp; Jerry")], None)}
        self.search(self.service(answers), "tom jerry")

        rows, _ = self.search(self.service(answers), "tom jerry")

        self.assertEqual(rows[0]["title"], "Tom &amp; Jerry")

    def test_query_without_a_searchable_word_is_not_sent(self):
        service = self.service({})

        _, diagnostics = self.search(service, "quotes shorts")

        self.assertEqual(service._youtube.calls, [])
        self.assertEqual(diagnostics["query_attempts"][0]["status"], "skipped")


class PageSizeAndDurationTests(_ServiceTestCase):
    """One search call brings a page of 25 (the same cost as 5), filtered to the video's length class."""

    ANSWERS = {"grief quotes": ([_row("v1", "Grief quotes")], None)}

    def test_a_search_asks_for_one_page_of_the_configured_size(self):
        service = self.service(self.ANSWERS)
        self.search(service, "grief quotes")
        self.assertEqual(service._youtube.calls[0]["max_results"], 25)
        self.assertEqual(Settings().youtube_max_results, 25)

    def test_each_format_asks_youtube_for_its_own_length_band(self):
        # YouTube's bands: short under 4 minutes, medium 4-20, long over 20.
        planned = [{"type": "primary", "query": "grief quotes"}]
        briefs = [
            ("short", {"video_format": "youtube_shorts"}),
            ("medium", {"video_format": "tutorial", "duration_seconds": 600}),
            ("long", {"video_format": "long_form", "duration_seconds": 1800}),
            # "Any format" on the Demand page: the format was only inferred.
            (None, build_creator_brief(script="python csv parsing")),
        ]
        for expected, brief in briefs:
            with self.subTest(expected=expected):
                service = self.service(self.ANSWERS)
                with patch.object(research_service, "plan_research_queries", return_value=planned):
                    service.gather("topic", creator_brief=brief, results_only=True)
                self.assertEqual([call["video_duration"] for call in service._youtube.calls], [expected])

    def test_a_long_form_video_searches_every_length_unless_its_length_sits_well_inside_a_band(self):
        # One band a search: "medium" for a tutorial of unknown length dropped
        # every 25-60 minute rival, and "long" for a 21-minute review every
        # 15-20 minute one. A length near a band's edge competes on both sides.
        cases = [
            ({"video_format": "tutorial"}, None),  # no stated length
            ({"video_format": "tutorial", "duration_seconds": 70}, None),  # under 4 minutes: no long-form band
            ({"video_format": "vlog", "duration_seconds": 210}, None),
            ({"video_format": "tutorial", "duration_seconds": 360}, None),  # 6 minutes: within 3 of the 4-minute edge
            ({"video_format": "tutorial", "duration_seconds": 600}, "medium"),
            ({"video_format": "review", "duration_seconds": 1080}, None),  # 18 minutes
            ({"video_format": "review", "duration_seconds": 1260}, None),  # 21 minutes
            ({"video_format": "long_form", "duration_seconds": 1800}, "long"),
            # A number read out of the script is not the video's length.
            (build_creator_brief(script="a 30 minute workout explained", video_format="tutorial"), None),
        ]
        for brief, expected in cases:
            with self.subTest(brief={key: brief.get(key) for key in ("video_format", "duration_seconds")}):
                self.assertEqual(research_service._search_duration(False, brief), expected)
        self.assertEqual(research_service._search_duration(True, {"duration_seconds": 1800}), "short")

    def test_the_duration_filter_is_part_of_the_cache_key(self):
        planned = [{"type": "primary", "query": "grief quotes"}]
        first, second, third = (self.service(self.ANSWERS) for _ in range(3))
        first._search_research_queries(planned, video_duration="short")
        second._search_research_queries(planned)
        _, diagnostics = third._search_research_queries(planned, video_duration="short")

        self.assertEqual(len(second._youtube.calls), 1)
        self.assertEqual((third._youtube.calls, diagnostics["query_attempts"][0]["cache"]), ([], "hit"))

    def test_research_says_when_it_left_its_gemini_calls_to_the_writer(self):
        service = self.service(self.ANSWERS)
        service._suggest = MagicMock(fetch=MagicMock(return_value={"status": "disabled"}))
        reserved = {"primary_topic": "", "secondary_topics": [], "search_intents": [], "keyword_clusters": [],
                    "concept_evidence": [], "source": "local_fallback", "fallback_reason": "gemini_writer_reserve"}
        local = {name: MagicMock(return_value=value) for name, value in {
            "analyze_script_semantics": reserved, "refine_research_semantics": {},
            "discover_search_opportunities": {}, "build_keyword_research": {"candidates": []},
            "demand_seed_phrases": [], "extract_keyword_signals": [], "extract_entity_signals": [],
            "build_upload_timing": {}, "analyze_thumbnails": {}, "build_research_decision": {},
            "plan_research_queries": [{"type": "primary", "query": "grief quotes"}],
        }.items()}
        with patch.multiple(research_service, **local):
            research = service.gather("topic")

        self.assertTrue(any("left to the writer" in item for item in research["research_warnings"]), research["research_warnings"])


def _http(status, payload):
    response = MagicMock(status_code=status)
    response.json.return_value = payload
    if status >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
    return response


class QuotaTests(_ServiceTestCase):
    """The real client over mocked HTTP: search.list spends one call of its own bucket, videos and channels 1 unit each."""

    def setUp(self):
        super().setUp()
        patcher = patch.dict(youtube_client._ROTATIONS, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_failed_statistics_lookup_is_retried_without_a_new_search(self):
        spent = (403, {"error": {"errors": [{"reason": "quotaExceeded"}]}})
        replies = {
            "search": [(200, {"items": [{"id": {"videoId": "v1"},
                                         "snippet": {"channelId": "UC1", "title": "Grief quotes"}}]})],
            "videos": [spent, (200, {"items": [{"id": "v1", "statistics": {"viewCount": "10"},
                                                "contentDetails": {"duration": "PT30S"}}]})],
            # Not asked while the video statistics are missing: that row could not be complete.
            "channels": [(200, {"items": [{"id": "UC1", "statistics": {"subscriberCount": "5"}}]})],
        }
        requested = []

        def get(url, **_kwargs):
            name = url.rsplit("/", 1)[-1]
            requested.append(name)
            queue = replies[name]  # the last reply repeats
            return _http(*(queue.pop(0) if len(queue) > 1 else queue[0]))

        runs = []
        with patch("win_engine.ingestion.youtube_client.requests.get", side_effect=get):
            for _ in range(3):
                start = len(requested)
                rows, _ = self.search(ResearchService(Settings(database_path=":memory:", youtube_api_key="key")),
                                      "grief quotes")
                runs.append((requested[start:], rows[0]["view_count"]))

        self.assertEqual(runs, [
            (["search", "videos"], None),  # the statistics failed: unknown, not zero
            (["videos", "channels"], "10"),  # 2 units, and no second search call
            ([], "10"),  # complete now, so served from the cache
        ])


class RelevanceTermTests(unittest.TestCase):
    def test_a_number_alone_is_not_a_term_a_result_must_echo(self):
        self.assertEqual(ResearchService._query_terms("best budget phone 2024"), {"best", "budget", "phone"})
        self.assertEqual(ResearchService._query_terms("ps5 horror games"), {"ps5", "horror", "games"})
        row = {"video_id": "v", "title": "Best budget phones under 20000 - full review", "description": "",
               "channel_title": "Channel",
               "matched_query_details": [{"query": "best budget phone 2024", "type": "primary"}]}

        self.assertEqual(len(ResearchService._filter_relevant_results([row])), 1)


class GatherTests(_ServiceTestCase):
    def gather(self, service, queries, **kwargs):
        planned = [{"type": "primary", "query": query} for query in queries]
        with patch.object(research_service, "plan_research_queries", return_value=planned):
            return service.gather("topic", **kwargs)

    def test_results_only_mode_skips_gemini_suggestions_and_keyword_research(self):
        service = self.service({"grief quotes": ([_row("v1", "Grief quotes")], None)})
        service._suggest = MagicMock()
        expensive = {name: MagicMock() for name in (
            "analyze_script_semantics", "refine_research_semantics", "discover_search_opportunities",
            "build_keyword_research", "demand_seed_phrases",
        )}
        with patch.multiple(research_service, **expensive):
            research = self.gather(service, ["grief quotes"], results_only=True)

        for name, mock in expensive.items():
            with self.subTest(name=name):
                mock.assert_not_called()
        service._suggest.fetch.assert_not_called()
        self.assertEqual([row["video_id"] for row in research["youtube_results"]], ["v1"])
        self.assertIsNotNone(research["youtube_results"][0]["outlier_score"])

    def test_every_failed_query_reaches_the_warnings(self):
        service = self.service({
            "grief quotes": ([], "YouTube API request failed: quotaExceeded"),
            "silence in grief": ([_row("v1", "Silence in grief")], None),
        })

        research = self.gather(service, ["grief quotes", "silence in grief"], results_only=True)

        self.assertEqual(research["research_warnings"], ["YouTube API request failed: quotaExceeded"])

    def test_only_fresh_rows_are_recorded_each_under_its_own_query(self):
        answers = {"grief quotes": ([_row("v1", "Grief quotes")], None),
                   "silence in grief": ([_row("v2", "Silence in grief")], None)}
        first = self.service(answers)
        self.gather(first, ["grief quotes", "silence in grief"], results_only=True)
        later = self.service(answers)
        self.gather(later, ["grief quotes", "silence in grief"], results_only=True)

        recorded = {call.args[0]: [row["video_id"] for row in call.args[1]]
                    for call in first._history.record_snapshots.call_args_list}
        self.assertEqual(recorded, {"grief quotes": ["v1"], "silence in grief": ["v2"]})
        later._history.record_snapshots.assert_not_called()  # served from the cache

    def test_stale_or_incomplete_rows_are_not_recorded(self):
        week_old = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        service = self.service({"grief quotes": ([_row("old", "Grief quotes", captured_at=week_old),
                                                  _row("gap", "Grief", captured_at=None)], None)})

        self.gather(service, ["grief quotes"], results_only=True)

        service._history.record_snapshots.assert_not_called()

    def test_velocity_is_no_longer_read_per_result(self):
        service = self.service({"grief quotes": ([_row("v1", "Grief quotes")], None)})

        research = self.gather(service, ["grief quotes"], results_only=True)

        service._history.velocity_signals.assert_not_called()
        self.assertNotIn("velocity_24h", research["youtube_results"][0])

    def test_unscored_rows_stay_out_of_top_opportunities(self):
        service = self.service({"grief quotes": ([_row("hidden", "Grief quotes", subscriber_count=None),
                                                  _row("known", "Grief quotes")], None)})

        research = self.gather(service, ["grief quotes"], results_only=True)

        self.assertEqual([row["video_id"] for row in research["top_opportunities"]], ["known"])
        self.assertEqual(len(research["youtube_results"]), 2)

    def test_a_query_is_found_whichever_query_led_the_earlier_run(self):
        queries = ("latest iphone review", "iphone camera test", "iphone battery test")
        answers = {query: ([_row(query, query.title())], None) for query in queries}
        self.gather(self.service(answers), queries[:2], results_only=True)  # a "trending" run
        later = self.service(answers)

        research = self.gather(later, queries[1:], results_only=True)  # an "evergreen" run

        self.assertEqual([call["query"] for call in later._youtube.calls], ["iphone battery test"])
        self.assertEqual(research["research_diagnostics"]["query_attempts"][0]["cache"], "hit")

    def test_each_query_is_cached_for_its_own_policy(self):
        queries = ("latest iphone review", "iphone camera test")
        service = self.service({query: ([_row(query, query.title())], None) for query in queries})
        service._cache = MagicMock(wraps=service._cache)

        research = self.gather(service, queries, results_only=True)

        settings = Settings()
        self.assertEqual(research["cache_policy"], "trending")  # the run's first query, reported only
        self.assertEqual([call.kwargs["ttl_seconds"] for call in service._cache.set.call_args_list],
                         [settings.cache_ttl_trending_seconds, settings.cache_ttl_evergreen_seconds])

    @staticmethod
    def refine(service, plans, creator_brief=None):
        """A full run whose first pass finds too little evidence, so the refinement pass runs."""

        service._suggest = MagicMock(fetch=MagicMock(return_value={"status": "disabled"}))
        local = {name: MagicMock(return_value=value) for name, value in {
            "analyze_script_semantics": {}, "refine_research_semantics": {"primary_topic": "silence"},
            "discover_search_opportunities": {}, "build_keyword_research": {"candidates": []},
            "demand_seed_phrases": [], "extract_keyword_signals": [], "extract_entity_signals": [],
            "build_upload_timing": {}, "analyze_thumbnails": {}, "build_research_decision": {},
        }.items()}
        planner = MagicMock(side_effect=plans)
        with patch.multiple(research_service, plan_research_queries=planner, **local):
            research = service.gather("topic", creator_brief=creator_brief)
        research["planner_limits"] = [call.kwargs.get("max_queries") for call in planner.call_args_list]
        research["mocks"] = local
        return research

    FIRST_PASS = ["grief quotes", "silence grief", "grief poetry", "missing someone", "empty chair"]
    REFINEMENT = ["quiet loss", "unsaid words", "late goodbye"]

    def plans(self, first):
        return [[{"type": "primary", "query": query} for query in first],
                [{"type": "secondary_topic", "query": query} for query in self.REFINEMENT]]

    def test_a_short_spends_at_most_three_searches_refinement_included(self):
        # search.list has its own bucket of 100 calls a day per project.
        short = {"video_format": "youtube_shorts"}
        for first, expected in (
            (self.FIRST_PASS, self.FIRST_PASS[:3]),                # a planner that over-delivers is cut to three
            (self.FIRST_PASS[:1], ["grief quotes", *self.REFINEMENT[:2]]),
            (self.FIRST_PASS[:2], [*self.FIRST_PASS[:2], self.REFINEMENT[0]]),
        ):
            with self.subTest(first=first):
                cache_module._SHARED_CACHES.clear()  # each run pays for its own searches
                service = self.service({}, youtube_max_research_queries=5)
                research = self.refine(service, self.plans(first), creator_brief=short)
                self.assertEqual([call["query"] for call in service._youtube.calls], expected)
                self.assertEqual([item["query"] for item in research["research_queries"]], expected)
                self.assertEqual(research["planner_limits"][0], 3)

    def test_long_form_research_is_unchanged(self):
        service = self.service({}, youtube_max_research_queries=5)
        research = self.refine(service, self.plans(self.FIRST_PASS), creator_brief={"video_format": "tutorial"})
        self.assertEqual([call["query"] for call in service._youtube.calls], [*self.FIRST_PASS, *self.REFINEMENT[:2]])
        self.assertEqual(research["planner_limits"][0], 5)

    def test_refinement_keeps_the_first_pass_queries_of_a_video(self):
        row = _row("same", "Silence in grief")
        service = self.service({"grief quotes": ([row], None), "silence grief": ([row], None)})

        research = self.refine(service, [[{"type": "primary", "query": "grief quotes"}],
                                         [{"type": "secondary_topic", "query": "silence grief"}]])

        (merged,) = research["youtube_results"]
        self.assertEqual(merged["matched_queries"], ["grief quotes", "silence grief"])
        self.assertEqual([item["query"] for item in merged["matched_query_details"]], ["grief quotes", "silence grief"])

    def test_refinement_skips_a_query_that_adds_only_generic_words(self):
        service = self.service({"grief quotes": ([_row("v1", "Grief quotes")], None),
                                "silence grief": ([_row("v2", "Silence in grief")], None)})

        self.refine(service, [[{"type": "primary", "query": "grief quotes"}],
                              [{"type": "secondary_topic", "query": "grief quotes for her"},
                               {"type": "secondary_topic", "query": "silence grief"}]])

        self.assertEqual([call["query"] for call in service._youtube.calls], ["grief quotes", "silence grief"])

    def test_keyword_and_entity_signals_count_the_refinement_results_too(self):
        # The gap analysis compares the signals with the final results; signals
        # counted over the first pass alone made a phrase the refinement's
        # videos use look like the script's own.
        service = self.service({"grief quotes": ([_row("v1", "Grief quotes")], None),
                                "silence grief": ([_row("v2", "Silence in grief")], None)})

        research = self.refine(service, [[{"type": "primary", "query": "grief quotes"}],
                                         [{"type": "secondary_topic", "query": "silence grief"}]])

        self.assertEqual(sorted(row["video_id"] for row in research["youtube_results"]), ["v1", "v2"])
        for name in ("extract_keyword_signals", "extract_entity_signals"):
            with self.subTest(name=name):
                counted = research["mocks"][name].call_args.args[1]
                self.assertEqual(sorted(row["video_id"] for row in counted), ["v1", "v2"])


if __name__ == "__main__":
    unittest.main()
